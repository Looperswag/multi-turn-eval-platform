"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type BadcaseListResponse,
  type BadcaseTag,
  type CaseFullDetail,
} from "@/lib/api";

const DIM_CODES = ["dim1", "dim2", "dim3", "dim4", "dim5", "dim6"] as const;
const DIM_LABELS: Record<string, string> = {
  dim1: "改写忠实性",
  dim2: "跨轮记忆保留",
  dim3: "意图边界识别",
  dim4: "指代消解准确性",
  dim5: "重复请求处理",
  dim6: "用户纠错响应",
};

function scoreColor(s: number | null | undefined): string {
  if (s == null) return "text-ink-3";
  if (s < 0.6) return "text-tomato";
  if (s < 0.8) return "text-amber";
  return "text-moss";
}

function scoreBadge(s: number | null | undefined): string {
  if (s == null) return "badge badge-neutral";
  if (s < 0.6) return "badge badge-fail";
  if (s < 0.8) return "badge badge-warn";
  return "badge badge-pass";
}

export default function BadcasesPage({ params }: { params: { id: string } }) {
  const runId = parseInt(params.id, 10);
  const searchParams = useSearchParams();

  // ===== filters =====
  const [dimFilter, setDimFilter] = useState<string | null>(null); // null = weighted
  const [scoreMax, setScoreMax] = useState<number>(0.6);
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [confirmedState, setConfirmedState] = useState<"all" | "confirmed" | "pending">("all");
  const [offset, setOffset] = useState(0);
  const LIMIT = 50;

  // ===== data =====
  const [data, setData] = useState<BadcaseListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // drawer
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);

  // P0 修复（B.2 reviewer）：从维度页跳来 `/badcases?case_id=X` 时自动打开 Drawer
  useEffect(() => {
    const initCaseId = searchParams.get("case_id");
    if (initCaseId) {
      const n = parseInt(initCaseId, 10);
      if (!Number.isNaN(n)) setSelectedCaseId(n);
    }
  }, [searchParams]);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({
      score_max: scoreMax.toFixed(2),
      limit: String(LIMIT),
      offset: String(offset),
    });
    if (dimFilter) params.append("dim_filter", dimFilter);
    if (tagFilter) params.append("tag_filter", tagFilter);
    if (confirmedState !== "all") {
      params.append("confirmed", confirmedState === "confirmed" ? "true" : "false");
    }
    try {
      const resp = await api<BadcaseListResponse>(
        `/api/eval-runs/${runId}/badcases?${params.toString()}`
      );
      setData(resp);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setLoading(false);
    }
  }, [runId, dimFilter, scoreMax, tagFilter, confirmedState, offset]);

  useEffect(() => {
    reload();
  }, [reload]);

  // 过滤变化时重置 offset
  useEffect(() => {
    setOffset(0);
  }, [dimFilter, scoreMax, tagFilter, confirmedState]);

  const stats = data?.stats;
  const facets = data?.tag_facets ?? [];
  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="max-w-[1800px]">
      <div className="mb-2 text-ink-3 text-xs">
        <Link href="/eval-runs" className="text-ink-2 hover:text-ink">
          评测任务
        </Link>{" "}
        /{" "}
        <Link href={`/eval-runs/${runId}`} className="text-ink-2 hover:text-ink">
          #{runId}
        </Link>{" "}
        / <span className="ml-1">Badcase 钻取</span>
      </div>
      <div className="flex items-baseline justify-between mb-6">
        <h1 className="font-display text-4xl font-medium tracking-tight">Badcase 钻取</h1>
        <div className="text-sm text-ink-3">
          {loading ? "加载中…" : `共 ${total} 条`}
        </div>
      </div>

      {error && (
        <div className="border border-tomato/30 bg-tomato/5 rounded p-3 text-sm text-tomato mb-4">
          {error}
        </div>
      )}

      <div className="grid grid-cols-[240px_minmax(0,1fr)] gap-6">
        {/* ============ 左栏：过滤面板 ============ */}
        <aside className="space-y-5 sticky top-6 self-start">
          {/* 统计卡片 */}
          <div className="bg-card border border-[var(--rule)] rounded p-4">
            <div className="uppercase-label text-ink-3 mb-3">统计</div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <StatBlock label="全部" value={stats?.total_cases ?? 0} />
              <StatBlock label="< 阈值" value={stats?.below_threshold ?? 0} tone="tomato" />
              <StatBlock label="已打标" value={stats?.tagged ?? 0} tone="info" />
              <StatBlock label="已复审" value={stats?.confirmed ?? 0} tone="moss" />
            </div>
          </div>

          {/* 维度筛选 */}
          <div className="bg-card border border-[var(--rule)] rounded p-4">
            <div className="uppercase-label text-ink-3 mb-3">过滤维度</div>
            <div className="space-y-1.5 text-sm">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="dim"
                  checked={dimFilter === null}
                  onChange={() => setDimFilter(null)}
                />
                <span>按加权总分</span>
              </label>
              {DIM_CODES.map((d) => (
                <label key={d} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="dim"
                    checked={dimFilter === d}
                    onChange={() => setDimFilter(d)}
                  />
                  <span className="font-mono-feat text-xs">{d}</span>
                  <span className="text-ink-2 text-xs">{DIM_LABELS[d]}</span>
                </label>
              ))}
            </div>
          </div>

          {/* 阈值 */}
          <div className="bg-card border border-[var(--rule)] rounded p-4">
            <div className="uppercase-label text-ink-3 mb-3 flex justify-between">
              <span>阈值 (≤)</span>
              <span className="font-mono-feat text-ink tabular-nums normal-case tracking-normal">
                {scoreMax.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={scoreMax}
              onChange={(e) => setScoreMax(parseFloat(e.target.value))}
              className="w-full accent-tomato"
            />
            <div className="flex justify-between text-[10px] text-ink-3 font-mono-feat mt-1">
              <span>0.00</span>
              <span>0.60</span>
              <span>1.00</span>
            </div>
          </div>

          {/* Tag facet */}
          <div className="bg-card border border-[var(--rule)] rounded p-4">
            <div className="uppercase-label text-ink-3 mb-3">Tag 过滤</div>
            {facets.length === 0 ? (
              <div className="text-xs text-ink-3">暂无 tag</div>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                <button
                  onClick={() => setTagFilter(null)}
                  className={`px-2 py-1 text-xs rounded border transition-colors ${
                    tagFilter === null
                      ? "bg-moss text-white border-moss"
                      : "border-[var(--rule-strong)] hover:bg-[var(--rule)]"
                  }`}
                >
                  全部
                </button>
                {facets.map((f) => (
                  <button
                    key={f.tag}
                    onClick={() => setTagFilter(f.tag)}
                    className={`px-2 py-1 text-xs rounded border transition-colors ${
                      tagFilter === f.tag
                        ? "bg-moss text-white border-moss"
                        : "border-[var(--rule-strong)] hover:bg-[var(--rule)]"
                    }`}
                    title={`${f.count} 条`}
                  >
                    {f.tag} <span className="opacity-70">·{f.count}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 复审状态 */}
          <div className="bg-card border border-[var(--rule)] rounded p-4">
            <div className="uppercase-label text-ink-3 mb-3">复审状态</div>
            <div className="grid grid-cols-3 gap-1 text-xs">
              {(
                [
                  ["all", "全部"],
                  ["confirmed", "已复审"],
                  ["pending", "未复审"],
                ] as const
              ).map(([v, label]) => (
                <button
                  key={v}
                  onClick={() => setConfirmedState(v)}
                  className={`px-2 py-1.5 border rounded transition-colors ${
                    confirmedState === v
                      ? "bg-moss text-white border-moss"
                      : "border-[var(--rule-strong)] hover:bg-[var(--rule)]"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </aside>

        {/* ============ 中央：表格 ============ */}
        <section className="bg-card border border-[var(--rule)] rounded overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--rule)] flex items-center justify-between">
            <div className="uppercase-label text-ink-3">
              Badcase 列表 ·{" "}
              {dimFilter ? `${dimFilter} · ${DIM_LABELS[dimFilter]}` : "按加权总分"}
              {" · "}阈值 ≤ {scoreMax.toFixed(2)}
            </div>
            <div className="text-xs text-ink-3 font-mono-feat tabular-nums">
              {total > 0
                ? `${offset + 1}-${Math.min(offset + items.length, total)} / ${total}`
                : "0"}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-ink-3 uppercase-label border-b border-[var(--rule)] bg-[var(--bg)]">
                  <th className="text-left px-3 py-2.5">case</th>
                  <th className="text-left px-2 py-2.5">conv id</th>
                  <th className="text-right px-2 py-2.5">加权</th>
                  <th className="text-left px-2 py-2.5">最低维</th>
                  {DIM_CODES.map((d) => (
                    <th key={d} className="text-center px-1 py-2.5 font-mono-feat">
                      {d}
                    </th>
                  ))}
                  <th className="text-left px-2 py-2.5">tags</th>
                  <th className="text-left px-2 py-2.5">预览</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 && !loading && (
                  <tr>
                    <td colSpan={12} className="px-4 py-12 text-center text-ink-3 text-sm">
                      没有符合条件的 badcase。
                    </td>
                  </tr>
                )}
                {items.map((it) => (
                  <tr
                    key={it.case_id}
                    onClick={() => setSelectedCaseId(it.case_id)}
                    className={`border-b border-[var(--rule)] last:border-0 cursor-pointer transition-colors ${
                      selectedCaseId === it.case_id
                        ? "bg-[var(--moss-bg)]"
                        : "hover:bg-[var(--rule)]"
                    }`}
                  >
                    <td className="px-3 py-2 font-mono-feat text-xs text-ink-2">
                      #{it.case_id}
                    </td>
                    <td className="px-2 py-2 font-mono-feat text-xs text-ink">
                      {it.conversation_id_src}
                    </td>
                    <td
                      className={`px-2 py-2 text-right font-mono-feat tabular-nums font-medium ${scoreColor(it.weighted_score)}`}
                    >
                      {it.weighted_score == null ? "—" : it.weighted_score.toFixed(3)}
                    </td>
                    <td className="px-2 py-2 text-xs text-ink-2">
                      {it.lowest_dim_code ? (
                        <span className="font-mono-feat">{it.lowest_dim_code}</span>
                      ) : (
                        "—"
                      )}
                    </td>
                    {DIM_CODES.map((d) => {
                      const v = it.dim_scores[d];
                      return (
                        <td key={d} className="px-1 py-2 text-center">
                          <span
                            className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-mono-feat ${scoreBadge(v)}`}
                          >
                            {v == null ? "—" : v.toFixed(2)}
                          </span>
                        </td>
                      );
                    })}
                    <td className="px-2 py-2">
                      <div className="flex flex-wrap gap-1">
                        {it.tags.length === 0 ? (
                          <span className="text-ink-3 text-xs">—</span>
                        ) : (
                          it.tags.slice(0, 3).map((t) => (
                            <span
                              key={t.id}
                              className={`badge text-[10px] ${
                                t.is_confirmed ? "badge-pass" : "badge-info"
                              }`}
                            >
                              {t.tag}
                            </span>
                          ))
                        )}
                        {it.tags.length > 3 && (
                          <span className="text-ink-3 text-[10px]">
                            +{it.tags.length - 3}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-2 py-2 text-xs text-ink-2 max-w-[280px]">
                      <div className="truncate">{it.preview_query || "—"}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* 分页 */}
          {total > LIMIT && (
            <div className="px-4 py-3 border-t border-[var(--rule)] flex items-center justify-between text-sm">
              <button
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - LIMIT))}
                className="px-3 py-1 border border-[var(--rule-strong)] rounded disabled:opacity-40 hover:bg-[var(--rule)]"
              >
                ← 上一页
              </button>
              <span className="text-ink-3 text-xs">
                第 {Math.floor(offset / LIMIT) + 1} / {Math.ceil(total / LIMIT)} 页
              </span>
              <button
                disabled={offset + LIMIT >= total}
                onClick={() => setOffset(offset + LIMIT)}
                className="px-3 py-1 border border-[var(--rule-strong)] rounded disabled:opacity-40 hover:bg-[var(--rule)]"
              >
                下一页 →
              </button>
            </div>
          )}
        </section>
      </div>

      {/* ============ 右侧 Drawer ============ */}
      {selectedCaseId !== null && (
        <CaseDrawer
          runId={runId}
          caseId={selectedCaseId}
          onClose={() => setSelectedCaseId(null)}
          onTagChange={reload}
        />
      )}
    </div>
  );
}

