"""PromptRenderer：把 DB 中的 jinja2 模板字符串渲染为 judge 调用 messages。

W2/A.3 关键改造：从原 prompts.py 硬编码 f-string 切换为 DB 驱动的 jinja2 模板。
- 输入：dict[dim_code -> jinja2_template_str]
- 输出：render(dim_code, **ctx) -> [{"role": "user", "content": str}]

设计要点：
- 使用 StrictUndefined：缺失变量直接报错，避免静默渲染出 "None" 字符串导致评测偏差
- keep_trailing_newline=True：保留原 f-string 末尾换行（vs jinja2 默认 strip）
- 不做 HTML autoescape：模板内容是给 LLM 的纯文本，没有注入风险
"""
from __future__ import annotations

from jinja2 import Environment, StrictUndefined


class PromptRenderer:
    def __init__(
        self,
        templates: dict[str, str],
        strategies: dict[str, str] | None = None,
    ):
        env = Environment(
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
        )
        self._sources: dict[str, str] = dict(templates)
        self._strategies: dict[str, str] = dict(strategies or {})
        self.envs = {code: env.from_string(tmpl) for code, tmpl in templates.items()}

    def render(self, dim_code: str, **ctx) -> list[dict[str, str]]:
        if dim_code not in self.envs:
            raise KeyError(f"PromptRenderer: no template for dimension '{dim_code}'")
        rendered = self.envs[dim_code].render(**ctx)
        return [{"role": "user", "content": rendered}]

    def template_source(self, dim_code: str) -> str | None:
        return self._sources.get(dim_code)

    def strategy(self, dim_code: str) -> str:
        """返回该维度的评估调用策略；缺失或未配置时回落到 per_turn。"""
        return self._strategies.get(dim_code, "per_turn")
