/* Hallmark · macrostructure: Catalogue · theme: EvalKit Studio (custom) */

import Link from "next/link";
import { api, RegressionSetOut } from "@/lib/api";
import { PageShell } from "@/components/page-shell";

async function getSets(): Promise<RegressionSetOut[]> {
  return api<RegressionSetOut[]>("/api/regression-sets");
}

export default async function RegressionSetsPage() {
  const sets = await getSets();
  return (
    <PageShell
      eyebrow={{ label: "数据" }}
      title="回归集"
      lede="人工策划的必须能跑过的对话集合。新建评测时可选「仅跑回归集」，快速验证 prompt 或 bot 改动是否触发已知 bad pattern 的回归。"
      meta={`共 ${sets.length} 套`}
      actions={
        <Link
          href="/regression-sets/new"
          className="inline-flex items-center gap-2xs border-b border-accent pb-[1px] text-sm font-medium text-accent transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
        >
          新建回归集 <span aria-hidden>→</span>
        </Link>
      }
    >
      {sets.length === 0 ? (
        <div className="border-t border-rule py-2xl text-center text-lede italic-display text-ink-3">
          尚无回归集。点上方「新建回归集」开始。
        </div>
      ) : (
        <div className="min-w-0 overflow-x-auto border-t border-rule">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule text-caption uppercase tracking-[0.08em] text-ink-3">
                <th className="py-sm pr-md text-left font-normal">ID</th>
                <th className="py-sm pr-md text-left font-normal">名称</th>
                <th className="py-sm pr-md text-right font-normal">条数</th>
                <th className="py-sm text-right font-normal">创建</th>
              </tr>
            </thead>
            <tbody>
              {sets.map((s) => (
                <tr
                  key={s.id}
                  className="group border-b border-rule last:border-0 transition-colors duration-fast ease-out hover:bg-paper-2"
                >
                  <td className="py-sm pr-md font-mono tabular-nums text-ink-3">#{s.id}</td>
                  <td className="py-sm pr-md">
                    <Link
                      href={`/regression-sets/${s.id}`}
                      className="text-ink transition-colors duration-fast ease-out group-hover:text-accent"
                    >
                      {s.name}
                    </Link>
                    {s.description ? (
                      <div className="mt-2xs text-xs italic-display text-ink-3">{s.description}</div>
                    ) : null}
                  </td>
                  <td className="py-sm pr-md text-right font-mono tabular-nums">{s.item_count}</td>
                  <td className="py-sm text-right font-mono text-xs tabular-nums text-ink-3">
                    {new Date(s.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageShell>
  );
}
