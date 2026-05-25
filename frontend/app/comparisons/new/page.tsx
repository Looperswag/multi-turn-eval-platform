"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type DiffRunsResult, type EvalRun } from "@/lib/api";

type ComparisonType = "prompt" | "bot" | "judge" | "human";

const TYPE_OPTIONS: { value: ComparisonType; label: string; hint: string; disabled?: boolean }[] = [
  { value: "prompt", label: "Prompt 对比", hint: "bot/judge/dataset 相同，prompt 版本不同" },
  { value: "bot", label: "Bot 对比", hint: "dataset/judge/prompt 相同，bot 版本不同" },
  { value: "judge", label: "Judge 模型对比", hint: "dataset/bot/prompt 相同，judge 模型不同" },
  {
    value: "human",
    label: "机评 vs 人工（A.5.2 启用）",
    hint: "走独立端点，W1.5 末尾启用",
    disabled: true,
  },
];

const FIELD_LABEL: Record<string, string> = {
  dataset_id: "数据集",
  bot_version_id: "Bot 版本",
  judge_model_id: "Judge 模型",
  judge_prompt_version_ids: "Prompt 版本",
};

export default function NewComparisonPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [runA, setRunA] = useState<number>(0);
  const [runB, setRunB] = useState<number>(0);
  const [diff, setDiff] = useState<DiffRunsResult | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [diffError, setDiffError] = useState<string | null>(null);
  const [type, setType] = useState<ComparisonType>("prompt");
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    api<EvalRun[]>("/api/eval-runs")
      .then((all) => {
        const finished = all.filter((r) => r.status === "success" || r.status === "partial");
        setRuns(finished);
        if (finished.length > 0) setRunA(finished[0].id);
        if (finished.length > 1) setRunB(finished[1].id);
      })
      .catch(console.error);
  }, []);

  // Spec-7: 用户选好两 run 后自动调 diff-runs
  useEffect(() => {
    if (!runA || !runB || runA === runB) {
      setDiff(null);
      setDiffError(null);
      return;
    }
    setDiffLoading(true);
    setDiffError(null);
    api<DiffRunsResult>(`/api/comparisons/diff-runs?a=${runA}&b=${runB}`)
      .then((d) => {
        setDiff(d);
        if (d.suggested_type) setType(d.suggested_type as ComparisonType);
      })
      .catch((e) => {
        setDiff(null);
        setDiffError(String((e as Error).message || e));
      })
      .finally(() => setDiffLoading(false));
  }, [runA, runB]);

  const runOptionsB = useMemo(() => runs.filter((r) => r.id !== runA), [runs, runA]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!runA || !runB || runA === runB) {
      setSubmitError("请选择两个不同的 run");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await api<{ id: number }>("/api/comparisons", {
        method: "POST",
        body: JSON.stringify({
          run_a_id: runA,
          run_b_id: runB,
          type,
          name: name || null,
        }),
      });
      router.push(`/comparisons/${created.id}`);
    } catch (err) {
      setSubmitError((err as Error).message || String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-[820px] min-w-0 flex-col gap-2xl pb-4xl">
      <header className="flex flex-col gap-sm">
        <div className="text-caption uppercase tracking-[0.08em] text-ink-3">
          <span className="font-mono tabular-nums">1/1</span>
          <span aria-hidden className="px-xs text-ink-4">·</span>
          <span className="italic-display normal-case tracking-normal">对比 · 新建</span>
        </div>
        <h1 className="m-0 font-display text-h1 text-ink">新建对比</h1>
        <p className="m-0 max-w-[68ch] text-lede italic-display text-ink-2">
          选定两个已完成的 run，平台自动检测差异并推荐对比类型（Prompt / Bot / Judge）。
        </p>
      </header>

      <form onSubmit={submit} className="flex flex-col gap-xl border-t border-rule pt-lg">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Run A">
            <select
              required
              value={runA}
              onChange={(e) => setRunA(parseInt(e.target.value, 10))}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            >
              <option value={0}>—</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  #{r.id} {r.name} ({r.status})
                </option>
              ))}
            </select>
          </Field>
          <Field label="Run B">
            <select
              required
              value={runB}
              onChange={(e) => setRunB(parseInt(e.target.value, 10))}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            >
              <option value={0}>—</option>
              {runOptionsB.map((r) => (
                <option key={r.id} value={r.id}>
                  #{r.id} {r.name} ({r.status})
                </option>
              ))}
            </select>
          </Field>
        </div>

        {/* Diff 自动检测面板 */}
        <div className="border border-dashed border-[var(--rule-strong)] rounded p-4 bg-card-2">
          <div className="uppercase-label text-ink-3 mb-2">差异自动检测</div>
          {!runA || !runB || runA === runB ? (
            <div className="text-ink-3 text-sm">请先选择两个不同的 run。</div>
          ) : diffLoading ? (
            <div className="text-ink-3 text-sm">检测中…</div>
          ) : diffError ? (
            <div className="text-tomato text-sm">{diffError}</div>
          ) : diff ? (
            <>
              {diff.diff_points.length === 0 ? (
                <div className="text-tomato text-sm">
                  两 run 配置完全相同，无差异可对比。建议换一个 run。
                </div>
              ) : (
                <ul className="text-sm space-y-1.5">
                  {diff.diff_points.map((p) => (
                    <li key={p.field} className="flex items-baseline gap-2">
                      <span className="font-mono-feat text-ink-3 min-w-[120px]">
                        {FIELD_LABEL[p.field] || p.field}
                      </span>
                      <span className="text-ink">
                        A=<code className="text-moss">{JSON.stringify(p.value_a)}</code>{" "}
                        B=<code className="text-tomato">{JSON.stringify(p.value_b)}</code>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {diff.suggested_type && (
                <div className="mt-3 text-xs text-ink-2">
                  推荐对比类型：
                  <span className="ml-1 badge badge-info">{diff.suggested_type}</span>
                  （已自动选中下方）
                </div>
              )}
            </>
          ) : null}
        </div>

        <Field label="对比类型">
          <div className="space-y-2">
            {TYPE_OPTIONS.map((opt) => {
              const isSuggested = diff?.suggested_type === opt.value;
              return (
                <label
                  key={opt.value}
                  className={`flex items-start gap-3 px-3 py-2 border rounded cursor-pointer transition-colors ${
                    type === opt.value
                      ? "border-moss bg-[var(--moss-bg)]"
                      : "border-[var(--rule-strong)] hover:bg-[var(--rule)]"
                  } ${opt.disabled ? "opacity-40 cursor-not-allowed" : ""}`}
                >
                  <input
                    type="radio"
                    name="ctype"
                    value={opt.value}
                    checked={type === opt.value}
                    disabled={opt.disabled}
                    onChange={() => setType(opt.value)}
                    className="mt-1"
                  />
                  <div className="flex-1">
                    <div className="text-ink flex items-baseline gap-2">
                      {opt.label}
                      {isSuggested && (
                        <span className="text-xs text-moss font-medium">推荐</span>
                      )}
                    </div>
                    <div className="text-ink-3 text-xs">{opt.hint}</div>
                  </div>
                </label>
              );
            })}
          </div>
        </Field>

        <Field label="名称（可选，留空自动生成）">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. prompt v4 vs v5"
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
          />
        </Field>

        {submitError && (
          <div className="border border-tomato/30 bg-tomato/5 rounded px-3 py-2 text-sm text-tomato">
            {submitError}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-4 border-t border-[var(--rule)]">
          <button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2 border border-[var(--rule-strong)] rounded text-sm"
          >
            取消
          </button>
          <button
            type="submit"
            disabled={submitting || !runA || !runB || runA === runB}
            className="px-5 py-2 bg-moss text-white text-sm rounded hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? "计算中…" : "创建对比"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block uppercase-label text-ink-3 mb-1.5">{label}</span>
      {children}
    </label>
  );
}
