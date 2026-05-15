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
import time
import traceback
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


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
    def _create_completion(self, messages: list[dict[str, str]]) -> str:
        """Provider-specific 调用，返回原始文本。"""

    def call(self, messages: list[dict[str, str]]) -> dict | None:
        for attempt in range(self.max_retries):
            try:
                content = self._create_completion(messages)
                result = extract_json(content)
                if result is not None:
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

    def _create_completion(self, messages: list[dict[str, str]]) -> str:
        completion = self._client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            temperature=self.temperature,
        )
        return completion.choices[0].message.content


SUPPORTED_PROVIDERS = {"ark"}  # W3 阶段会加 anthropic / openai 子类


def build_judge_client(provider: str, **kwargs: Any) -> BaseJudgeClient:
    """根据 provider 字符串构建对应的 judge client。"""
    if provider == "ark":
        return ArkJudgeClient(**kwargs)
    if provider in {"anthropic", "openai"}:
        raise NotImplementedError(
            f"provider {provider!r} 尚未实现，请暂时使用 ark/doubao；"
            f"AnthropicJudgeClient/OpenAIJudgeClient 计划在 W3 提供"
        )
    raise ValueError(f"unsupported judge provider: {provider!r}")
