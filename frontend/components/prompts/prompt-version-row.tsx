"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export type PromptRowItem = {
  id: number;
  dimension_code: string;
  version_tag: string;
  weight: number;
  is_active: boolean;
  parent_version_id: number | null;
  in_use_count: number;
  updated_at: string;
};

export default function PromptVersionRow({ p }: { p: PromptRowItem }) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);

  // 业务规则（与 backend 一致）：
  //  - active 版本不能直接编辑/删除（先克隆）
  //  - 任何 in_use_count > 0 的版本被引用，不能编辑/删除（避免破坏历史 run）
  //  - draft 但未被引用：可以编辑/删除
  const editable = !p.is_active && p.in_use_count === 0;

  async function handleClone() {
    if (busy) return;
    setBusy("clone");
    try {
      const created = await api<{ id: number }>(
        `/api/judge-config/prompts/${p.id}/clone`,
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
    if (
      !confirm(
        `将 ${p.dimension_code}/${p.version_tag} 设为 active？\n同维度原 active 版本将自动取消。`,
      )
    )
      return;
    setBusy("activate");
    try {
      await api(`/api/judge-config/prompts/${p.id}/activate`, { method: "POST" });
      router.refresh();
    } catch (err) {
      alert("激活失败：" + (err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function handleDelete() {
    if (busy) return;
    if (!confirm(`确认删除草稿 ${p.dimension_code}/${p.version_tag}？此操作不可撤销。`))
      return;
    setBusy("delete");
    try {
      await api(`/api/judge-config/prompts/${p.id}`, { method: "DELETE" });
      router.refresh();
    } catch (err) {
      alert("删除失败：" + (err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const lockedTitle =
    p.is_active
      ? "active 版本受保护，请先激活其他版本再操作"
      : p.in_use_count > 0
        ? `已被 ${p.in_use_count} 个 run 引用，不能修改`
        : "";

  return (
    <li className="flex items-center gap-2 py-1.5 group">
      <Link
        href={`/judge-config/prompts/${p.id}`}
        className="font-mono-feat no-underline text-ink-2 hover:text-ink min-w-[64px]"
      >
        {p.version_tag}
      </Link>
      {p.is_active && <span className="badge badge-pass">Active</span>}
      {!p.is_active && p.in_use_count > 0 && (
        <span className="badge badge-neutral" title={`被 ${p.in_use_count} 个 run 引用`}>
          锁定 · {p.in_use_count}
        </span>
      )}
      {editable && p.parent_version_id !== null && (
        <span className="badge badge-info">草稿</span>
      )}
      <span className="text-ink-3 text-[11px] font-mono-feat ml-2">
        w={p.weight}
      </span>

      <span className="ml-auto inline-flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
        {!p.is_active && (
          <button
            type="button"
            onClick={handleActivate}
            disabled={busy !== null}
            className="text-[11px] px-2 py-0.5 rounded border border-[var(--rule-strong)] hover:bg-[var(--moss-bg)] text-moss disabled:opacity-50"
            title="设为该维度的 active"
          >
            {busy === "activate" ? "…" : "设为 Active"}
          </button>
        )}
        {editable ? (
          <Link
            href={`/judge-config/prompts/${p.id}/edit`}
            className="text-[11px] px-2 py-0.5 rounded border border-[var(--rule-strong)] hover:bg-card-2 text-ink-2 no-underline"
          >
            编辑
          </Link>
        ) : (
          <span
            className="text-[11px] px-2 py-0.5 rounded border border-[var(--rule)] text-ink-4 cursor-not-allowed"
            title={lockedTitle}
          >
            编辑
          </span>
        )}
        <button
          type="button"
          onClick={handleClone}
          disabled={busy !== null}
          className="text-[11px] px-2 py-0.5 rounded border border-[var(--rule-strong)] hover:bg-card-2 text-ink-2 disabled:opacity-50"
        >
          {busy === "clone" ? "…" : "克隆"}
        </button>
        {editable ? (
          <button
            type="button"
            onClick={handleDelete}
            disabled={busy !== null}
            className="text-[11px] px-2 py-0.5 rounded border border-[var(--rule-strong)] hover:bg-[#FDECEC] text-tomato disabled:opacity-50"
          >
            {busy === "delete" ? "…" : "删除"}
          </button>
        ) : (
          <span
            className="text-[11px] px-2 py-0.5 rounded border border-[var(--rule)] text-ink-4 cursor-not-allowed"
            title={lockedTitle}
          >
            删除
          </span>
        )}
      </span>
    </li>
  );
}
