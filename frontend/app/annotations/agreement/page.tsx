"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
  type AgreementResponse,
  type AgreementAnnotator,
  type AgreementDim,
  type EvalRun,
} from "@/lib/api";

const LEVELS = ["0", "0.5", "1", "N/A"];
const MIN_SAMPLE = 20; // Spec-12

function kappaLabel(k: number | null): string {
  if (k == null) return "—";
  if (k >= 0.8) return "几乎完全一致";
  if (k >= 0.6) return "显著一致";
  if (k >= 0.4) return "中等一致";
  if (k >= 0.2) return "弱一致";
  return "差或反向";
}

function kappaToneClass(k: number | null): string {
  if (k == null) return "text-ink-3";
  if (k >= 0.6) return "text-moss";
  if (k >= 0.4) return "text-ink";
  if (k >= 0.2) return "text-amber";
  return "text-tomato";
}

export default function AgreementDashboardPage() {
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [runId, setRunId] = useState<number>(0);
  const [annotator, setAnnotator] = useState<string>("");
  const [merge, setMerge] = useState(false);
  const [data, setData] = useState<AgreementResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (annotator.trim()) params.append("annotator", annotator.trim());
    if (merge) params.append("merge", "true");
    const qs = params.toString();
    api<AgreementResponse>(`/api/agreement/${runId}${qs ? `?${qs}` : ""}`)
      .then(setData)
      .catch((e) => setError(String((e as Error).message)))
      .finally(() => setLoading(false));
  }, [runId, annotator, merge]);

  return (
    <div className="mx-auto flex max-w-[1500px] min-w-0 flex-col gap-2xl pb-4xl">
      <header className="flex flex-col gap-sm">
        <div className="text-caption uppercase tracking-[0.08em] text-ink-3">
          <span className="italic-display normal-case tracking-normal">标注 · 一致率</span>
        </div>
        <div className="flex flex-wrap items-baseline justify-between gap-md">
          <h1 className="m-0 font-display text-h1 text-ink">一致率看板</h1>
          <Link
            href="/annotations"
            className="border-b border-rule pb-[1px] text-sm text-ink-2 transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
          >
            <span aria-hidden>←</span> 返回工作台
          </Link>
        </div>
        <p className="m-0 max-w-[68ch] text-lede italic-display text-ink-2">
          基于人工标注 vs 机评分的 4 档（0 / 0.5 / 1 / N/A）一致率。每维度独立计算 accuracy 和 Cohen&apos;s weighted κ。
          样本不足 20 时仅展示 accuracy。
        </p>
      </header>

      {/* 筛选条 */}
      <div className="bg-card border border-[var(--rule)] rounded p-4 mb-6 flex flex-wrap items-end gap-4">
        <label className="block">
          <span className="block uppercase-label text-ink-3 mb-1.5 text-[10px]">Eval Run</span>
          <select
            value={runId}
            onChange={(e) => setRunId(parseInt(e.target.value, 10))}
            className="px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 text-sm min-w-[280px]"
          >
            <option value={0}>—</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                #{r.id} {r.name} ({r.status})
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="block uppercase-label text-ink-3 mb-1.5 text-[10px]">Annotator（可选）</span>
          <input
            value={annotator}
            onChange={(e) => setAnnotator(e.target.value)}
            placeholder="留空 = 所有"
            disabled={merge}
            className="px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 text-sm disabled:opacity-50"
          />
        </label>
        <div className="flex gap-2 pb-1">
          <button
            onClick={() => setMerge(false)}
            className={`px-3 py-1.5 text-xs border rounded ${
              !merge
                ? "bg-moss text-white border-moss"
                : "border-[var(--rule-strong)] hover:bg-[var(--rule)]"
            }`}
          >
            按 annotator 分
          </button>
          <button
            onClick={() => {
              setMerge(true);
              setAnnotator("");
            }}
            className={`px-3 py-1.5 text-xs border rounded ${
              merge
                ? "bg-moss text-white border-moss"
                : "border-[var(--rule-strong)] hover:bg-[var(--rule)]"
            }`}
          >
            合并视图 (投票)
          </button>
        </div>
      </div>

      {error && (
        <div className="border border-tomato/30 bg-tomato/5 rounded p-3 text-sm text-tomato mb-4">
          {error}
        </div>
      )}

      {loading && <div className="text-ink-3 text-sm">加载中…</div>}

      {!loading && data && data.per_annotator.length === 0 && (
        <div className="bg-card border border-[var(--rule)] rounded p-10 text-center text-ink-3">
          该 run 暂无人工标注数据。前往 <Link className="text-moss underline" href="/annotations">标注工作台</Link> 开始标注。
        </div>
      )}

      {!loading && data?.per_annotator.map((ann) => (
        <AnnotatorCard key={ann.annotator} ann={ann} />
      ))}
    </div>
  );
}

