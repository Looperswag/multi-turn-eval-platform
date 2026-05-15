"""灌入初始数据：判官模型、prompt v4、baseline bot、mock 100 条 query。

运行：`make seed`  等同于  `python -m app.seeds.seed`
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import (
    BotRewrite,
    BotVersion,
    Conversation,
    Dataset,
    JudgeModel,
    JudgePromptVersion,
    Turn,
)

# 现有 mock 数据相对路径：仓库内的 self-production/mock_multi_turn_queries_100.json
# 在容器内默认挂载到 /seeds/mock_multi_turn_queries_100.json（见 docker-compose volumes）
DEFAULT_DATA_PATH = os.environ.get("SEED_DATA_PATH", "/seeds/mock_multi_turn_queries_100.json")

DIMENSION_WEIGHTS = {
    "dim1": 0.30,
    "dim2": 0.30,
    "dim3": 0.10,
    "dim4": 0.10,
    "dim5": 0.10,
    "dim6": 0.10,
}

# W1：prompt template 暂存「占位 marker」，evaluator 仍走 prompts.py 硬编码字符串。
# W2 改造 PromptRenderer 后，把 markdown 完整 prompt 写入此处。
PROMPT_PLACEHOLDER_NOTE = "v4 baseline — 当前 evaluator 仍从 app/services/eval_engine/prompts.py 读取硬编码 prompt；W2 阶段将切换为读取此字段。"


def seed_judge_models(db) -> JudgeModel:
    """从 settings.ark_default_model 读取模型 id，保证与 .env 一致。"""
    model_id = settings.ark_default_model
    existing = db.scalar(select(JudgeModel).where(JudgeModel.provider == "ark"))
    if existing:
        # 若 .env 改过模型，校正 DB 行（保留同一 provider 的唯一记录）
        if existing.model_id != model_id:
            existing.model_id = model_id
            existing.name = f"Doubao · {model_id}"
            db.flush()
        return existing
    obj = JudgeModel(
        name=f"Doubao · {model_id}",
        provider="ark",
        model_id=model_id,
        temperature=settings.default_judge_temperature,
        is_default=True,
    )
    db.add(obj)
    db.flush()
    return obj


def seed_prompt_versions(db) -> dict[str, int]:
    """灌入 6 个维度的 v4 prompt 版本。"""
    result: dict[str, int] = {}
    for code, weight in DIMENSION_WEIGHTS.items():
        existing = db.scalar(
            select(JudgePromptVersion)
            .where(JudgePromptVersion.dimension_code == code)
            .where(JudgePromptVersion.version_tag == "v4")
        )
        if existing:
            result[code] = existing.id
            continue
        obj = JudgePromptVersion(
            dimension_code=code,
            version_tag="v4",
            weight=weight,
            prompt_template=PROMPT_PLACEHOLDER_NOTE,
            notes="W1 seed: 实际 prompt 走代码硬编码；W2 起此字段将作为唯一来源。",
        )
        db.add(obj)
        db.flush()
        result[code] = obj.id
    return result


def seed_baseline_bot(db) -> BotVersion:
    existing = db.scalar(select(BotVersion).where(BotVersion.version_tag == "baseline"))
    if existing:
        return existing
    obj = BotVersion(
        name="Baseline bot",
        version_tag="baseline",
        description="导入 mock 数据时的原始 rewrite 输出，作为默认基线。",
        bot_provider="mock",
        base_model="seed",
    )
    db.add(obj)
    db.flush()
    return obj


def seed_dataset(db, data_path: str, baseline_bot: BotVersion) -> Dataset:
    existing = db.scalar(
        select(Dataset).where(Dataset.name == "mock_multi_turn_queries_100")
    )
    if existing:
        return existing
    raw = Path(data_path).read_text(encoding="utf-8")
    data = json.loads(raw)
    dataset = Dataset(
        name="mock_multi_turn_queries_100",
        description="种子数据：100 条多轮会话覆盖六大维度 + good/bad 标签。",
        version="v1",
        source_file_uri=str(data_path),
        conversation_count=len(data),
    )
    db.add(dataset)
    db.flush()
    for conv_payload in data:
        conv = Conversation(
            dataset_id=dataset.id,
            conversation_id_src=conv_payload["conversation_id"],
            dimension_tag=conv_payload.get("dimension_tag"),
            quality_label=conv_payload.get("quality_label"),
            issue_type=conv_payload.get("issue_type"),
            total_turns=conv_payload.get("total_turns", len(conv_payload.get("turns", []))),
        )
        db.add(conv)
        db.flush()
        for t in conv_payload.get("turns", []):
            turn = Turn(
                conversation_id=conv.id,
                turn_index=t["turn_index"],
                user_query=t["user_query"],
                timestamp=t.get("timestamp"),
            )
            db.add(turn)
            db.flush()
            db.add(
                BotRewrite(
                    turn_id=turn.id,
                    bot_version_id=baseline_bot.id,
                    rewritten_query=t.get("rewritten_query"),
                )
            )
    return dataset


def main():
    db = SessionLocal()
    try:
        judge_model = seed_judge_models(db)
        prompt_ids = seed_prompt_versions(db)
        baseline_bot = seed_baseline_bot(db)
        if not Path(DEFAULT_DATA_PATH).exists():
            print(f"[WARN] seed data file not found at {DEFAULT_DATA_PATH}; skipped dataset seed")
            db.commit()
            return
        dataset = seed_dataset(db, DEFAULT_DATA_PATH, baseline_bot)
        db.commit()
        print("[OK] seed completed:")
        print(f"  judge_model id={judge_model.id} model={judge_model.model_id}")
        print(f"  prompt_versions v4: {prompt_ids}")
        print(f"  bot_version baseline id={baseline_bot.id}")
        print(f"  dataset id={dataset.id} name={dataset.name} conversations={dataset.conversation_count}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
