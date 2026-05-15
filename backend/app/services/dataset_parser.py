"""Dataset 上传 4 步向导通用解析 / 校验 / 转换工具。

工作流：
  1. parse_excel/csv/json(file_bytes) -> ParsedFile  (列 + 扁平行)
  2. infer_field_mapping(columns)     -> FieldMapping （列名启发式）
  3. validate(rows, mapping)          -> ValidationReport
  4. transform(rows, mapping)         -> list[嵌套 conversation payload]

设计原则：
- 内存内处理。任何持久化由调用方在 redis / Postgres 完成。
- 嵌套 JSON（含 turns）会被展平为行；扁平 JSON/CSV/Excel 直接当行处理。
- 启发式列名匹配大小写不敏感，并兼容下划线 / 中划线 / 中文。
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field, asdict
from typing import Any

from openpyxl import load_workbook


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


@dataclass
class ParsedFile:
    columns: list[str]
    rows: list[dict[str, Any]]
    format: str  # excel / csv / json


@dataclass
class FieldMapping:
    conversation_id: str | None = None
    turn_index: str | None = None
    user_query: str | None = None
    rewritten_query: str | None = None
    dimension_tag: str | None = None
    quality_label: str | None = None
    issue_type: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass
class ValidationIssue:
    severity: str  # error / warning / info
    code: str
    message: str
    count: int
    sample: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    issues: list[ValidationIssue]
    total_conversations: int
    total_turns: int
    is_passable: bool


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------


def parse_excel(file_bytes: bytes, sheet_name: int | str = 0) -> ParsedFile:
    """读 .xlsx 首 sheet（或指定 sheet），第一行作 header。空值统一转 ""。"""
    wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    if isinstance(sheet_name, int):
        ws = wb.worksheets[sheet_name]
    else:
        ws = wb[sheet_name]

    row_iter = ws.iter_rows(values_only=True)
    try:
        header_row = next(row_iter)
    except StopIteration:
        return ParsedFile(columns=[], rows=[], format="excel")

    columns = [
        str(c).strip() if c is not None else f"col_{i + 1}"
        for i, c in enumerate(header_row)
    ]

    rows: list[dict[str, Any]] = []
    for raw in row_iter:
        if raw is None or all(v is None or (isinstance(v, str) and not v.strip()) for v in raw):
            continue
        row = {columns[i]: ("" if raw[i] is None else raw[i]) for i in range(min(len(columns), len(raw)))}
        rows.append(row)

    return ParsedFile(columns=columns, rows=rows, format="excel")


def parse_csv(file_bytes: bytes) -> ParsedFile:
    """用 csv.DictReader 读 CSV；尝试 utf-8 / utf-8-sig / gbk 三种编码。"""
    text: str | None = None
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError as e:
            last_err = e
    if text is None:
        raise ValueError(f"unable to decode csv: {last_err}")

    reader = csv.DictReader(io.StringIO(text))
    columns = [c.strip() for c in (reader.fieldnames or [])]
    rows = [dict(r) for r in reader]
    return ParsedFile(columns=columns, rows=rows, format="csv")


def parse_json(file_bytes: bytes) -> ParsedFile:
    """JSON 支持两种格式：
    1. 嵌套（mock_multi_turn_queries_100.json 同款）：[{conversation_id, turns: [...]}]
       -> 展平为行：每个 turn 一行，附带 conversation 级元信息
    2. 扁平：[{conversation_id, turn_index, user_query, ...}]
    """
    text = file_bytes.decode("utf-8-sig", errors="replace")
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("expect json array at top level")

    if not data:
        return ParsedFile(columns=[], rows=[], format="json")

    # 判定嵌套：第一条含 turns list
    first = data[0]
    if isinstance(first, dict) and isinstance(first.get("turns"), list):
        rows: list[dict[str, Any]] = []
        for conv in data:
            conv_id = conv.get("conversation_id")
            for t in conv.get("turns", []):
                row = {
                    "conversation_id": conv_id,
                    "dimension_tag": conv.get("dimension_tag"),
                    "quality_label": conv.get("quality_label"),
                    "issue_type": conv.get("issue_type"),
                    "turn_index": t.get("turn_index"),
                    "user_query": t.get("user_query"),
                    "rewritten_query": t.get("rewritten_query"),
                    "timestamp": t.get("timestamp"),
                    "query_id": t.get("query_id"),
                }
                rows.append(row)
        cols = list(rows[0].keys()) if rows else [
            "conversation_id", "dimension_tag", "quality_label", "issue_type",
            "turn_index", "user_query", "rewritten_query", "timestamp", "query_id",
        ]
        return ParsedFile(columns=cols, rows=rows, format="json")

    # 扁平：用并集列名
    cols_set: list[str] = []
    seen: set[str] = set()
    for r in data:
        if not isinstance(r, dict):
            continue
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                cols_set.append(k)
    return ParsedFile(columns=cols_set, rows=[dict(r) for r in data], format="json")


# ---------------------------------------------------------------------------
# 启发式映射
# ---------------------------------------------------------------------------


# 关键字 -> 目标字段。匹配规则：lower-strip + 去掉下划线/中划线/空格 后整词或子串匹配。
_FIELD_ALIASES: dict[str, list[str]] = {
    "conversation_id": [
        "conversation_id", "conv_id", "conversationid", "convid",
        "session_id", "sessionid", "dialogue_id", "dialog_id",
        "会话id", "对话id", "session", "conversation",
    ],
    "turn_index": [
        "turn_index", "turn", "turnidx", "turnindex", "turnno", "turn_no",
        "round", "round_index", "step", "step_index",
        "轮次", "轮序", "轮数", "turn轮次", "顺序",
    ],
    "user_query": [
        "user_query", "userquery", "query", "user_input", "userinput",
        "input", "utterance", "user", "user_text", "raw_query", "原始query",
        "用户输入", "用户问题", "问题", "用户query",
    ],
    "rewritten_query": [
        "rewritten_query", "rewrittenquery", "rewrite", "rewrite_query",
        "rewritten", "bot_rewrite", "bot_query", "expanded_query",
        "改写query", "改写", "改写后", "重写query",
    ],
    "dimension_tag": [
        "dimension_tag", "dimension", "dim", "dim_tag", "category",
        "维度", "维度标签", "标签",
    ],
    "quality_label": [
        "quality_label", "quality", "label", "good_bad", "is_good",
        "质量", "质量标签", "正负样本", "good/bad",
    ],
    "issue_type": [
        "issue_type", "issue", "issuetype", "bug_type", "error_type",
        "问题类型", "问题",
    ],
}


def _normalize(col: str) -> str:
    return col.strip().lower().replace("_", "").replace("-", "").replace(" ", "")


def infer_field_mapping(columns: list[str]) -> FieldMapping:
    """按列名启发式推断映射。每个目标字段只匹配第一个命中的列。"""
    normalized = [(c, _normalize(c)) for c in columns]
    mapping = FieldMapping()
    used_cols: set[str] = set()

    for target, aliases in _FIELD_ALIASES.items():
        norm_aliases = [_normalize(a) for a in aliases]
        # 优先精确匹配（normalized 完全相等）
        chosen: str | None = None
        for col, n in normalized:
            if col in used_cols:
                continue
            if n in norm_aliases:
                chosen = col
                break
        # 次优：子串匹配（normalized 包含 alias 或 alias 包含 normalized）
        if chosen is None:
            for col, n in normalized:
                if col in used_cols:
                    continue
                for a in norm_aliases:
                    if not a:
                        continue
                    if a in n or n in a:
                        chosen = col
                        break
                if chosen:
                    break
        if chosen:
            setattr(mapping, target, chosen)
            used_cols.add(chosen)

    return mapping


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------


_REQUIRED_FIELDS = ("conversation_id", "turn_index", "user_query")
_MAX_SAMPLE = 5


def _to_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None


def _to_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return str(v).strip()


def validate(rows: list[dict[str, Any]], mapping: FieldMapping) -> ValidationReport:
    issues: list[ValidationIssue] = []

    # 1. 检查必填字段映射存在
    missing_mappings = [f for f in _REQUIRED_FIELDS if not getattr(mapping, f)]
    if missing_mappings:
        issues.append(
            ValidationIssue(
                severity="error",
                code="missing_field_mapping",
                message=f"必填字段未映射：{', '.join(missing_mappings)}",
                count=len(missing_mappings),
                sample=missing_mappings,
            )
        )
        # 直接返回，后续校验依赖映射
        return ValidationReport(issues=issues, total_conversations=0, total_turns=0, is_passable=False)

    cid_col = mapping.conversation_id
    tidx_col = mapping.turn_index
    uq_col = mapping.user_query

    empty_conv: list[str] = []
    empty_query: list[str] = []
    invalid_turn_idx: list[str] = []

    # 按 conversation_id 聚合
    conv_turns: dict[str, list[int]] = {}
    conv_seen_pairs: dict[tuple[str, int], int] = {}
    dup_pairs: list[str] = []

    for i, row in enumerate(rows):
        conv_id = _to_str(row.get(cid_col))
        tidx = _to_int(row.get(tidx_col))
        uq = _to_str(row.get(uq_col))

        if not conv_id:
            if len(empty_conv) < _MAX_SAMPLE:
                empty_conv.append(f"row#{i + 2}")
            continue
        if tidx is None:
            if len(invalid_turn_idx) < _MAX_SAMPLE:
                invalid_turn_idx.append(f"row#{i + 2} value={row.get(tidx_col)!r}")
            continue
        if not uq:
            if len(empty_query) < _MAX_SAMPLE:
                empty_query.append(f"{conv_id}/turn#{tidx}")

        key = (conv_id, tidx)
        if key in conv_seen_pairs:
            if len(dup_pairs) < _MAX_SAMPLE:
                dup_pairs.append(f"{conv_id}/turn#{tidx}")
            continue
        conv_seen_pairs[key] = i
        conv_turns.setdefault(conv_id, []).append(tidx)

    if empty_conv:
        issues.append(ValidationIssue(
            severity="error", code="empty_conversation_id",
            message="存在空 conversation_id 的行", count=len(empty_conv), sample=empty_conv,
        ))
    if invalid_turn_idx:
        issues.append(ValidationIssue(
            severity="error", code="invalid_turn_index",
            message="turn_index 无法解析为整数", count=len(invalid_turn_idx), sample=invalid_turn_idx,
        ))
    if empty_query:
        issues.append(ValidationIssue(
            severity="error", code="empty_user_query",
            message="user_query 为空", count=len(empty_query), sample=empty_query,
        ))
    if dup_pairs:
        issues.append(ValidationIssue(
            severity="warning", code="duplicate_pair",
            message="重复 (conversation_id, turn_index) 已被忽略", count=len(dup_pairs), sample=dup_pairs,
        ))

    # 连续性 / 长度
    turn_gaps: list[str] = []
    long_convs: list[str] = []
    for cid, idxs in conv_turns.items():
        idxs_sorted = sorted(idxs)
        # 期望 1..N
        if idxs_sorted[0] != 1 or any(b - a != 1 for a, b in zip(idxs_sorted, idxs_sorted[1:])):
            if len(turn_gaps) < _MAX_SAMPLE:
                turn_gaps.append(f"{cid} turns={idxs_sorted}")
        if len(idxs_sorted) > 20:
            if len(long_convs) < _MAX_SAMPLE:
                long_convs.append(f"{cid} ({len(idxs_sorted)} turns)")

    if turn_gaps:
        issues.append(ValidationIssue(
            severity="warning", code="turn_index_gap",
            message="同一 conversation 的 turn_index 不连续或未从 1 开始",
            count=len(turn_gaps), sample=turn_gaps,
        ))
    if long_convs:
        issues.append(ValidationIssue(
            severity="warning", code="overlong_conversation",
            message="单个 conversation 轮次过多（> 20）",
            count=len(long_convs), sample=long_convs,
        ))

    # info：首轮无 rewritten_query 属正常
    if mapping.rewritten_query:
        first_no_rewrite = 0
        for row in rows:
            if _to_int(row.get(tidx_col)) == 1:
                rw = _to_str(row.get(mapping.rewritten_query))
                if not rw:
                    first_no_rewrite += 1
        if first_no_rewrite > 0:
            issues.append(ValidationIssue(
                severity="info", code="first_turn_no_rewrite",
                message="首轮 rewritten_query 为空（正常）",
                count=first_no_rewrite, sample=[],
            ))

    is_passable = not any(i.severity == "error" for i in issues)
    return ValidationReport(
        issues=issues,
        total_conversations=len(conv_turns),
        total_turns=len(conv_seen_pairs),
        is_passable=is_passable,
    )


# ---------------------------------------------------------------------------
# 转换为入库格式
# ---------------------------------------------------------------------------


def transform(rows: list[dict[str, Any]], mapping: FieldMapping) -> list[dict[str, Any]]:
    """按 (conversation_id) 分组拼装为现有 datasets.upload 接受的嵌套格式。"""
    if not all(getattr(mapping, f) for f in _REQUIRED_FIELDS):
        raise ValueError("mapping missing required fields")

    cid_col = mapping.conversation_id
    tidx_col = mapping.turn_index
    uq_col = mapping.user_query
    rw_col = mapping.rewritten_query
    dim_col = mapping.dimension_tag
    ql_col = mapping.quality_label
    iss_col = mapping.issue_type

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        cid = _to_str(row.get(cid_col))
        tidx = _to_int(row.get(tidx_col))
        if not cid or tidx is None:
            continue
        uq = _to_str(row.get(uq_col))
        if not uq:
            continue
        conv = grouped.get(cid)
        if conv is None:
            conv = {
                "conversation_id": cid,
                "dimension_tag": _to_str(row.get(dim_col)) if dim_col else None,
                "quality_label": _to_str(row.get(ql_col)) if ql_col else None,
                "issue_type": _to_str(row.get(iss_col)) if iss_col else None,
                "turns": [],
                "_turn_keys": set(),
            }
            # 空字符串当 None
            for k in ("dimension_tag", "quality_label", "issue_type"):
                if conv[k] == "":
                    conv[k] = None
            grouped[cid] = conv

        if tidx in conv["_turn_keys"]:
            continue
        conv["_turn_keys"].add(tidx)

        turn = {
            "turn_index": tidx,
            "user_query": uq,
        }
        if rw_col:
            rw = _to_str(row.get(rw_col))
            turn["rewritten_query"] = rw or None
        ts = row.get("timestamp")
        if ts:
            turn["timestamp"] = _to_str(ts)
        conv["turns"].append(turn)

    out: list[dict[str, Any]] = []
    for conv in grouped.values():
        conv["turns"].sort(key=lambda t: t["turn_index"])
        conv["total_turns"] = len(conv["turns"])
        conv.pop("_turn_keys", None)
        out.append(conv)
    return out


# ---------------------------------------------------------------------------
# 顶层入口
# ---------------------------------------------------------------------------


def parse_any(file_bytes: bytes, filename: str, format_hint: str | None = None) -> ParsedFile:
    """按文件扩展名 / format hint 调度到具体 parser。"""
    fmt = (format_hint or "").lower().strip()
    name = (filename or "").lower()
    if fmt:
        if fmt in ("excel", "xlsx"):
            return parse_excel(file_bytes)
        if fmt == "csv":
            return parse_csv(file_bytes)
        if fmt == "json":
            return parse_json(file_bytes)
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return parse_excel(file_bytes)
    if name.endswith(".csv"):
        return parse_csv(file_bytes)
    if name.endswith(".json"):
        return parse_json(file_bytes)
    # 兜底尝试 JSON
    return parse_json(file_bytes)
