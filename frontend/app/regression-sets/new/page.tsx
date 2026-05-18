"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, RegressionSetOut } from "@/lib/api";

export default function NewRegressionSetPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setErr(null);
    try {
      const created = await api<RegressionSetOut>("/api/regression-sets", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
        }),
      });
      router.push(`/regression-sets/${created.id}`);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-[640px]">
      <div className="mb-8">
        <div className="uppercase-label text-ink-3 mb-2">回归集 / 新建</div>
        <h1 className="font-display text-4xl font-medium tracking-tight">新建回归集</h1>
        <p className="text-ink-2 mt-2 text-sm">
          创建后在 <code className="font-mono-feat">/eval-runs/[id]/badcases</code> 的
          Drawer 中可以把单条 case 加入；也可在详情页一键从 badcase 批量加入。
        </p>
      </div>

      <form onSubmit={submit} className="space-y-6">
        <Field label="名称">
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            placeholder="e.g. dim2-memory-loss-regression"
          />
        </Field>

        <Field label="描述（可选）">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            placeholder="该回归集的用途、收集规则…"
          />
        </Field>

        {err && <div className="text-sm text-tomato">{err}</div>}

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
            disabled={submitting || !name.trim()}
            className="px-5 py-2 bg-moss text-white text-sm rounded hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? "创建中…" : "创建"}
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
