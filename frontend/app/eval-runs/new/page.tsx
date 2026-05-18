"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, RegressionSetOut } from "@/lib/api";

type Dataset = { id: number; name: string; conversation_count: number };
type BotVersion = { id: number; name: string; version_tag: string };
type JudgeModel = { id: number; name: string; provider: string; model_id: string };
type PromptVersion = { id: number; dimension_code: string; version_tag: string; weight: number };

const DIM_NAMES: Record<string, string> = {
  dim1: "改写忠实性",
  dim2: "跨轮记忆保留",
  dim3: "意图边界识别",
  dim4: "指代消解准确性",
  dim5: "重复请求处理",
  dim6: "用户纠错响应",
};

const DEFAULT_DIM_WEIGHTS: Record<string, number> = {
  dim1: 0.30,
  dim2: 0.30,
  dim3: 0.10,
  dim4: 0.10,
  dim5: 0.10,
  dim6: 0.10,
};

export default function NewEvalRunPage() {
  const router = useRouter();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [bots, setBots] = useState<BotVersion[]>([]);
  const [models, setModels] = useState<JudgeModel[]>([]);
  const [prompts, setPrompts] = useState<PromptVersion[]>([]);
  const [regressionSets, setRegressionSets] = useState<RegressionSetOut[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    dataset_id: 0,
    bot_version_id: 0,
    judge_model_id: 0,
    concurrency: 5,
    sampling_count: "" as string | "",
    dimensions: ["dim1", "dim2", "dim3", "dim4", "dim5", "dim6"],
    prompt_versions: {} as Record<string, number>,
    // 每维度权重；空字符串表示用户清空了，提交时按 0 处理（但 UI 会警告 sum=0）
    weights: { ...DEFAULT_DIM_WEIGHTS } as Record<string, number>,
    regression_set_id: 0, // 0 表示不指定
  });

  useEffect(() => {
    Promise.all([
      api<Dataset[]>("/api/datasets"),
      api<BotVersion[]>("/api/bot-versions"),
      api<JudgeModel[]>("/api/judge-config/models"),
      api<PromptVersion[]>("/api/judge-config/prompts"),
      api<RegressionSetOut[]>("/api/regression-sets"),
    ])
      .then(([d, b, m, p, rs]) => {
        setDatasets(d);
        setBots(b);
        setModels(m);
        setPrompts(p);
        setRegressionSets(rs);
        const defaults: Record<string, number> = {};
        const weightDefaults: Record<string, number> = { ...DEFAULT_DIM_WEIGHTS };
        for (const dim of ["dim1", "dim2", "dim3", "dim4", "dim5", "dim6"]) {
          const v = p.find((x) => x.dimension_code === dim);
          if (v) {
            defaults[dim] = v.id;
            // 优先用 prompt 自带 weight 作为默认；为 0/未设则回到 DEFAULT_DIM_WEIGHTS
            if (typeof v.weight === "number" && v.weight > 0) {
              weightDefaults[dim] = v.weight;
            }
          }
        }
        setForm((f) => ({
          ...f,
          dataset_id: d[0]?.id ?? 0,
          bot_version_id: b[0]?.id ?? 0,
          judge_model_id: m[0]?.id ?? 0,
          prompt_versions: defaults,
          weights: weightDefaults,
        }));
      })
      .catch(console.error);
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    // 前端兜底：已选维度的权重总和必须 > 0
    const selectedSum = form.dimensions.reduce((s, d) => s + (form.weights[d] ?? 0), 0);
    if (selectedSum <= 0) {
      alert("已选维度的权重总和必须 > 0；请至少给一个维度配权重，或恢复默认。");
      return;
    }
    setSubmitting(true);
    try {
      const useRS = form.regression_set_id > 0;
      // 只把"已选维度"的权重提交，避免后端误将未选维度纳入分母
      const weightsPayload: Record<string, number> = {};
      for (const d of form.dimensions) {
        weightsPayload[d] = form.weights[d] ?? 0;
      }
      const created = await api<{ id: number }>("/api/eval-runs", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          description: form.description || null,
          dataset_id: form.dataset_id,
          bot_version_id: form.bot_version_id,
          judge_model_id: form.judge_model_id,
          dimensions_selected: form.dimensions,
          judge_prompt_version_ids: form.prompt_versions,
          dimension_weights: weightsPayload,
          concurrency: form.concurrency,
          // 回归集模式下 sampling_count 必置 null（集合已定数）
          sampling_count:
            useRS || !form.sampling_count
              ? null
              : parseInt(form.sampling_count, 10),
          regression_set_id: useRS ? form.regression_set_id : null,
        }),
      });
      router.push(`/eval-runs/${created.id}`);
    } catch (err) {
      alert("创建失败：" + (err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-[800px]">
      <div className="mb-8">
        <div className="uppercase-label text-ink-3 mb-2">评测 / 新建</div>
        <h1 className="font-display text-4xl font-medium tracking-tight">新建评测任务</h1>
      </div>

      <form onSubmit={submit} className="space-y-6">
        <Field label="任务名称">
          <input
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            placeholder="e.g. v4 baseline 2026-05"
          />
        </Field>

        <Field label="描述（可选）">
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={2}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
          />
        </Field>

        <div className="grid grid-cols-3 gap-4">
          <Field label="评测集">
            <Select
              value={form.dataset_id}
              onChange={(v) => setForm({ ...form, dataset_id: v })}
              options={datasets.map((d) => ({ value: d.id, label: `${d.name} (${d.conversation_count})` }))}
            />
          </Field>
          <Field label="Bot 版本">
            <Select
              value={form.bot_version_id}
              onChange={(v) => setForm({ ...form, bot_version_id: v })}
              options={bots.map((b) => ({ value: b.id, label: `${b.name} · ${b.version_tag}` }))}
            />
          </Field>
          <Field label="Judge 模型">
            <Select
              value={form.judge_model_id}
              onChange={(v) => setForm({ ...form, judge_model_id: v })}
              options={models.map((m) => ({ value: m.id, label: `${m.provider} · ${m.model_id}` }))}
            />
          </Field>
        </div>

        <Field label="维度 · Prompt · 权重">
          <div className="border border-[var(--rule)] rounded">
            <div className="grid grid-cols-[24px_1fr_140px_120px] items-center gap-3 px-4 py-2 border-b border-[var(--rule)] bg-[var(--card-2)] text-ink-3 uppercase-label text-[10px]">
              <span></span>
              <span>维度</span>
              <span>Prompt 版本</span>
              <span>权重</span>
            </div>
            {(["dim1", "dim2", "dim3", "dim4", "dim5", "dim6"] as const).map((dim) => {
              const isSelected = form.dimensions.includes(dim);
              const dimPrompts = prompts.filter((p) => p.dimension_code === dim);
              const currentPromptId = form.prompt_versions[dim] ?? 0;
              const currentWeight = form.weights[dim];
              return (
                <div
                  key={dim}
                  className={`grid grid-cols-[24px_1fr_140px_120px] items-center gap-3 px-4 py-3 border-b border-[var(--rule)] last:border-0 ${
                    isSelected ? "" : "opacity-50"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={(e) => {
                      const next = e.target.checked
                        ? [...form.dimensions, dim]
                        : form.dimensions.filter((d) => d !== dim);
                      setForm({ ...form, dimensions: next });
                    }}
                  />
                  <span>
                    <span className="text-ink">{DIM_NAMES[dim]}</span>
                    <span className="text-ink-3 text-xs ml-2 font-mono-feat">{dim}</span>
                  </span>
                  <Select
                    value={currentPromptId}
                    onChange={(v) => {
                      const p = dimPrompts.find((x) => x.id === v);
                      // 切换 prompt 时同步把权重默认值改为新 prompt 的 weight
                      const w =
                        p && typeof p.weight === "number" && p.weight > 0
                          ? p.weight
                          : form.weights[dim] ?? DEFAULT_DIM_WEIGHTS[dim];
                      setForm({
                        ...form,
                        prompt_versions: { ...form.prompt_versions, [dim]: v },
                        weights: { ...form.weights, [dim]: w },
                      });
                    }}
                    options={dimPrompts.map((p) => ({
                      value: p.id,
                      label: `${p.version_tag} · w=${p.weight}`,
                    }))}
                    small
                  />
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    value={Number.isFinite(currentWeight) ? currentWeight : 0}
                    disabled={!isSelected}
                    onChange={(e) => {
                      const raw = e.target.value;
                      const num = raw === "" ? 0 : parseFloat(raw);
                      setForm({
                        ...form,
                        weights: {
                          ...form.weights,
                          [dim]: Number.isFinite(num) && num >= 0 ? num : 0,
                        },
                      });
                    }}
                    className="px-2 py-1 border border-[var(--rule-strong)] rounded bg-card-2 text-xs font-mono-feat tabular-nums disabled:opacity-40"
                  />
                </div>
              );
            })}
            <WeightSummary
              dimensions={form.dimensions}
              weights={form.weights}
              onReset={() => setForm({ ...form, weights: { ...DEFAULT_DIM_WEIGHTS } })}
              onNormalize={() => {
                const total = form.dimensions.reduce(
                  (s, d) => s + (form.weights[d] ?? 0),
                  0,
                );
                if (total <= 0) return;
                const next: Record<string, number> = { ...form.weights };
                for (const d of form.dimensions) {
                  next[d] = Math.round(((form.weights[d] ?? 0) / total) * 10000) / 10000;
                }
                setForm({ ...form, weights: next });
              }}
            />
          </div>
        </Field>

        <Field label="仅跑回归集（可选）">
          <select
            value={form.regression_set_id}
            onChange={(e) =>
              setForm({ ...form, regression_set_id: parseInt(e.target.value, 10) })
            }
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
          >
            <option value={0}>— 不指定（按 dataset 全量/抽样）</option>
            {regressionSets.map((rs) => (
              <option key={rs.id} value={rs.id}>
                {rs.name} ({rs.item_count} 条)
              </option>
            ))}
          </select>
          {form.regression_set_id > 0 && (
            <div className="text-xs text-ink-3 mt-1.5">
              已选回归集，<code className="font-mono-feat">sampling_count</code> 被忽略；
              任务仅评测集合内 conversation（取 dataset 交集）。
            </div>
          )}
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="并发数">
            <input
              type="number"
              min={1}
              max={20}
              value={form.concurrency}
              onChange={(e) => setForm({ ...form, concurrency: parseInt(e.target.value, 10) })}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            />
          </Field>
          <Field label="抽样数（留空跑全量）">
            <input
              type="number"
              min={1}
              value={form.sampling_count}
              disabled={form.regression_set_id > 0}
              onChange={(e) => setForm({ ...form, sampling_count: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 disabled:opacity-50 disabled:bg-[var(--rule)]"
              placeholder={form.regression_set_id > 0 ? "回归集模式禁用" : "100"}
            />
          </Field>
        </div>

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
            disabled={submitting}
            className="px-5 py-2 bg-moss text-white text-sm rounded hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? "创建中…" : "启动评测"}
          </button>
        </div>
      </form>
    </div>
  );
}

function WeightSummary({
  dimensions,
  weights,
  onReset,
  onNormalize,
}: {
  dimensions: string[];
  weights: Record<string, number>;
  onReset: () => void;
  onNormalize: () => void;
}) {
  const sum = dimensions.reduce((s, d) => s + (weights[d] ?? 0), 0);
  const okSum = sum > 0;
  const isNorm = Math.abs(sum - 1) < 1e-3;
  return (
    <div className="px-4 py-2.5 flex items-center gap-3 bg-[var(--card-2)] text-xs">
      <span className="uppercase-label text-ink-3">已选维度权重总和</span>
      <span
        className={`font-mono-feat tabular-nums ${
          okSum ? (isNorm ? "text-moss" : "text-ink") : "text-tomato"
        }`}
      >
        {sum.toFixed(4).replace(/0+$/, "").replace(/\.$/, "") || "0"}
      </span>
      {!okSum && <span className="text-tomato">⚠ 总和必须 &gt; 0</span>}
      {okSum && !isNorm && (
        <span className="text-ink-3">
          相对权重不需要严格 = 1，scoring 会按总和归一化
        </span>
      )}
      <button
        type="button"
        onClick={onNormalize}
        disabled={!okSum}
        className="ml-auto text-ink-blue hover:underline disabled:opacity-40 disabled:no-underline"
      >
        归一化到 1
      </button>
      <button
        type="button"
        onClick={onReset}
        className="text-ink-3 hover:text-ink"
      >
        恢复默认
      </button>
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

function Select({
  value,
  onChange,
  options,
  small,
}: {
  value: number;
  onChange: (v: number) => void;
  options: { value: number; label: string }[];
  small?: boolean;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(parseInt(e.target.value, 10))}
      className={`border border-[var(--rule-strong)] rounded bg-card-2 ${
        small ? "px-2 py-1 text-xs" : "w-full px-3 py-2"
      }`}
    >
      {options.length === 0 && <option value={0}>—</option>}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
