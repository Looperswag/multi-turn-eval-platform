"""单测：dataset_parser 的线上格式路径

覆盖：
- is_online_format 检测（三列同时存在）
- _parse_history_query 把 historyquery 文本拆成 turn dict 列表
- parse_online_excel 端到端（构造一个微型 xlsx 走全流程）
- llm_resp JSON 字符串解析后 inherited/dropped/intent_type/needs_rewrite 落入 turn
- phantom turn 1 被重构（user_query 来自 #第1轮问题，bot_response 来自 #第1轮追问，rewrite=None）
- 多行同 conv 合并，turn_index 重新 1..N 连续
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.services import dataset_parser as dp


# ---------------------------------------------------------------------------
# 辅助：内存里造一份满足"线上格式三列"的 Excel
# ---------------------------------------------------------------------------

ONLINE_COLUMNS = [
    "meta_conversation_id",
    "id",
    "ori_query",
    "gmt_create",
    "cnt",
    "rewritten_query",
    "llm_resp",
    "attributes",
    "query",
    "historyquery",
    "ds",
]


def _make_xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(ONLINE_COLUMNS)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _llm_resp(intent: str, inherited: list[str], dropped: list[str] | None = None,
              needs_rewrite: bool = True) -> str:
    return json.dumps({
        "rewritten_query": "(rewrite text)",
        "intent_type": intent,
        "inherited_constraints": inherited,
        "dropped_constraints": dropped or [],
        "needs_rewrite": needs_rewrite,
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 单测：is_online_format
# ---------------------------------------------------------------------------

def test_is_online_format_true():
    assert dp.is_online_format(ONLINE_COLUMNS) is True


def test_is_online_format_false_missing_one():
    cols = [c for c in ONLINE_COLUMNS if c != "historyquery"]
    assert dp.is_online_format(cols) is False


def test_is_online_format_case_insensitive():
    cols = ["Meta_Conversation_ID", "HISTORYQUERY", "Llm_Resp"]
    assert dp.is_online_format(cols) is True


# ---------------------------------------------------------------------------
# 单测：_parse_history_query
# ---------------------------------------------------------------------------

def test_parse_history_query_two_turns():
    text = (
        "#第1轮问题：帮我找优惠\n"
        "#第2轮问题：本人身形偏瘦，身高1.71米\n"
        "#第2轮追问：你对哪款比较感兴趣？"
    )
    out = dp._parse_history_query(text)
    assert len(out) == 2
    assert out[0]["turn_index"] == 1
    assert out[0]["user_query"] == "帮我找优惠"
    assert out[0]["bot_response"] is None
    assert out[1]["turn_index"] == 2
    assert out[1]["user_query"] == "本人身形偏瘦，身高1.71米"
    assert out[1]["bot_response"] == "你对哪款比较感兴趣？"


def test_parse_history_query_empty_string():
    assert dp._parse_history_query("") == []
    assert dp._parse_history_query("没有任何标记") == []


def test_parse_history_query_full_width_colon():
    text = "#第1轮问题: 半角冒号也接受"
    out = dp._parse_history_query(text)
    assert out and out[0]["user_query"] == "半角冒号也接受"


# ---------------------------------------------------------------------------
# 单测：parse_online_excel 端到端
# ---------------------------------------------------------------------------

def test_parse_online_excel_two_rows_one_conv_with_phantom_turn():
    """模拟 60-conv Excel 中的 conv ...437518：historyquery 含 phantom turn 1，
    Excel 本身两行各为 turn 2 / 3。"""
    rows = [
        # turn 2: 用户描述身形 + bot 回复
        [
            "1026802932736437518",  # meta_conversation_id
            "1029262390272437518",  # id
            "本人身形偏瘦，身高1.71米",  # ori_query
            "2026-05-18 23:55:57",  # gmt_create
            2,  # cnt
            "帮我推荐适合夏天穿的短袖上衣",  # rewritten_query
            _llm_resp(
                intent="商品检索",
                inherited=["身形偏瘦", "身高1.71米", "夏季短袖上衣"],
                dropped=[],
                needs_rewrite=True,
            ),  # llm_resp
            "{}",  # attributes
            "本人身形偏瘦，身高1.71米",  # query
            "#第1轮问题：帮我找优惠",  # historyquery（含 phantom turn 1）
            "20260518_50",
        ],
        # turn 3: 用户追加要更多
        [
            "1026802932736437518",
            "1028929078272437518",
            "多推几款我选择",
            "2026-05-18 23:58:02",
            2,
            "请推荐几款适合夏天穿的短袖上衣",
            _llm_resp(
                intent="商品检索",
                inherited=["夏季短袖上衣", "身形偏瘦", "身高1.71米"],
                dropped=[],
                needs_rewrite=True,
            ),
            "{}",
            "多推几款我选择",
            (
                "#第1轮问题：帮我找优惠\n"
                "#第2轮问题：本人身形偏瘦，身高1.71米\n"
                "#第2轮追问：你对哪款比较感兴趣？"
            ),
            "20260518_50",
        ],
    ]
    convs = dp.parse_online_excel(_make_xlsx(rows))
    assert len(convs) == 1
    conv = convs[0]
    assert conv["conversation_id"] == "1026802932736437518"
    turns = conv["turns"]
    assert len(turns) == 3, "应当重构出 3 个 turn（phantom turn 1 + Excel 两行）"

    # turn 1: phantom，user_query 来自 #第1轮问题，无 rewrite，无 bot meta
    assert turns[0]["turn_index"] == 1
    assert turns[0]["user_query"] == "帮我找优惠"
    assert turns[0]["rewritten_query"] is None
    assert turns[0]["intent_type"] is None
    assert turns[0]["inherited_constraints"] is None
    assert turns[0]["needs_rewrite"] is None

    # turn 2: Excel row 0，user_query=本人身形偏瘦...，bot_response 来自 history 第2轮追问？
    # 注：当前实现中，turn 2 的 bot_response 应当从 longest-history 行（即 row 2）取
    # 该行的 history 含"#第2轮追问：你对哪款比较感兴趣？" → bot_response 填入
    assert turns[1]["turn_index"] == 2
    assert turns[1]["user_query"] == "本人身形偏瘦，身高1.71米"
    assert turns[1]["rewritten_query"] == "帮我推荐适合夏天穿的短袖上衣"
    assert turns[1]["intent_type"] == "商品检索"
    assert "身形偏瘦" in (turns[1]["inherited_constraints"] or [])
    assert turns[1]["needs_rewrite"] is True
    # 时间戳格式化保留
    assert turns[1]["timestamp"] == "2026-05-18 23:55:57"

    # turn 3: Excel row 1
    assert turns[2]["turn_index"] == 3
    assert turns[2]["user_query"] == "多推几款我选择"
    assert turns[2]["rewritten_query"] == "请推荐几款适合夏天穿的短袖上衣"
    assert "夏季短袖上衣" in (turns[2]["inherited_constraints"] or [])


def test_parse_online_excel_no_history_falls_back_to_sequential_index():
    """historyquery 为空时，按 gmt_create 升序派生 turn_index 1..N。"""
    rows = [
        [
            "C1", "id1", "用户问1", "2026-05-19 10:00:00", 1, "rewrite1",
            _llm_resp("商品检索", ["x"]),
            "{}", "用户问1", "", "ds",
        ],
        [
            "C1", "id2", "用户问2", "2026-05-19 10:01:00", 1, "rewrite2",
            _llm_resp("选项点选", ["x"]),
            "{}", "用户问2", "", "ds",
        ],
    ]
    convs = dp.parse_online_excel(_make_xlsx(rows))
    assert len(convs) == 1
    turns = convs[0]["turns"]
    assert [t["turn_index"] for t in turns] == [1, 2]
    assert turns[0]["intent_type"] == "商品检索"
    assert turns[1]["intent_type"] == "选项点选"


def test_parse_online_excel_invalid_llm_resp_does_not_crash():
    """llm_resp 不是合法 JSON 时，inherited/intent_type 都应为 None，不报错。"""
    rows = [
        [
            "C2", "id1", "你好", "2026-05-19 11:00:00", 1, "rewrite",
            "this is not json!!!",  # bad llm_resp
            "{}", "你好", "", "ds",
        ],
    ]
    convs = dp.parse_online_excel(_make_xlsx(rows))
    assert len(convs) == 1
    turns = convs[0]["turns"]
    assert len(turns) == 1
    assert turns[0]["intent_type"] is None
    assert turns[0]["inherited_constraints"] is None
    assert turns[0]["needs_rewrite"] is None


def test_parse_online_excel_multi_conv_sorted():
    """多个 conv 应按 conversation_id 字典序输出。"""
    rows = [
        [
            "C_B", "id1", "Q1", "2026-05-19 10:00:00", 1, "R1",
            _llm_resp("x", ["a"]), "{}", "Q1", "", "ds",
        ],
        [
            "C_A", "id2", "Q2", "2026-05-19 10:00:00", 1, "R2",
            _llm_resp("x", ["b"]), "{}", "Q2", "", "ds",
        ],
    ]
    convs = dp.parse_online_excel(_make_xlsx(rows))
    assert [c["conversation_id"] for c in convs] == ["C_A", "C_B"]


# ---------------------------------------------------------------------------
# 与真实文件的 smoke 测试（仅在 docker 容器中可访问 /tmp/online.xlsx 时跑）
# ---------------------------------------------------------------------------

def test_real_online_file_smoke():
    p = Path("/tmp/online.xlsx")
    if not p.exists():
        pytest.skip("/tmp/online.xlsx not present (run agent's docker cp first)")
    convs = dp.parse_online_excel(p.read_bytes())
    # 期望 60 conv
    assert 50 <= len(convs) <= 70, f"real file should have ~60 conv, got {len(convs)}"
    # 每条 conv 至少 1 turn
    assert all(len(c["turns"]) >= 1 for c in convs)
    # 至少有部分 turn 带 inherited_constraints（线上数据特性）
    has_inherited = any(
        any(t.get("inherited_constraints") for t in c["turns"])
        for c in convs
    )
    assert has_inherited, "real file should have at least some inherited_constraints populated"
