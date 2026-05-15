"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

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

export default function NewEvalRunPage() {
  const router = useRouter();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [bots, setBots] = useState<BotVersion[]>([]);
  const [models, setModels] = useState<JudgeModel[]>([]);
  const [prompts, setPrompts] = useState<PromptVersion[]>([]);
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
  });

  useEffect(() => {
    Promise.all([
      api<Dataset[]>("/api/datasets"),
      api<BotVersion[]>("/api/bot-versions"),
      api<JudgeModel[]>("/api/judge-config/models"),
      api<PromptVersion[]>("/api/judge-config/prompts"),
    ])
      .then(([d, b, m, p]) => {
        setDatasets(d);
        setBots(b);
        setModels(m);
        setPrompts(p);
        const defaults: Record<string, number> = {};
        for (const dim of ["dim1", "dim2", "dim3", "dim4", "dim5", "dim6"]) {
          const v = p.find((x) => x.dimension_code === dim);
          if (v) defaults[dim] = v.id;
        }
        setForm((f) => ({
          ...f,
          dataset_id: d[0]?.id ?? 0,
          bot_version_id: b[0]?.id ?? 0,
          judge_model_id: m[0]?.id ?? 0,
          prompt_versions: defaults,
        }));
      })
      .catch(console.error);
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
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
          concurrency: form.concurrency,
          sampling_count: form.sampling_count ? parseInt(form.sampling_count, 10) : null,
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

        <Field label="维度与 Prompt 版本">
          <div className="border border-[var(--rule)] rounded divide-y divide-[var(--rule)]">
            {(["dim1", "dim2", "dim3", "dim4", "dim5", "dim6"] as const).map((dim) => (
              <label key={dim} className="flex items-center gap-4 px-4 py-3">
                <input
                  type="checkbox"
                  checked={form.dimensions.includes(dim)}
                  onChange={(e) => {
                    const next = e.target.checked
                      ? [...form.dimensions, dim]
                      : form.dimensions.filter((d) => d !== dim);
                    setForm({ ...form, dimensions: next });
                  }}
                />
                <span className="flex-1">
                  <span className="text-ink">{DIM_NAMES[dim]}</span>
                  <span className="text-ink-3 text-xs ml-2 font-mono-feat">{dim}</span>
                </span>
                <Select
                  value={form.prompt_versions[dim] ?? 0}
                  onChange={(v) => setForm({ ...form, prompt_versions: { ...form.prompt_versions, [dim]: v } })}
                  options={prompts
                    .filter((p) => p.dimension_code === dim)
                    .map((p) => ({ value: p.id, label: p.version_tag }))}
                  small
                />
              </label>
            ))}
          </div>
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
              onChange={(e) => setForm({ ...form, sampling_count: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
              placeholder="100"
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
