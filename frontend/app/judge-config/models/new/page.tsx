"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

const PROVIDER_OPTIONS = [
  { value: "ark", label: "ark（火山方舟）" },
  { value: "deepseek", label: "deepseek（Anthropic 兼容端点）" },
  { value: "anthropic", label: "anthropic" },
  { value: "openai", label: "openai" },
];

export default function NewJudgeModelPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    name: "",
    provider: "ark",
    model_id: "",
    temperature: 0.1,
    max_tokens: "" as string,
    is_default: false,
  });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const created = await api<{ id: number }>("/api/judge-config/models", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          provider: form.provider,
          model_id: form.model_id,
          temperature: form.temperature,
          max_tokens: form.max_tokens ? parseInt(form.max_tokens, 10) : null,
          is_default: form.is_default,
        }),
      });
      router.push(`/judge-config/models/${created.id}`);
    } catch (err) {
      alert("注册失败：" + (err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-[700px]">
      <div className="mb-8">
        <div className="uppercase-label text-ink-3 mb-2">
          配置 / Judge 模型 / 新建
        </div>
        <h1 className="font-display text-4xl font-medium tracking-tight">注册新 Judge 模型</h1>
        <p className="text-ink-2 mt-2">
          为评测任务登记一个 LLM judge。provider 与 model_id 创建后不可修改（避免破坏历史 eval_run 引用）。
        </p>
      </div>

      <form onSubmit={submit} className="space-y-6">
        <Field label="模型展示名称">
          <input
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            placeholder="e.g. Doubao Seed 2.0 Pro"
          />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Provider">
            <select
              value={form.provider}
              onChange={(e) => setForm({ ...form, provider: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            >
              {PROVIDER_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Model ID">
            <input
              required
              value={form.model_id}
              onChange={(e) => setForm({ ...form, model_id: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 font-mono-feat"
              placeholder="e.g. doubao-seed-2-0-pro-260215"
            />
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Temperature">
            <input
              type="number"
              step={0.1}
              min={0}
              max={2}
              value={form.temperature}
              onChange={(e) => setForm({ ...form, temperature: parseFloat(e.target.value) })}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 font-mono-feat"
            />
          </Field>
          <Field label="Max Tokens（可空）">
            <input
              type="number"
              min={1}
              value={form.max_tokens}
              onChange={(e) => setForm({ ...form, max_tokens: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 font-mono-feat"
              placeholder="留空使用 provider 默认"
            />
          </Field>
        </div>

        <Field label="">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
            />
            <span className="text-ink">设为默认 judge 模型</span>
            <span className="text-ink-3 text-xs">（其他模型会自动取消默认状态）</span>
          </label>
        </Field>

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
            {submitting ? "注册中…" : "注册模型"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      {label && <span className="block uppercase-label text-ink-3 mb-1.5">{label}</span>}
      {children}
    </label>
  );
}
