"""Judge 模型客户端抽象。

设计：
- BaseJudgeClient 定义统一接口 call(messages) -> dict | None
- ArkJudgeClient 复用现有火山引擎实现，含重试 + JSON 提取
- 后续 W3 增加 AnthropicJudgeClient / OpenAIJudgeClient 兄弟类
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import traceback
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import settings
from app.core.pricing import compute_cost

logger = logging.getLogger(__name__)

# M1.5：thread-local 成本回收 — 每个 worker 线程在 evaluate 前 set_cost_sink([])，
# evaluate 后读取累积的 cost_record 写 DB。判官 client 保持 stateless，多线程共享。
_thread_local = threading.local()


def set_cost_sink(sink: list[dict] | None) -> None:
    _thread_local.cost_sink = sink


def get_cost_sink() -> list[dict] | None:
    return getattr(_thread_local, "cost_sink", None)


def set_dim_context(dim_code: str | None) -> None:
    """Evaluator 在调用 _call 前设置自己的 dim_code，让 cost_record 带上来源维度。"""
    _thread_local.dim_code = dim_code


def get_dim_context() -> str | None:
    return getattr(_thread_local, "dim_code", None)


def extract_json(text: str) -> dict | None:
    """从模型返回文本中提取 JSON。支持 ```json 代码块、纯 JSON、嵌入 JSON 三种格式。"""
    if not text:
        return None
    json_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_block:
        try:
            return json.loads(json_block.group(1).strip())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


class BaseJudgeClient(ABC):
    provider: str

    def __init__(
        self,
        model_id: str,
        temperature: float = 0.1,
        max_retries: int = 3,
        timeout: int = 1800,
    ) -> None:
        self.model_id = model_id
        self.temperature = temperature
        self.max_retries = max_retries
        self.timeout = timeout

    @abstractmethod
    def _create_completion(
        self, messages: list[dict[str, str]]
    ) -> tuple[str, int, int]:
        """Provider-specific 调用，返回 (text, prompt_tokens, completion_tokens)。"""

    def _record_cost(self, prompt_tokens: int, completion_tokens: int) -> None:
        sink = get_cost_sink()
        if sink is None:
            return
        cost_usd, cost_cny = compute_cost(self.model_id, prompt_tokens, completion_tokens)
        sink.append(
            {
                "dimension_code": get_dim_context() or "unknown",
                "model_id": self.model_id,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost_usd": cost_usd,
                "cost_cny": cost_cny,
            }
        )

    def call(self, messages: list[dict[str, str]]) -> dict | None:
        for attempt in range(self.max_retries):
            try:
                content, prompt_tokens, completion_tokens = self._create_completion(messages)
                result = extract_json(content)
                if result is not None:
                    # 仅在 JSON 解析成功的调用算入成本（失败重试不重复计费）
                    self._record_cost(prompt_tokens, completion_tokens)
                    return result
                logger.warning(
                    "judge[%s] attempt=%d returned non-JSON: %s",
                    self.provider,
                    attempt + 1,
                    (content or "")[:200],
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("judge[%s] attempt=%d failed: %s", self.provider, attempt + 1, exc)
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    time.sleep(wait_time)
                else:
                    traceback.print_exc()
        return None


class ArkJudgeClient(BaseJudgeClient):
    provider = "ark"

    def __init__(
        self,
        model_id: str | None = None,
        temperature: float = 0.1,
        max_retries: int = 3,
        timeout: int | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(
            model_id=model_id or settings.ark_default_model,
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout or settings.ark_timeout,
        )
        from volcenginesdkarkruntime import Ark  # 延迟导入，避免无 ARK key 时启动失败

        self._client = Ark(
            base_url=base_url or settings.ark_base_url,
            api_key=api_key or settings.ark_api_key,
            timeout=self.timeout,
        )

    def _create_completion(self, messages: list[dict[str, str]]) -> tuple[str, int, int]:
        completion = self._client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            temperature=self.temperature,
        )
        text = completion.choices[0].message.content
        usage = getattr(completion, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        return text, prompt_tokens, completion_tokens


class DeepSeekJudgeClient(BaseJudgeClient):
    """DeepSeek judge client。走官方 Anthropic 兼容端点 (base_url=.../anthropic)。

    DeepSeek 的 /anthropic 端点接受标准 Anthropic messages API，
    因此直接复用 anthropic SDK 即可，只需替换 base_url。
    """

    provider = "deepseek"

    def __init__(
        self,
        model_id: str | None = None,
        temperature: float = 0.1,
        max_retries: int = 3,
        timeout: int | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        super().__init__(
            model_id=model_id or settings.deepseek_default_model,
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout or settings.ark_timeout,
        )
        from anthropic import Anthropic  # 延迟导入

        resolved_key = api_key or settings.deepseek_api_key
        if not resolved_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY 未配置；请在 backend/.env 中设置后重启 api/worker"
            )
        self._client = Anthropic(
            api_key=resolved_key,
            base_url=base_url or settings.deepseek_base_url,
            timeout=float(self.timeout),
        )
        self._max_tokens = max_tokens or settings.deepseek_max_tokens

    def _create_completion(self, messages: list[dict[str, str]]) -> tuple[str, int, int]:
        # Anthropic 协议要求 system 与 messages 分离；把 OpenAI 风格的
        # role=system 抽出来作为顶层 system 参数。
        system_parts: list[str] = []
        chat_messages: list[dict[str, str]] = []
        for m in messages:
            if m.get("role") == "system":
                content = m.get("content")
                if content:
                    system_parts.append(content)
            else:
                chat_messages.append({"role": m["role"], "content": m["content"]})

        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": self._max_tokens,
            "temperature": self.temperature,
            "messages": chat_messages or [{"role": "user", "content": ""}],
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)

        resp = self._client.messages.create(**kwargs)
        # Anthropic usage 字段名是 input_tokens / output_tokens
        usage = getattr(resp, "usage", None)
        prompt_tokens = getattr(usage, "input_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "output_tokens", 0) if usage else 0
        # 取首个 text block 的内容
        for block in resp.content or []:
            text = getattr(block, "text", None)
            if text:
                return text, prompt_tokens, completion_tokens
        return "", prompt_tokens, completion_tokens


SUPPORTED_PROVIDERS = {"ark", "deepseek"}  # anthropic/openai 暂未启用


def build_judge_client(provider: str, **kwargs: Any) -> BaseJudgeClient:
    """根据 provider 字符串构建对应的 judge client。"""
    if provider == "ark":
        return ArkJudgeClient(**kwargs)
    if provider == "deepseek":
        return DeepSeekJudgeClient(**kwargs)
    if provider in {"anthropic", "openai"}:
        raise NotImplementedError(
            f"provider {provider!r} 尚未实现，请暂时使用 ark/deepseek；"
            f"AnthropicJudgeClient/OpenAIJudgeClient 计划在 W3 提供"
        )
    raise ValueError(f"unsupported judge provider: {provider!r}")
