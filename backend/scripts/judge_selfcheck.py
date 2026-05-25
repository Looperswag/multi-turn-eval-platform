"""Judge 联通性自检脚本。

用途：在调评测 run 之前，先确认 Ark / DeepSeek 两路 judge 都能：
  1. 完成一次 chat completion 调用
  2. 返回可被 extract_json 解析的 JSON

容器内运行：
  docker compose exec api python -m scripts.judge_selfcheck
本地（已 source backend/.env）：
  cd backend && python -m scripts.judge_selfcheck

退出码：
  0 = 所有 provider 通过
  1 = 至少一个 provider 失败
"""
from __future__ import annotations

import os
import sys
import time

# 允许 `python -m scripts.judge_selfcheck` 与直接执行两种方式
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.services.eval_engine.judge_client import (  # noqa: E402
    build_judge_client,
    extract_json,
)

PROBE_MESSAGES = [
    {
        "role": "user",
        "content": (
            "请严格输出以下 JSON（不要包裹 markdown 代码块、不要多余文字）：\n"
            '{"ok": true, "score": 0.5, "note": "selfcheck"}'
        ),
    }
]


def _probe(provider: str, model_id: str | None, api_key: str | None) -> tuple[bool, str]:
    """返回 (ok, message)。"""
    if not api_key:
        return False, f"{provider}: API key 未配置（.env 里对应字段为空）"

    try:
        client = build_judge_client(
            provider=provider,
            model_id=model_id,
            temperature=0.0,
            max_retries=1,
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"{provider}: 客户端构造失败 → {type(exc).__name__}: {exc}"

    t0 = time.time()
    try:
        # 直接调底层 _create_completion，跳过 BaseJudgeClient.call 的 retry/parse，
        # 这样能拿到原始文本，更容易诊断
        raw = client._create_completion(PROBE_MESSAGES)  # noqa: SLF001
    except Exception as exc:  # noqa: BLE001
        return False, (
            f"{provider}: API 调用抛错 → {type(exc).__name__}: {exc}\n"
            f"        model_id={client.model_id!r}"
        )

    elapsed = (time.time() - t0) * 1000
    parsed = extract_json(raw or "")
    snippet = (raw or "").strip().replace("\n", " ")[:200]

    if parsed is None:
        return False, (
            f"{provider}: 返回不是合法 JSON（{elapsed:.0f}ms）\n"
            f"        model_id={client.model_id!r}\n"
            f"        raw[:200]={snippet!r}"
        )
    if "ok" not in parsed:
        return False, (
            f"{provider}: 返回 JSON 缺少预期字段 'ok'（{elapsed:.0f}ms）\n"
            f"        model_id={client.model_id!r}\n"
            f"        parsed={parsed!r}"
        )
    return True, (
        f"{provider}: OK ({elapsed:.0f}ms) "
        f"model_id={client.model_id!r} parsed={parsed!r}"
    )


def main() -> int:
    print("=" * 70)
    print("Judge self-check — 探测 Ark / DeepSeek 两路 judge 是否可用")
    print("=" * 70)
    print(f"ARK_BASE_URL          = {settings.ark_base_url}")
    print(f"ARK_DEFAULT_MODEL     = {settings.ark_default_model}")
    print(f"ARK_API_KEY           = {'(set)' if settings.ark_api_key else '(empty)'}")
    print(f"DEEPSEEK_BASE_URL     = {settings.deepseek_base_url}")
    print(f"DEEPSEEK_DEFAULT_MODEL= {settings.deepseek_default_model}")
    print(f"DEEPSEEK_API_KEY      = {'(set)' if settings.deepseek_api_key else '(empty)'}")
    print("-" * 70)

    failed = []
    for provider, model_id, api_key in [
        ("ark", settings.ark_default_model, settings.ark_api_key),
        ("deepseek", settings.deepseek_default_model, settings.deepseek_api_key),
    ]:
        ok, msg = _probe(provider, model_id, api_key)
        print(("✓ " if ok else "✗ ") + msg)
        if not ok:
            failed.append(provider)

    print("-" * 70)
    if failed:
        print(f"FAILED: {failed}")
        print(
            "若错误是 model not found / invalid endpoint，请在控制台拿到真实 endpoint id："
        )
        print("  Ark:      https://console.volcengine.com/ark → 「在线推理」endpoint 列表")
        print("  DeepSeek: https://api-docs.deepseek.com/zh-cn/  → 模型列表（公开 deepseek-chat / deepseek-reasoner）")
        return 1
    print("ALL OK — 两路 judge 都能正确返回 JSON，可以放心跑评测 run。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