function StatBlock({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "tomato" | "moss" | "info";
}) {
  const color =
    tone === "tomato"
      ? "text-tomato"
      : tone === "moss"
        ? "text-moss"
        : tone === "info"
          ? "text-ink-blue"
          : "text-ink";
  return (
    <div>
      <div className="text-[10px] uppercase-label text-ink-3">{label}</div>
      <div className={`font-display text-2xl font-medium tabular-nums ${color}`}>
        {value}
      </div>
    </div>
  );
}

// ====================================================================
// Drawer
// ====================================================================

function CaseDrawer({
  runId,
  caseId,
  onClose,
  onTagChange,
}: {
  runId: number;
  caseId: number;
  onClose: () => void;
  onTagChange: () => void;
}) {
  const [detail, setDetail] = useState<CaseFullDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const fetchDetail = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const d = await api<CaseFullDetail>(`/api/eval-runs/${runId}/cases/${caseId}/full`);
      setDetail(d);
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setLoading(false);
    }
  }, [runId, caseId]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  // esc 关闭
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  return (
    <>
      {/* mask */}
      <div
        onClick={onClose}
        className="fixed inset-0 bg-ink/30 z-40"
        aria-hidden="true"
      />
      {/* drawer */}
      <div
        role="dialog"
        aria-modal="true"
        className="fixed top-0 right-0 bottom-0 w-[540px] bg-card border-l border-[var(--rule-strong)] z-50 overflow-y-auto shadow-[-8px_0_24px_rgba(0,0,0,0.08)]"
      >
        <div className="sticky top-0 bg-card border-b border-[var(--rule)] px-5 py-3 flex items-center justify-between z-10">
          <div className="uppercase-label text-ink-3">Case 详情</div>
          <button
            onClick={onClose}
            aria-label="关闭"
            className="text-ink-3 hover:text-ink text-xl leading-none w-6 h-6 flex items-center justify-center"
          >
            ×
          </button>
        </div>

        {err && (
          <div className="m-5 border border-tomato/30 bg-tomato/5 rounded p-3 text-sm text-tomato">
            {err}
          </div>
        )}
        {loading && <div className="px-5 py-8 text-sm text-ink-3">加载中…</div>}

        {detail && (
          <div className="p-5 space-y-6">
            {/* 头部 */}
            <div>
              <div className="flex items-baseline justify-between gap-3">
                <div>
                  <div className="font-display text-2xl font-medium">
                    {detail.conversation_id_src}
                  </div>
                  <div className="text-xs text-ink-3 mt-1 font-mono-feat">
                    case #{detail.case_id} · conv #{detail.conversation_id}
                  </div>
                </div>
                <div
                  className={`font-display text-3xl tabular-nums ${scoreColor(detail.weighted_score)}`}
                >
                  {detail.weighted_score == null
                    ? "—"
                    : detail.weighted_score.toFixed(3)}
                </div>
              </div>
              <div className="flex flex-wrap gap-2 mt-2 text-xs">
                {detail.lowest_dim_code && (
                  <span className="badge badge-warn">
                    最低维 {detail.lowest_dim_code}
                  </span>
                )}
                {detail.conversation_meta.quality_label && (
                  <span className="badge badge-neutral">
                    {detail.conversation_meta.quality_label}
                  </span>
                )}
                {detail.conversation_meta.dimension_tag && (
                  <span className="badge badge-info">
                    {detail.conversation_meta.dimension_tag}
                  </span>
                )}
                {detail.conversation_meta.issue_type && (
                  <span className="badge badge-fail">
                    {detail.conversation_meta.issue_type}
                  </span>
                )}
              </div>
            </div>

            {/* 6 维 bar */}
            <DimMiniBars dim_scores={detail.dim_scores} />

            {/* 完整对话 */}
            <div>
              <div className="uppercase-label text-ink-3 mb-3">
                完整对话 · {detail.turns.length} 轮
              </div>
              <div className="space-y-4">
                {detail.turns.map((t) => (
                  <div key={t.turn_index}>
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="uppercase-label text-ink-3 text-[10px]">
                        Turn {t.turn_index}
                      </div>
                      {t.timestamp && (
                        <div className="text-[10px] text-ink-3 font-mono-feat">
                          {t.timestamp}
                        </div>
                      )}
                    </div>
                    <div className="space-y-1.5">
                      <div className="bg-[var(--bg)] border border-[var(--rule)] rounded p-2.5">
                        <div className="uppercase-label text-ink-3 text-[9px] mb-1">
                          User
                        </div>
                        <div className="text-sm whitespace-pre-wrap">
                          {t.user_query}
                        </div>
                      </div>
                      {t.rewritten_query ? (
                        <div className="bg-[var(--moss-bg)] border border-moss/30 rounded p-2.5">
                          <div className="uppercase-label text-ink-3 text-[9px] mb-1">
                            Bot 改写
                          </div>
                          <div className="text-sm whitespace-pre-wrap text-ink">
                            {t.rewritten_query}
                          </div>
                        </div>
                      ) : (
                        <div className="text-[11px] text-ink-3 italic px-1">
                          （首轮无需改写 / Bot 未生成）
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Raw judge JSON 折叠 */}
            <div>
              <div className="uppercase-label text-ink-3 mb-3">
                Raw Judge Response
              </div>
              <div className="space-y-2">
                {DIM_CODES.map((d) => {
                  const block = (detail.dim_results_full as Record<string, unknown>)[d];
                  if (block === undefined) return null;
                  return (
                    <RawDimBlock
                      key={d}
                      dim={d}
                      label={DIM_LABELS[d]}
                      score={detail.dim_scores[d]}
                      data={block}
                    />
                  );
                })}
              </div>
            </div>

            {/* Tag 管理（B.1 reviewer P1：key={caseId} 保证切换 case 时草稿状态被清空） */}
            <TagPanel
              key={detail.case_id}
              caseId={detail.case_id}
              tags={detail.tags}
              onChanged={() => {
                fetchDetail();
                onTagChange();
              }}
            />
          </div>
        )}
      </div>
    </>
  );
}

function DimMiniBars({
  dim_scores,
}: {
  dim_scores: Record<string, number | null>;
}) {
  return (
    <div>
      <div className="uppercase-label text-ink-3 mb-2">六维分数</div>
      <div className="space-y-1.5">
        {DIM_CODES.map((d) => {
          const v = dim_scores[d];
          const pct = v == null ? 0 : Math.max(0, Math.min(1, v)) * 100;
          const color = v == null ? "var(--ink-4)" : v < 0.6 ? "var(--tomato)" : v < 0.8 ? "var(--amber)" : "var(--moss)";
          return (
            <div key={d} className="flex items-center gap-2 text-xs">
              <div className="w-12 font-mono-feat text-ink-2">{d}</div>
              <div className="flex-1 h-3 bg-[var(--rule)] rounded-sm overflow-hidden">
                <div
                  className="h-full transition-all"
                  style={{ width: `${pct}%`, background: color }}
                />
              </div>
              <div
                className={`w-10 text-right font-mono-feat tabular-nums ${scoreColor(v)}`}
              >
                {v == null ? "—" : v.toFixed(2)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RawDimBlock({
  dim,
  label,
  score,
  data,
}: {
  dim: string;
  label: string;
  score: number | null | undefined;
  data: unknown;
}) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const json = useMemo(() => JSON.stringify(data, null, 2), [data]);
  const lines = json.split("\n");

  async function copy() {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  }

  return (
    <div className="border border-[var(--rule)] rounded overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-3 py-2 flex items-center justify-between text-sm hover:bg-[var(--rule)] transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-ink-3">{open ? "▾" : "▸"}</span>
          <span className="font-mono-feat text-xs text-ink-2">{dim}</span>
          <span className="text-ink">{label}</span>
        </div>
        <span
          className={`badge text-[10px] ${scoreBadge(score ?? null)}`}
        >
          {score == null ? "—" : score.toFixed(2)}
        </span>
      </button>
      {open && (
        <div className="border-t border-[var(--rule)] bg-[var(--bg)]">
          <div className="flex items-center justify-end px-2 py-1 border-b border-[var(--rule)]">
            <button
              onClick={copy}
              className="text-[10px] text-ink-3 hover:text-ink px-2 py-0.5"
            >
              {copied ? "已复制" : "复制"}
            </button>
          </div>
          <pre className="text-[10px] font-mono-feat leading-snug max-h-72 overflow-auto">
            <table className="w-full">
              <tbody>
                {lines.map((line, i) => (
                  <tr key={i}>
                    <td className="text-ink-4 text-right pr-2 pl-2 select-none tabular-nums w-10 border-r border-[var(--rule)]">
                      {i + 1}
                    </td>
                    <td className="pl-2 whitespace-pre">{line}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </pre>
        </div>
      )}
    </div>
  );
}

function TagPanel({
  caseId,
  tags,
  onChanged,
}: {
  caseId: number;
  tags: BadcaseTag[];
  onChanged: () => void;
}) {
  const [newTag, setNewTag] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function add() {
    const tag = newTag.trim();
    if (!tag) return;
    setBusy(true);
    setErr(null);
    try {
      await api(`/api/badcases/${caseId}/tag`, {
        method: "POST",
        body: JSON.stringify({ tag, notes: notes.trim() || null }),
      });
      setNewTag("");
      setNotes("");
      onChanged();
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }

  async function toggleConfirm(t: BadcaseTag) {
    await api(`/api/badcases/tags/${t.id}/confirm`, {
      method: "POST",
      body: JSON.stringify({ is_confirmed: !t.is_confirmed }),
    });
    onChanged();
  }

  async function toggleRegression(t: BadcaseTag) {
    await api(`/api/badcases/tags/${t.id}/regression`, {
      method: "POST",
      body: JSON.stringify({ added: !t.added_to_regression }),
    });
    onChanged();
  }

  async function remove(t: BadcaseTag) {
    await api(`/api/badcases/tags/${t.id}`, { method: "DELETE" });
    onChanged();
  }

  return (
    <div>
      <div className="uppercase-label text-ink-3 mb-3">打标签</div>

      {/* 已有 tag 列表 */}
      {tags.length === 0 ? (
        <div className="text-xs text-ink-3 mb-3">暂无 tag。</div>
      ) : (
        <ul className="space-y-2 mb-4">
          {tags.map((t) => (
            <li
              key={t.id}
              className="border border-[var(--rule)] rounded p-2.5 text-sm bg-card-2"
            >
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className={`badge text-xs ${t.is_confirmed ? "badge-pass" : "badge-info"}`}
                  >
                    {t.tag}
                  </span>
                  {t.added_to_regression && (
                    <span className="badge badge-warn text-[10px]">→ 回归集</span>
                  )}
                </div>
                <button
                  onClick={() => remove(t)}
                  aria-label="删除"
                  className="text-ink-3 hover:text-tomato text-base leading-none px-1"
                >
                  ×
                </button>
              </div>
              {t.notes && (
                <div className="text-xs text-ink-2 mb-1.5 whitespace-pre-wrap">
                  {t.notes}
                </div>
              )}
              <div className="flex flex-wrap gap-1.5 text-[11px]">
                <button
                  onClick={() => toggleConfirm(t)}
                  className={`px-2 py-0.5 rounded border transition-colors ${
                    t.is_confirmed
                      ? "border-moss bg-[var(--moss-bg)] text-moss"
                      : "border-[var(--rule-strong)] hover:bg-[var(--rule)]"
                  }`}
                >
                  {t.is_confirmed ? "✓ 已复审" : "标记复审"}
                </button>
                <button
                  onClick={() => toggleRegression(t)}
                  className={`px-2 py-0.5 rounded border transition-colors ${
                    t.added_to_regression
                      ? "border-amber bg-[var(--amber-bg)] text-amber"
                      : "border-[var(--rule-strong)] hover:bg-[var(--rule)]"
                  }`}
                >
                  {t.added_to_regression ? "✓ 回归集" : "→ 回归集"}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* 新增 tag */}
      <div className="border border-[var(--rule)] rounded p-3 bg-card-2 space-y-2">
        <input
          value={newTag}
          onChange={(e) => setNewTag(e.target.value)}
          placeholder="新标签（如 抽指代失败 / 记忆遗失）"
          className="w-full px-3 py-1.5 border border-[var(--rule-strong)] rounded bg-card-2 text-sm"
        />
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder="备注（可选）"
          className="w-full px-3 py-1.5 border border-[var(--rule-strong)] rounded bg-card-2 text-sm resize-none"
        />
        {err && <div className="text-xs text-tomato">{err}</div>}
        <div className="flex justify-end">
          <button
            onClick={add}
            disabled={busy || !newTag.trim()}
            className="px-3 py-1.5 bg-moss text-white text-sm rounded hover:opacity-90 disabled:opacity-40"
          >
            {busy ? "提交…" : "添加 tag"}
          </button>
        </div>
      </div>

      {/* 回归集占位 */}
      <div className="mt-4 border border-dashed border-[var(--rule-strong)] rounded p-3 text-xs text-ink-3">
        <div className="flex items-center justify-between">
          <span>关联到回归集</span>
          <button
            disabled
            className="px-2 py-1 border border-[var(--rule)] rounded opacity-50 cursor-not-allowed"
          >
            待启用
          </button>
        </div>
        <div className="mt-1.5">回归集管理在 C 周提供。</div>
      </div>
    </div>
  );
}