function AnnotatorCard({ ann }: { ann: AgreementAnnotator }) {
  return (
    <section className="bg-card border border-[var(--rule)] rounded mb-6">
      <header className="px-6 py-4 border-b border-[var(--rule)] flex items-baseline justify-between">
        <div className="flex items-baseline gap-3">
          <div className="uppercase-label text-ink-3">Annotator</div>
          <div className="font-display text-2xl">
            {ann.annotator === "<merged>" ? "合并视图（众数投票）" : ann.annotator}
          </div>
        </div>
        <div className="flex items-baseline gap-6 text-sm">
          <Stat label="总样本" value={ann.total_sample_size.toString()} mono />
          <Stat
            label="加权 accuracy"
            value={ann.overall_accuracy != null ? `${(ann.overall_accuracy * 100).toFixed(1)}%` : "—"}
            mono
          />
          <Stat
            label="加权 κ"
            value={ann.overall_kappa != null ? ann.overall_kappa.toFixed(3) : "—"}
            mono
            valueClass={kappaToneClass(ann.overall_kappa)}
          />
        </div>
      </header>
      <div className="p-6 grid grid-cols-2 gap-4">
        {ann.dims.map((d) => (
          <DimCard key={d.dim_code} dim={d} />
        ))}
      </div>
    </section>
  );
}

function DimCard({ dim }: { dim: AgreementDim }) {
  const tooFew = dim.sample_size < MIN_SAMPLE;
  return (
    <div className="border border-[var(--rule)] rounded p-4 bg-card-2">
      <div className="flex items-baseline justify-between mb-3">
        <div>
          <div className="text-ink font-medium">{dim.dim_name}</div>
          <div className="font-mono-feat text-[11px] text-ink-3">{dim.dim_code}</div>
        </div>
        <div className="text-xs text-ink-3 font-mono-feat">n={dim.sample_size}</div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3 text-sm">
        <div>
          <div className="uppercase-label text-ink-3 text-[10px] mb-0.5">Accuracy</div>
          <div className="font-mono-feat tabular-nums">
            {dim.accuracy != null ? `${(dim.accuracy * 100).toFixed(1)}%` : "—"}
          </div>
        </div>
        <div>
          <div className="uppercase-label text-ink-3 text-[10px] mb-0.5">Kappa</div>
          {tooFew ? (
            <span className="badge badge-neutral text-[10px]">样本太少 (n={dim.sample_size})</span>
          ) : (
            <div className={`font-mono-feat tabular-nums ${kappaToneClass(dim.kappa)}`}>
              {dim.kappa != null ? dim.kappa.toFixed(3) : "—"}
              {dim.kappa != null && (
                <span className="ml-1.5 text-[10px] text-ink-3">{kappaLabel(dim.kappa)}</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 4×4 混淆矩阵 */}
      <div>
        <div className="uppercase-label text-ink-3 text-[10px] mb-1.5">
          混淆矩阵（行 judge × 列 human）
        </div>
        <table className="w-full text-[11px]">
          <thead>
            <tr>
              <th className="px-1 py-0.5 text-ink-3 text-left font-normal">J\H</th>
              {LEVELS.map((l) => (
                <th key={l} className="px-1 py-0.5 text-ink-3 font-normal">
                  {l}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dim.confusion_matrix.map((row, i) => (
              <tr key={i}>
                <td className="px-1 py-0.5 text-ink-3">{LEVELS[i]}</td>
                {row.map((v, j) => (
                  <td
                    key={j}
                    className={`px-1.5 py-0.5 text-center font-mono-feat tabular-nums border border-[var(--rule)] ${
                      v === 0
                        ? "text-ink-3"
                        : i === j
                        ? "bg-[var(--moss-bg)] text-moss font-medium"
                        : "text-tomato"
                    }`}
                  >
                    {v}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  mono,
  valueClass,
}: {
  label: string;
  value: string;
  mono?: boolean;
  valueClass?: string;
}) {
  return (
    <div>
      <div className="uppercase-label text-ink-3 text-[10px]">{label}</div>
      <div className={`${mono ? "font-mono-feat tabular-nums" : ""} ${valueClass || ""}`}>
        {value}
      </div>
    </div>
  );
}
