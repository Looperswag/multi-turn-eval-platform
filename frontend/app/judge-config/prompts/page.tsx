/* Hallmark · macrostructure: Catalogue (6-dim grid variant) · theme: EvalKit Studio (custom) */

import Link from "next/link";
import { api } from "@/lib/api";
import PromptVersionRow from "@/components/prompts/prompt-version-row";
import { PageShell } from "@/components/page-shell";

type PromptVersion = {
  id: number;
  dimension_code: string;
  version_tag: string;
  weight: number;
  notes: string | null;
  is_active: boolean;
  parent_version_id: number | null;
  created_at: string;
  updated_at: string;
  in_use_count: number;
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

async function getPrompts(): Promise<PromptVersion[]> {
  return api<PromptVersion[]>("/api/judge-config/prompts");
}

export default async function PromptsPage() {
  const prompts = await getPrompts();
  const byDim: Record<string, PromptVersion[]> = {};
  for (const p of prompts) {
    (byDim[p.dimension_code] ||= []).push(p);
  }
  for (const code of Object.keys(byDim)) {
    byDim[code].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    );
  }

  return (
    <PageShell
      eyebrow={{ label: "配置" }}
      title="Prompt 版本管理"
      lede="六大维度的判官 prompt 历史版本。一旦被 run 引用即不可改，需克隆为新草稿后编辑；每个维度恒有一个 active 版本。"
      actions={
        <Link
          href="/judge-config/prompts/new"
          className="inline-flex items-center gap-2xs border-b border-accent pb-[1px] text-sm font-medium text-accent transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
        >
          新建草稿 <span aria-hidden>→</span>
        </Link>
      }
    >
      <div className="grid grid-cols-1 gap-x-xl gap-y-2xl border-t border-rule pt-lg md:grid-cols-2">
        {DIM_ORDER.map((code) => {
          const name = DIM_NAMES[code];
          const list = byDim[code] || [];
          const active = list.find((p) => p.is_active);
          const draftCount = list.filter(
            (p) => !p.is_active && p.parent_version_id !== null,
          ).length;
          return (
            <article key={code} className="flex flex-col gap-md">
              <header className="flex items-baseline justify-between gap-sm">
                <div className="min-w-0">
                  <div className="text-caption uppercase tracking-[0.08em] text-ink-3">
                    <span className="font-mono">{code}</span>
                  </div>
                  <div className="mt-2xs font-display text-h2 text-ink">{name}</div>
                </div>
                <div className="text-xs font-mono tabular-nums text-ink-3">
                  {list.length} 版本
                </div>
              </header>

              <div className="flex flex-wrap items-center gap-xs">
                {active ? (
                  <>
                    <span className="badge badge-pass font-mono">
                      Active · {active.version_tag}
                    </span>
                    <span className="text-xs italic-display text-ink-3">
                      权重 {active.weight}
                    </span>
                  </>
                ) : (
                  <span className="badge badge-warn">无 active 版本</span>
                )}
                {draftCount > 0 && (
                  <span className="badge badge-info">{draftCount} 草稿</span>
                )}
              </div>

              {active?.notes && (
                <p className="border-l-2 border-rule-strong pl-md text-xs leading-relaxed text-ink-2 line-clamp-3">
                  {active.notes}
                </p>
              )}

              <div className="flex flex-wrap items-center gap-md border-t border-rule pt-sm text-sm">
                {active && (
                  <Link
                    href={`/judge-config/prompts/${active.id}`}
                    className="border-b border-rule pb-[1px] text-ink-2 transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
                  >
                    查看 active <span aria-hidden>→</span>
                  </Link>
                )}
                <Link
                  href={`/judge-config/prompts/new?dim=${code}`}
                  className="ml-auto border-b border-rule pb-[1px] text-ink-3 transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
                >
                  新建草稿
                </Link>
              </div>

              {list.length > 0 && (
                <details className="text-xs" open={list.length <= 4}>
                  <summary className="cursor-pointer select-none text-ink-3 transition-colors duration-fast ease-out hover:text-ink">
                    所有版本 · {list.length}
                  </summary>
                  <ul className="mt-xs list-none p-0">
                    {list.map((p) => (
                      <PromptVersionRow key={p.id} p={p} />
                    ))}
                  </ul>
                </details>
              )}
            </article>
          );
        })}
      </div>
    </PageShell>
  );
}
