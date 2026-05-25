"use client";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

type PromptOut = {
  id: number;
  dimension_code: string;
  version_tag: string;
};

type PreviewResult = {
  rendered: string;
  vars_detected: string[];
  vars_used: string[];
  error: string | null;
};

const DIM_NAMES: Record<string, string> = {
  dim1: "改写忠实性",
  dim2: "跨轮记忆保留",
  dim3: "意图边界识别",
  dim4: "指代消解准确性",
  dim5: "重复请求处理",
  dim6: "用户纠错响应",
};

const DIM_ORDER = ["dim1", "dim2", "dim3", "dim4", "dim5", "dim6"];

export default function NewPromptPage() {
  return (
    <Suspense fallback={<div className="py-xl text-sm italic-display text-ink-3">载入中…</div>}>
      <NewPromptInner />
    </Suspense>
  );
}

function NewPromptInner() {
  const router = useRouter();
  const sp = useSearchParams();
  const initialDim = sp.get("dim") || "dim1";

  const [dimensionCode, setDimensionCode] = useState(initialDim);
  const [versionTag, setVersionTag] = useState("");
  const [template, setTemplate] = useState("");
  const [weight, setWeight] = useState("0.1");
  const [notes, setNotes] = useState("");
  const [strategy, setStrategy] = useState<
    "per_turn" | "session_returns_per_turn" | "session_single_score"
  >("per_turn");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [existing, setExisting] = useState<PromptOut[]>([]);

  useEffect(() => {
    api<PromptOut[]>(
      `/api/judge-config/prompts?dimension_code=${dimensionCode}`,
    )
      .then(setExisting)
      .catch(() => setExisting([]));
  }, [dimensionCode]);

  // ----- 实时预览：debounce 400ms 后调 /prompts/preview -----
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewSeq = useRef(0);

  useEffect(() => {
    if (!template.trim()) {
      setPreview(null);
      return;
    }
    const seq = ++previewSeq.current;
    setPreviewLoading(true);
    const timer = setTimeout(async () => {
      try {
        const res = await api<PreviewResult>(
          "/api/judge-config/prompts/preview",
          {
            method: "POST",
            body: JSON.stringify({
              template,
              dim_code: dimensionCode,
              strategy,
            }),
          },
        );
        if (seq === previewSeq.current) setPreview(res);
      } catch (err) {
        if (seq === previewSeq.current) {
          setPreview({
            rendered: "",
            vars_detected: [],
            vars_used: [],
            error: "预览请求失败：" + (err as Error).message,
          });
        }
      } finally {
        if (seq === previewSeq.current) setPreviewLoading(false);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [template, dimensionCode, strategy]);

  const suggestedTag = useMemo(() => {
    const nums = existing
      .map((p) => {
        const m = p.version_tag.match(/^v(\d+)$/);
        return m ? parseInt(m[1], 10) : null;
      })
      .filter((n): n is number => n !== null);
    const next = nums.length > 0 ? Math.max(...nums) + 1 : 1;
    return `v${next}`;
  }, [existing]);

  useEffect(() => {
    setVersionTag(suggestedTag);
  }, [suggestedTag]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const w = parseFloat(weight);
      const created = await api<{ id: number }>(
        "/api/judge-config/prompts",
        {
          method: "POST",
          body: JSON.stringify({
            dimension_code: dimensionCode,
            version_tag: versionTag,
            prompt_template: template,
            weight: Number.isNaN(w) ? 0 : w,
            notes: notes || null,
            dimension_strategy: strategy,
          }),
        },
      );
      router.push(`/judge-config/prompts/${created.id}`);
    } catch (err) {
      setError("创建失败：" + (err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-[1400px]">
      <div className="mb-6">
        <div className="uppercase-label text-ink-3 mb-2">
          <Link
            href="/judge-config/prompts"
            className="no-underline text-ink-3 hover:text-ink"
          >
            Prompt 版本
          </Link>
          <span className="mx-1.5">/</span>
          <span>新建草稿</span>
        </div>
        <h1 className="font-display text-3xl font-medium tracking-tight">
          新建 Prompt 草稿
        </h1>
        <p className="text-ink-2 mt-2 text-sm">
          草稿创建后为非 active 状态，未被引用前可继续编辑；进入 active 需到详情页激活。
        </p>
      </div>

      <form onSubmit={submit} className="space-y-6">
        <div className="grid grid-cols-2 gap-4">
          <Field label="维度">
            <select
              value={dimensionCode}
              onChange={(e) => setDimensionCode(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            >
              {DIM_ORDER.map((c) => (
                <option key={c} value={c}>
                  {DIM_NAMES[c]} ({c})
                </option>
              ))}
            </select>
          </Field>

          <Field label="版本标签 (version_tag)">
            <input
              required
              value={versionTag}
              onChange={(e) => setVersionTag(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 font-mono-feat"
              placeholder={suggestedTag}
            />
            <span className="block text-ink-3 text-xs mt-1">
              当前维度已有 {existing.length} 个版本，建议使用{" "}
              <code className="font-mono-feat">{suggestedTag}</code>
            </span>
          </Field>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-6">
          <Field label="Prompt 模板">
            <textarea
              required
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              rows={22}
              spellCheck={false}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 font-mono-feat text-xs leading-relaxed"
              style={{ tabSize: 2 }}
              placeholder="判官 prompt 模板正文…"
            />
          </Field>
          <PreviewPane
            template={template}
            preview={preview}
            loading={previewLoading}
          />
        </div>

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

          <Field label="评估调用策略">
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value as typeof strategy)}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            >
              <option value="per_turn">per_turn · 每轮调一次 judge</option>
              <option value="session_returns_per_turn">
                session_returns_per_turn · 一次调用返回每轮分
              </option>
              <option value="session_single_score">
                session_single_score · 一次调用返回单一分
              </option>
            </select>
            <span className="block text-ink-3 text-xs mt-1">
              dim1 默认 per_turn；用户自定义 session 级 prompt 选第二种；dim2 / dim6 选第三种。
            </span>
          </Field>
        </div>

        <Field label="备注（可选）">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            placeholder="该草稿的改动说明 / 实验目的…"
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
            {submitting ? "创建中…" : "创建草稿"}
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

function PreviewPane({
  template,
  preview,
  loading,
}: {
  template: string;
  preview: PreviewResult | null;
  loading: boolean;
}) {
  const hasTemplate = template.trim().length > 0;
  return (
    <div className="block">
      <div className="flex items-center justify-between mb-1.5">
        <span className="uppercase-label text-ink-3">渲染预览</span>
        <span className="text-[10px] text-ink-3 font-mono-feat">
          {loading
            ? "渲染中…"
            : preview && preview.vars_used.length > 0
              ? `vars: ${preview.vars_used.join(", ")}`
              : ""}
        </span>
      </div>
      <div className="border border-[var(--rule-strong)] rounded bg-card-2 overflow-hidden">
        {!hasTemplate && (
          <div className="px-3 py-8 text-xs text-ink-3 italic-display">
            在左侧输入模板即可实时预览（带样例 turns_text / meta_id / total_turns 等样本数据）
          </div>
        )}
        {hasTemplate && preview?.error && (
          <div className="border-b border-tomato/30 bg-tomato/5 px-3 py-2 text-xs text-tomato whitespace-pre-wrap">
            {preview.error}
          </div>
        )}
        {hasTemplate && preview?.rendered && (
          <pre className="m-0 px-3 py-2 font-mono-feat text-xs leading-relaxed whitespace-pre-wrap text-ink max-h-[28rem] overflow-auto">
            {preview.rendered}
          </pre>
        )}
        {hasTemplate && !preview?.rendered && !preview?.error && !loading && (
          <div className="px-3 py-8 text-xs text-ink-3 italic-display">无渲染输出</div>
        )}
      </div>
      <div className="mt-2 text-[10px] text-ink-3 leading-relaxed">
        样例上下文：3 轮多轮对话；可用变量：
        <code className="font-mono-feat">history_text</code> ·{" "}
        <code className="font-mono-feat">current_user_query</code> ·{" "}
        <code className="font-mono-feat">current_rewritten_query</code> ·{" "}
        <code className="font-mono-feat">turns_text</code> ·{" "}
        <code className="font-mono-feat">turns_text_with_meta</code> ·{" "}
        <code className="font-mono-feat">meta_id</code> ·{" "}
        <code className="font-mono-feat">total_turns</code>。未提供变量以{" "}
        <code className="font-mono-feat">«var»</code> 占位。
      </div>
    </div>
  );
}
