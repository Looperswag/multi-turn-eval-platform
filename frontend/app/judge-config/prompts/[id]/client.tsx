"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type PerformanceItem = {
  eval_run_id: number;
  run_name: string;
  weighted_score: number | null;
  dim_score: number | null;
  used_at: string;
};

type Performance = {
  prompt_version_id: number;
  dimension_code: string;
  version_tag: string;
  is_active: boolean;
  in_use_count: number;
  avg_weighted_score: number | null;
  avg_dim_score: number | null;
  items: PerformanceItem[];
};

type Sibling = {
  id: number;
  version_tag: string;
  is_active: boolean;
  parent_version_id: number | null;
  updated_at: string;
};

export function PromptDetailClient({
  promptId,
  isActive,
  isDraft,
  isLocked,
  promptTemplate,
  notes,
  performance,
  siblings,
  dimName,
}: {
  promptId: number;
  isActive: boolean;
  isDraft: boolean;
  isLocked: boolean;
  promptTemplate: string;
  notes: string | null;
  performance: Performance;
  siblings: Sibling[];
  dimName: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function handleClone() {
    if (busy) return;
    setBusy("clone");
    try {
      const created = await api<{ id: number }>(
        `/api/judge-config/prompts/${promptId}/clone`,
        { method: "POST" },
      );
      router.push(`/judge-config/prompts/${created.id}`);
    } catch (err) {
      alert("克隆失败：" + (err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function handleActivate() {
    if (busy) return;
    if (!confirm(`将该 prompt 设为 ${dimName} 维度的 active 版本？\n同维度原 active 版本将自动取消。`))
      return;
    setBusy("activate");
    try {
      await api(`/api/judge-config/prompts/${promptId}/activate`, {
        method: "POST",
      });
      router.refresh();
    } catch (err) {
      alert("设为 active 失败：" + (err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function handleDelete() {
    if (busy) return;
    if (!confirm("确认删除该草稿？此操作不可撤销。")) return;
    setBusy("delete");
    try {
      await api(`/api/judge-config/prompts/${promptId}`, { method: "DELETE" });
      router.push("/judge-config/prompts");
    } catch (err) {
      alert("删除失败：" + (err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function copyTemplate() {
    try {
      await navigator.clipboard.writeText(promptTemplate);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // ignore
    }
  }

  const lines = promptTemplate.split("\n");

  return (
    <>
      {/* 操作按钮区 */}
      <div className="bg-card border border-[var(--rule)] rounded p-4 mb-6 flex items-center gap-3 flex-wrap">
        <span className="uppercase-label text-ink-3 mr-2">操作</span>

        {isDraft && (
          <Link
            href={`/judge-config/prompts/${promptId}/edit`}
            className="px-3.5 py-1.5 border border-[var(--rule-strong)] rounded text-sm no-underline text-ink hover:bg-card-2"
          >
            编辑
          </Link>
        )}

        <button
          type="button"
          onClick={handleClone}
          disabled={busy !== null}
          className="px-3.5 py-1.5 border border-[var(--rule-strong)] rounded text-sm hover:bg-card-2 disabled:opacity-50"
        >
          {busy === "clone" ? "克隆中…" : "克隆为新版"}
        </button>

        {!isActive && (
          <button
            type="button"
            onClick={handleActivate}
            disabled={busy !== null}
            className="px-3.5 py-1.5 bg-moss text-white rounded text-sm hover:opacity-90 disabled:opacity-50"
          >
            {busy === "activate" ? "激活中…" : "设为 Active"}
          </button>
        )}

        {isDraft && (
          <button
            type="button"
            onClick={handleDelete}
            disabled={busy !== null}
            className="ml-auto px-3.5 py-1.5 border border-[var(--rule-strong)] rounded text-sm text-tomato hover:bg-tomato-bg disabled:opacity-50"
          >
            {busy === "delete" ? "删除中…" : "删除"}
          </button>
        )}

        {isLocked && (
          <span className="ml-auto text-ink-3 text-xs">
            该版本已被引用，仅可克隆为新版
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        {/* 左列：Prompt 全文 + Notes */}
        <div className="space-y-6">
          <section className="bg-card border border-[var(--rule)] rounded">
            <div className="px-5 py-3 border-b border-[var(--rule)] flex items-center justify-between">
              <div className="uppercase-label text-ink-2">Prompt 全文</div>
              <button
                type="button"
                onClick={copyTemplate}
                className="text-xs text-ink-3 hover:text-ink"
              >
                {copied ? "已复制" : "复制"}
              </button>
            </div>
            <div className="overflow-x-auto">
              <pre className="font-mono-feat text-xs leading-relaxed text-ink m-0 px-0 py-4 whitespace-pre">
                {lines.map((line, i) => (
                  <div key={i} className="flex">
                    <span className="select-none text-ink-4 text-right pr-3 pl-5 min-w-[3.5rem]">
                      {i + 1}
                    </span>
                    <span className="flex-1 pr-5">{line || " "}</span>
                  </div>
                ))}
              </pre>
            </div>
          </section>

          {notes && (
            <section className="bg-card border border-[var(--rule)] rounded p-5">
              <div className="uppercase-label text-ink-2 mb-2">备注</div>
              <p className="text-ink-2 whitespace-pre-wrap leading-relaxed">
                {notes}
              </p>
            </section>
          )}

          {/* 评分沉淀 */}
          <section className="bg-card border border-[var(--rule)] rounded">
            <div className="px-5 py-3 border-b border-[var(--rule)]">
              <div className="uppercase-label text-ink-2">评分沉淀</div>
            </div>
            <div className="px-5 py-4 grid grid-cols-3 gap-5 border-b border-[var(--rule)]">
              <StatBlock
                label="被引用次数"
                value={performance.in_use_count.toString()}
                tone="ink"
              />
              <StatBlock
                label="平均 weighted"
                value={fmt(performance.avg_weighted_score)}
                tone="moss"
              />
              <StatBlock
                label={`平均 ${performance.dimension_code} 维度分`}
                value={fmt(performance.avg_dim_score)}
                tone="ink-blue"
              />
            </div>

            {performance.items.length === 0 ? (
              <div className="px-5 py-10 text-center text-ink-3 text-sm">
                尚未被任何 eval run 引用
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-ink-3 uppercase-label border-b border-[var(--rule)]">
                    <th className="px-5 py-2 text-left">Run</th>
                    <th className="px-5 py-2 text-right">维度分</th>
                    <th className="px-5 py-2 text-right">Weighted</th>
                    <th className="px-5 py-2 text-right">时间</th>
                  </tr>
                </thead>
                <tbody>
                  {performance.items.map((item) => (
                    <tr
                      key={item.eval_run_id}
                      className="border-b border-[var(--rule)] last:border-0"
                    >
                      <td className="px-5 py-2.5">
                        <Link
                          href={`/eval-runs/${item.eval_run_id}`}
                          className="no-underline text-ink hover:text-ink-blue"
                        >
                          {item.run_name}
                        </Link>
                        <div className="text-ink-3 text-xs font-mono-feat">
                          #{item.eval_run_id}
                        </div>
                      </td>
                      <td className="px-5 py-2.5 text-right font-mono-feat tabular-nums">
                        {fmt(item.dim_score)}
                      </td>
                      <td className="px-5 py-2.5 text-right font-mono-feat tabular-nums">
                        {fmt(item.weighted_score)}
                      </td>
                      <td className="px-5 py-2.5 text-right text-ink-3 text-xs">
                        {new Date(item.used_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>

        {/* 右列：历史时间线 */}
        <aside className="space-y-6">
          <section className="bg-card border border-[var(--rule)] rounded">
            <div className="px-5 py-3 border-b border-[var(--rule)]">
              <div className="uppercase-label text-ink-2">历史时间线</div>
              <div className="text-ink-3 text-xs mt-0.5">
                同维度 {siblings.length} 个版本
              </div>
            </div>
            <ul className="px-2 py-2">
              {siblings.map((s) => {
                const isCurrent = s.id === promptId;
                return (
                  <li key={s.id}>
                    <Link
                      href={`/judge-config/prompts/${s.id}`}
                      className={
                        "block px-3 py-2.5 rounded no-underline " +
                        (isCurrent
                          ? "bg-[var(--rule)] text-ink"
                          : "text-ink-2 hover:bg-[var(--rule)]")
                      }
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-mono-feat text-sm">
                          {s.version_tag}
                        </span>
                        {s.is_active && (
                          <span className="badge badge-pass">Active</span>
                        )}
                        {!s.is_active && s.parent_version_id !== null && (
                          <span className="badge badge-info">草稿</span>
                        )}
                        {isCurrent && (
                          <span className="ml-auto text-ink-3 text-xs">
                            当前
                          </span>
                        )}
                      </div>
                      <div className="text-ink-3 text-xs mt-0.5">
                        {new Date(s.updated_at).toLocaleString()}
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        </aside>
      </div>
    </>
  );
}

function fmt(n: number | null): string {
  if (n === null || n === undefined) return "—";
  return n.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
}

function StatBlock({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "moss" | "ink-blue" | "ink";
}) {
  const color =
    tone === "moss"
      ? "text-moss"
      : tone === "ink-blue"
        ? "text-ink-blue"
        : "text-ink";
  return (
    <div>
      <div className="uppercase-label text-ink-3 mb-1.5">{label}</div>
      <div
        className={"font-display text-3xl font-medium tabular-nums " + color}
      >
        {value}
      </div>
    </div>
  );
}
