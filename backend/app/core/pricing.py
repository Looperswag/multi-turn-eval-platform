"""LLM judge 调用计价表。

数据来源：各厂商官网公布价（截止 2026-05；如调价只需改这一个文件）。
单位：USD per 1M tokens，prompt / completion 分开。
USD → CNY 用固定汇率（部署时如需精准可改为日汇率 API，本平台不做实时折算）。
"""
from __future__ import annotations

# USD per 1M tokens
PRICES_USD_PER_M: dict[str, dict[str, float]] = {
    # DeepSeek 官网价（https://api-docs.deepseek.com/quick_start/pricing）
    "deepseek-chat": {"prompt": 0.27, "completion": 1.10},
    "deepseek-reasoner": {"prompt": 0.55, "completion": 2.19},
    "deepseek-v4-pro": {"prompt": 0.55, "completion": 2.19},  # 与 reasoner 同档
    # 火山引擎 ARK · 豆包系列（https://www.volcengine.com/docs/82379/1099455）
    "doubao-seed-2-0-pro-260215": {"prompt": 0.80, "completion": 2.00},
    "doubao-1.5-pro-32k": {"prompt": 0.80, "completion": 2.00},
    # Anthropic 官网价（https://www.anthropic.com/pricing#api）
    "claude-3-5-sonnet-20241022": {"prompt": 3.00, "completion": 15.00},
    "claude-sonnet-4-5": {"prompt": 3.00, "completion": 15.00},
    # OpenAI 官网价（https://openai.com/api/pricing/）
    "gpt-4o": {"prompt": 2.50, "completion": 10.00},
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
}

USD_TO_CNY = 7.20  # 部署时如需变更，改此常量


def compute_cost(
    model_id: str, prompt_tokens: int, completion_tokens: int
) -> tuple[float, float]:
    """返回 (cost_usd, cost_cny)。未知 model_id 时返回 (0, 0)（不致命，但 dashboard 会显示 ¥0 提示去补价）。"""
    price = PRICES_USD_PER_M.get(model_id)
    if price is None:
        return 0.0, 0.0
    usd = (
        prompt_tokens * price["prompt"] + completion_tokens * price["completion"]
    ) / 1_000_000
    cny = usd * USD_TO_CNY
    return round(usd, 6), round(cny, 6)
