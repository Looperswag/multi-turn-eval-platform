"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";

type PromptDetail = {
  id: number;
  dimension_code: string;
  version_tag: string;
  prompt_template: string;
  weight: number;
  notes: string | null;
  is_active: boolean;
  parent_version_id: number | null;
};

export default function EditPromptPage() {
  const params = useParams<{ id: string }>();
  const id = parseInt(params.id, 10);
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [prompt, setPrompt] = useState<PromptDetail | null>(null);
  const [template, setTemplate] = useState("");
  const [weight, setWeight] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);
  const [cloning, setCloning] = useState(false);

  useEffect(() => {
    let alive = true;
    api<PromptDetail>(`/api/judge-config/prompts/${id}`)
      .then((p) => {
        if (!alive) return;
        setPrompt(p);
        setTemplate(p.prompt_template);
        setWeight(String(p.weight));
        setNotes(p.notes ?? "");
        setLoading(false);
      })
      .catch((err) => {
        if (!alive) return;
        setError("加载失败：" + (err as Error).message);
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [id]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!prompt) return;
    setSubmitting(true);
    setError(null);
    setConflict(null);
    try {
      const payload: Record<string, unknown> = {
        prompt_template: template,
        notes: notes || null,
      };
      const w = parseFloat(weight);
      if (!Number.isNaN(w)) payload.weight = w;
      await api(`/api/judge-config/prompts/${id}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      router.push(`/judge-config/prompts/${id}`);
    } catch (err) {
      const msg = (err as Error).message;
      if (msg.includes("409")) {
        setConflict("此版本已被引用，请克隆为新版本编辑");
      } else {
        setError("保存失败：" + msg);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function cloneAndEdit() {
    setCloning(true);
    try {
      const created = await api<{ id: number }>(
        `/api/judge-config/prompts/${id}/clone`,
        { method: "POST" },
      );
      router.push(`/judge-config/prompts/${created.id}/edit`);
    } catch (err) {
      setError("克隆失败：" + (err as Error).message);
    } finally {
      setCloning(false);
    }
  }

  if (loading) {
    return <div className="text-ink-3">加载中…</div>;
  }
  if (!prompt) {
    return <div className="text-tomato">{error || "未找到"}</div>;
  }

  return (
    <div className="max-w-[1000px]">
      <div className="mb-6">
        <div className="uppercase-label text-ink-3 mb-2">
          <Link
            href="/judge-config/prompts"
            className="no-underline text-ink-3 hover:text-ink"
          >
            Prompt 版本
          </Link>
          <span className="mx-1.5">/</span>
          <Link
            href={`/judge-config/prompts/${id}`}
            className="no-underline text-ink-3 hover:text-ink font-mono-feat"
          >
            #{id}
          </Link>
          <span className="mx-1.5">/</span>
          <span>编辑</span>
        </div>
        <h1 className="font-display text-3xl font-medium tracking-tight">
          编辑草稿 ·{" "}
          <span className="font-mono-feat text-ink-2">
            {prompt.dimension_code} {prompt.version_tag}
          </span>
        </h1>
        <p className="text-ink-2 mt-2 text-sm">
          仅未被引用的草稿可编辑。一旦被任何评测引用，本版本将自动锁定。
        </p>
      </div>

      {conflict && (
        <div className="bg-amber-bg border border-amber rounded p-4 mb-6 flex items-start gap-3">
          <div className="flex-1">
            <div className="text-amber font-medium">{conflict}</div>
            <div className="text-ink-2 text-xs mt-1">
              克隆后将基于此版本生成新草稿，可立即编辑。
            </div>
          </div>
          <button
            type="button"
            onClick={cloneAndEdit}
            disabled={cloning}
            className="shrink-0 px-3.5 py-1.5 bg-moss text-white rounded text-sm hover:opacity-90 disabled:opacity-50"
          >
            {cloning ? "克隆中…" : "立即克隆"}
          </button>
        </div>
      )}

      <form onSubmit={submit} className="space-y-6">
        <Field label="Prompt 模板">
          <textarea
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            rows={18}
            spellCheck={false}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 font-mono-feat text-xs leading-relaxed"
            style={{ tabSize: 2 }}
          />
        </Field>

        <div className="grid grid-cols-3 gap-4">
          <Field label="权重">
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 font-mono-feat"
            />
          </Field>
        </div>

        <Field label="备注（可选）">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            placeholder="该版本相对父版本的改动说明…"
          />
        </Field>

        {error && <div className="text-tomato text-sm">{error}</div>}

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
            {submitting ? "保存中…" : "保存"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block uppercase-label text-ink-3 mb-1.5">{label}</span>
      {children}
    </label>
  );
}
