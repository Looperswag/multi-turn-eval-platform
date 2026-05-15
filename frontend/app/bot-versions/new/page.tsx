"use client";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type BotVersion = { id: number; name: string; version_tag: string };

function defaultVersionTag() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `v1-${yyyy}-${mm}-${dd}`;
}

export default function NewBotVersionPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const suggested = useMemo(() => defaultVersionTag(), []);
  const [form, setForm] = useState({
    name: "",
    version_tag: suggested,
    description: "",
    bot_provider: "",
    base_model: "",
  });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const created = await api<BotVersion>("/api/bot-versions", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          version_tag: form.version_tag,
          description: form.description || null,
          bot_provider: form.bot_provider || null,
          base_model: form.base_model || null,
        }),
      });
      router.push(`/bot-versions/${created.id}`);
    } catch (err) {
      alert("创建失败：" + (err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-[800px]">
      <div className="mb-8">
        <div className="uppercase-label text-ink-3 mb-2">Bot 版本 / 新建</div>
        <h1 className="font-display text-4xl font-medium tracking-tight">新建 Bot 版本</h1>
        <p className="text-ink-2 mt-2">
          登记一个 bot 改写器版本。名称用于人工识别，version_tag 用于在评测任务里精确选择该版本。
        </p>
      </div>

      <form onSubmit={submit} className="space-y-6">
        <Field label="名称">
          <input
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            placeholder="e.g. Baseline bot"
          />
        </Field>

        <Field label="版本标签 (version_tag)">
          <input
            required
            value={form.version_tag}
            onChange={(e) => setForm({ ...form, version_tag: e.target.value })}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 font-mono-feat"
            placeholder={suggested}
          />
          <span className="block text-ink-3 text-xs mt-1">
            建议格式：<code className="font-mono-feat">v{`<n>`}-yyyy-mm-dd</code>，例如{" "}
            <code className="font-mono-feat">{suggested}</code>
          </span>
        </Field>

        <Field label="描述（可选）">
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={3}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            placeholder="该版本的改写策略、变更点、回归原因…"
          />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Bot Provider（可选）">
            <input
              value={form.bot_provider}
              onChange={(e) => setForm({ ...form, bot_provider: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
              placeholder="e.g. openai / anthropic / inhouse"
            />
          </Field>
          <Field label="基础模型（可选）">
            <input
              value={form.base_model}
              onChange={(e) => setForm({ ...form, base_model: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 font-mono-feat"
              placeholder="e.g. gpt-4o-mini"
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
            {submitting ? "创建中…" : "创建版本"}
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
