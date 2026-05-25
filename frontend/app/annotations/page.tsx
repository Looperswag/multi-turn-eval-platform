"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  api,
  type AnnotationOut,
  type EvalRun,
  type QueueItem,
  type QueueResponse,
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

type Choice = "0" | "0.5" | "1" | "na" | "skip";

function scoreBadgeClass(score: number | null, applicable: boolean | null): string {
  if (applicable === false) return "badge badge-neutral";
  if (score === null) return "badge badge-neutral";
  if (score >= 0.9) return "badge badge-pass";
  if (score >= 0.4) return "badge badge-warn";
  return "badge badge-fail";
}

function scoreLabel(score: number | null, applicable: boolean | null): string {
  if (applicable === false) return "N/A";
  if (score === null) return "—";
  if (score === 0) return "0";
  if (score === 0.5) return "0.5";
  if (score === 1) return "1";
  return score.toFixed(2);
}

export default function AnnotationWorkbenchPage() {
  // 顶部筛选
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [runId, setRunId] = useState<number>(0);
  const [dimCode, setDimCode] = useState<string>("dim1");
  const [annotator, setAnnotator] = useState<string>("");
  const [includeDone, setIncludeDone] = useState(false);

  // 数据
  const [queue, setQueue] = useState<QueueResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 当前选中 case
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);

  // 标注表单
  const [choice, setChoice] = useState<Choice>("1");
  const [comment, setComment] = useState("");
  const [evidence, setEvidence] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitMsg, setSubmitMsg] = useState<{ tone: "ok" | "err"; text: string } | null>(null);

  // 折叠 raw response
  const [rawOpen, setRawOpen] = useState(false);

  // 拉 eval_runs
  useEffect(() => {
    api<EvalRun[]>("/api/eval-runs")
      .then((all) => {
        const ok = all.filter((r) => r.status === "success" || r.status === "partial");
        setRuns(ok);
        if (ok.length > 0 && !runId) setRunId(ok[0].id);
      })
      .catch((e) => setError(String((e as Error).message)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 拉队列
  function reload() {
    if (!runId) return;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({
      run_id: String(runId),
      dimension_code: dimCode,
    });
    if (annotator.trim()) params.append("annotator", annotator.trim());
    if (includeDone) params.append("include_done", "true");
    api<QueueResponse>(`/api/annotations/queue?${params.toString()}`)
      .then((q) => {
        setQueue(q);
        if (q.items.length > 0) setSelectedCaseId(q.items[0].case_id);
        else setSelectedCaseId(null);
      })
      .catch((e) => setError(String((e as Error).message)))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, dimCode, annotator, includeDone]);

  const selectedItem: QueueItem | undefined = useMemo(
    () => queue?.items.find((it) => it.case_id === selectedCaseId),
    [queue, selectedCaseId]
  );

  // 切换 case 时重置表单（如果该 case 已有标注则预填）
  useEffect(() => {
    if (!selectedItem) {
      setChoice("1");
      setComment("");
      setEvidence("");
      return;
    }
    const ex = selectedItem.existing_annotation;
    if (ex) {
      if (ex.is_applicable === false) setChoice("na");
      else if (ex.score === 0) setChoice("0");
      else if (ex.score === 0.5) setChoice("0.5");
      else if (ex.score === 1) setChoice("1");
      else setChoice("1");
      setComment(ex.comment || "");
      setEvidence(ex.evidence_text || "");
    } else {
      setChoice("1");
      setComment("");
      setEvidence("");
    }
    setSubmitMsg(null);
    setRawOpen(false);
  }, [selectedItem]);

  async function submit() {
    if (!selectedItem || !annotator.trim()) {
      setSubmitMsg({ tone: "err", text: "请先填写 annotator 名字" });
      return;
    }
    if (choice === "skip") {
      // 不入库，直接下一题
      goNext();
      return;
    }
    setSubmitting(true);
    setSubmitMsg(null);
    try {
      const body: Record<string, unknown> = {
        conversation_id: selectedItem.conversation_id,
        dimension_code: dimCode,
        annotator: annotator.trim(),
        comment: comment || null,
        evidence_text: evidence || null,
      };
      if (choice === "na") {
        body.score = null;
        body.is_applicable = false;
      } else {
        body.score = parseFloat(choice);
        body.is_applicable = true;
      }
      await api<AnnotationOut>("/api/annotations", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setSubmitMsg({ tone: "ok", text: "已保存" });
      // 移除 / 标记完成，跳下一题
      goNext(selectedItem.case_id);
    } catch (e) {
      setSubmitMsg({ tone: "err", text: String((e as Error).message) });
    } finally {
      setSubmitting(false);
    }
  }

  function goNext(justFinishedCaseId?: number) {
    if (!queue) return;
    let nextItems = queue.items;
    if (justFinishedCaseId !== undefined && !includeDone) {
      nextItems = queue.items.filter((it) => it.case_id !== justFinishedCaseId);
      setQueue({ ...queue, items: nextItems, total: nextItems.length });
    }
    if (nextItems.length === 0) {
      setSelectedCaseId(null);
      return;
    }
    const idx = nextItems.findIndex((it) => it.case_id === selectedCaseId);
    const next = nextItems[idx + 1] || nextItems[0];
    setSelectedCaseId(next.case_id);
  }

  return (
    <div className="mx-auto flex max-w-[1800px] min-w-0 flex-col gap-xl pb-4xl">
      <header className="flex flex-col gap-sm">
        <div className="text-caption uppercase tracking-[0.08em] text-ink-3">
          <span className="italic-display normal-case tracking-normal">标注 · 工作台</span>
        </div>
        <div className="flex flex-wrap items-baseline justify-between gap-md">
          <h1 className="m-0 font-display text-h1 text-ink">标注工作台</h1>
          <Link
            href="/annotations/agreement"
            className="border-b border-rule pb-[1px] text-sm text-ink-2 transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
          >
            一致率看板 <span aria-hidden>→</span>
          </Link>
        </div>
        <p className="m-0 max-w-[72ch] text-lede italic-display text-ink-2">
          按机评分（0 → 0.5 → 1 → N/A）优先级展示待标注 case，对照模型评分给出人评，可选「评分 / 不适用 / 跳过」。
          同一 annotator 对同一 (case, 维度) 多次提交将 UPSERT 覆盖。
        </p>
      </header>

      {/* 顶部筛选条 */}
      <div className="bg-card border border-[var(--rule)] rounded p-4 mb-6 grid grid-cols-[1fr_2fr_1fr_auto] gap-4 items-end">
        <Field label="Eval Run">
          <select
            value={runId}
            onChange={(e) => setRunId(parseInt(e.target.value, 10))}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 text-sm"
          >
            <option value={0}>—</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                #{r.id} {r.name} ({r.status})
              </option>
            ))}
          </select>
        </Field>
        <Field label="维度">
          <div className="flex gap-1.5 flex-wrap">
            {DIM_CODES.map((d) => (
              <button
                key={d}
                onClick={() => setDimCode(d)}
                className={`px-2.5 py-1.5 text-xs border rounded transition-colors ${
                  dimCode === d
                    ? "bg-moss text-white border-moss"
                    : "border-[var(--rule-strong)] hover:bg-[var(--rule)]"
                }`}
              >
                {d} · {DIM_LABELS[d]}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Annotator 名">
          <input
            value={annotator}
            onChange={(e) => setAnnotator(e.target.value)}
            placeholder="e.g. alice"
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 text-sm"
          />
        </Field>
        <label className="flex items-center gap-2 text-sm pb-2">
          <input
            type="checkbox"
            checked={includeDone}
            onChange={(e) => setIncludeDone(e.target.checked)}
          />
          含已标
        </label>
      </div>

      {error && (
        <div className="border border-tomato/30 bg-tomato/5 rounded p-3 text-sm text-tomato mb-4">
          {error}
        </div>
      )}

      {/* 三栏布局 */}
      <div className="grid grid-cols-[340px_minmax(0,1fr)_420px] gap-6">
        {/* 左栏：队列 */}
        <div className="bg-card border border-[var(--rule)] rounded">
          <div className="px-4 py-3 border-b border-[var(--rule)] flex items-baseline justify-between">
            <div className="uppercase-label text-ink-3">队列</div>
            <div className="text-xs text-ink-3 font-mono-feat">
              {loading ? "..." : queue ? `${queue.total} 条` : "—"}
            </div>
          </div>
          <div className="max-h-[700px] overflow-y-auto">
            {queue?.items.length === 0 && !loading && (
              <div className="px-4 py-8 text-center text-ink-3 text-sm">
                队列为空。{annotator.trim() ? "（该 annotator 可能已全部标完）" : "选择 Run + 维度后会自动加载。"}
              </div>
            )}
            {queue?.items.map((it) => {
              const isSelected = it.case_id === selectedCaseId;
              const isDone = !!it.existing_annotation;
              return (
                <button
                  key={it.case_id}
                  onClick={() => setSelectedCaseId(it.case_id)}
                  className={`block w-full text-left px-4 py-2.5 border-b border-[var(--rule)] last:border-0 transition-colors ${
                    isSelected
                      ? "bg-[var(--moss-bg)]"
                      : "hover:bg-[var(--rule)]"
                  } ${isDone ? "opacity-60" : ""}`}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="font-mono-feat text-xs text-ink-2 truncate">
                      {it.conversation_id_src}
                    </div>
                    <span className={scoreBadgeClass(it.judge_score, it.judge_applicable)}>
                      {scoreLabel(it.judge_score, it.judge_applicable)}
                    </span>
                  </div>
                  <div className="text-[11px] text-ink-3 mt-1 flex items-center gap-2">
                    {it.quality_label && (
                      <span className="badge badge-neutral text-[10px]">{it.quality_label}</span>
                    )}
                    {it.dimension_tag && <span className="truncate">{it.dimension_tag}</span>}
                    {isDone && <span className="text-moss ml-auto">✓ 已标</span>}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* 中栏：对话 */}
        <div className="bg-card border border-[var(--rule)] rounded">
          <div className="px-5 py-3 border-b border-[var(--rule)]">
            {selectedItem ? (
              <>
                <div className="flex items-baseline justify-between">
                  <div className="font-display text-xl">{selectedItem.conversation_id_src}</div>
                  <div className="text-xs text-ink-3">case #{selectedItem.case_id}</div>
                </div>
                <div className="text-xs text-ink-3 mt-1 flex gap-3">
                  {selectedItem.quality_label && (
                    <span>
                      质量：<span className="text-ink-2">{selectedItem.quality_label}</span>
                    </span>
                  )}
                  {selectedItem.dimension_tag && (
                    <span>
                      标签：<span className="text-ink-2">{selectedItem.dimension_tag}</span>
                    </span>
                  )}
                  <span>共 {selectedItem.turns.length} 轮</span>
                </div>
              </>
            ) : (
              <div className="uppercase-label text-ink-3">对话内容</div>
            )}
          </div>
          <div className="px-5 py-4 max-h-[700px] overflow-y-auto">
            {!selectedItem && (
              <div className="text-ink-3 text-sm py-8 text-center">
                从左侧队列选择一个 case 开始标注。
              </div>
            )}
            {selectedItem?.turns.map((t) => (
              <div key={t.turn_index} className="mb-5 last:mb-0">
                <div className="uppercase-label text-ink-3 mb-2">Turn {t.turn_index}</div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-card-2 border border-[var(--rule)] rounded p-3">
                    <div className="uppercase-label text-ink-3 text-[10px] mb-1.5">User</div>
                    <div className="text-sm text-ink whitespace-pre-wrap">{t.user_query}</div>
                  </div>
                  <div className="bg-card-2 border border-[var(--rule)] rounded p-3">
                    <div className="uppercase-label text-ink-3 text-[10px] mb-1.5">Bot 改写</div>
                    <div className="text-sm whitespace-pre-wrap">
                      {t.rewritten_query ? (
                        <span className="text-ink">{t.rewritten_query}</span>
                      ) : (
                        <span className="text-ink-3 italic">（首轮无需改写 / Bot 未生成）</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 右栏：机评结果 + 标注表单 */}
        <div className="flex flex-col gap-6">
          {/* 机评结果卡 */}
          <div className="bg-card border border-[var(--rule)] rounded p-5">
            <div className="uppercase-label text-ink-3 mb-3">机评结果 · {DIM_LABELS[dimCode]}</div>
            {selectedItem ? (
              <>
                <div className="flex items-baseline gap-3 mb-3">
                  <span className={`${scoreBadgeClass(selectedItem.judge_score, selectedItem.judge_applicable)} text-lg`}>
                    {scoreLabel(selectedItem.judge_score, selectedItem.judge_applicable)}
                  </span>
                  {selectedItem.judge_applicable === false && (
                    <span className="text-ink-3 text-xs">机评判定本维度不适用</span>
                  )}
                  {selectedItem.judge_confidence != null && (
                    <span className="text-xs text-ink-3 font-mono-feat">
                      conf={selectedItem.judge_confidence.toFixed(2)}
                    </span>
                  )}
                </div>
                {selectedItem.judge_explanation && (
                  <div className="text-sm text-ink-2 mb-3 leading-relaxed">
                    {selectedItem.judge_explanation}
                  </div>
                )}
                {selectedItem.judge_raw && (
                  <details
                    open={rawOpen}
                    onToggle={(e) => setRawOpen((e.target as HTMLDetailsElement).open)}
                    className="mt-2"
                  >
                    <summary className="cursor-pointer text-xs text-ink-3 hover:text-ink">
                      原始 judge 响应（JSON）
                    </summary>
                    <pre className="mt-2 text-[11px] bg-[var(--bg)] p-2 rounded overflow-x-auto max-h-60 leading-snug font-mono-feat">
                      {JSON.stringify(selectedItem.judge_raw, null, 2)}
                    </pre>
                  </details>
                )}
              </>
            ) : (
              <div className="text-ink-3 text-sm">—</div>
            )}
          </div>

          {/* 标注表单 */}
          <div className="bg-card border border-[var(--rule)] rounded p-5">
            <div className="uppercase-label text-ink-3 mb-3">人工标注</div>
            <fieldset disabled={!selectedItem || !annotator.trim()} className="space-y-4">
              <div>
                <div className="uppercase-label text-ink-3 mb-2 text-[10px]">评分</div>
                <div className="grid grid-cols-5 gap-2 text-sm">
                  {(["0", "0.5", "1", "na", "skip"] as Choice[]).map((c) => {
                    const label =
                      c === "0" ? "0" : c === "0.5" ? "0.5" : c === "1" ? "1" : c === "na" ? "N/A" : "跳过";
                    const checked = choice === c;
                    return (
                      <label
                        key={c}
                        className={`flex items-center justify-center px-2 py-2 border rounded cursor-pointer transition-colors ${
                          checked
                            ? "border-moss bg-[var(--moss-bg)] text-moss font-medium"
                            : "border-[var(--rule-strong)] hover:bg-[var(--rule)]"
                        }`}
                      >
                        <input
                          type="radio"
                          name="choice"
                          value={c}
                          checked={checked}
                          onChange={() => setChoice(c)}
                          className="sr-only"
                        />
                        {label}
                      </label>
                    );
                  })}
                </div>
                <div className="text-[11px] text-ink-3 mt-1.5 leading-snug">
                  0/0.5/1 → 评分；N/A → 不适用；跳过 → 不入库，直接下一条
                </div>
              </div>

              <div>
                <div className="uppercase-label text-ink-3 mb-1.5 text-[10px]">备注（可选）</div>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  rows={2}
                  placeholder="为什么打这个分？"
                  className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 text-sm resize-none"
                />
              </div>

              <div>
                <div className="uppercase-label text-ink-3 mb-1.5 text-[10px]">证据片段（可选）</div>
                <textarea
                  value={evidence}
                  onChange={(e) => setEvidence(e.target.value)}
                  rows={2}
                  placeholder="对话中关键句"
                  className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 text-sm resize-none"
                />
              </div>

              {submitMsg && (
                <div
                  className={`text-xs px-2 py-1 rounded ${
                    submitMsg.tone === "ok"
                      ? "bg-[var(--moss-bg)] text-moss"
                      : "bg-tomato/10 text-tomato"
                  }`}
                >
                  {submitMsg.text}
                </div>
              )}

              <div className="flex justify-between items-center pt-2 border-t border-[var(--rule)]">
                <button
                  type="button"
                  onClick={() => goNext()}
                  className="text-xs text-ink-3 hover:text-ink"
                >
                  ← 下一条 (不保存)
                </button>
                <button
                  type="button"
                  disabled={submitting}
                  onClick={submit}
                  className="px-4 py-2 bg-moss text-white text-sm rounded hover:opacity-90 disabled:opacity-50"
                >
                  {submitting ? "提交中…" : choice === "skip" ? "跳过 →" : "提交 + 下一条"}
                </button>
              </div>
            </fieldset>
            {!annotator.trim() && (
              <div className="text-xs text-tomato mt-3">请先在顶部填写 annotator 名字。</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block uppercase-label text-ink-3 mb-1.5 text-[10px]">{label}</span>
      {children}
    </label>
  );
}
