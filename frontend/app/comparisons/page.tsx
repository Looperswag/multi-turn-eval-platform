/* Hallmark · macrostructure: Catalogue · theme: EvalKit Studio (custom) */

import Link from "next/link";
import { api, type ComparisonOut } from "@/lib/api";
import { PageShell } from "@/components/page-shell";

async function getComparisons(): Promise<ComparisonOut[]> {
  try {
    return await api<ComparisonOut[]>("/api/comparisons");
  } catch (err) {
    console.error("[getComparisons]", err);
    return [];
  }
}

const TYPE_LABEL: Record<string, string> = {
  prompt: "Prompt 对比",
  bot: "Bot 对比",
  judge: "Judge 模型对比",
  human: "机评 vs 人工",
};

export default async function ComparisonsListPage() {
  const items = await getComparisons();
  return (
    <PageShell
      eyebrow={{ label: "对比" }}
      title="对比任务"
      lede="Prompt / Bot / Judge 三类机评对比，结果含六维差异、Movement 双视图、Cohen&apos;s κ 一致率。创建即时计算（同步 &lt; 1s for 100 case）。"
      meta={`共 ${items.length} 个`}
      actions={
        <Link
          href="/comparisons/new"
          className="inline-flex items-center gap-2xs border-b border-accent pb-[1px] text-sm font-medium text-accent transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
        >
          新建对比 <span aria-hidden>→</span>
        </Link>
      }
    >
      {items.length === 0 ? (
        <div className="border-t border-rule py-2xl text-center text-lede italic-display text-ink-3">
          尚无对比。
          <Link href="/comparisons/new" className="ml-xs border-b border-rule pb-[1px] text-ink-2 hover:border-ink hover:text-ink">
            创建第一个 →
          </Link>
        </div>
      ) : (
        <div className="min-w-0 overflow-x-auto border-t border-rule">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule text-caption uppercase tracking-[0.08em] text-ink-3">
                <th className="py-sm pr-md text-left font-normal">ID</th>
                <th className="py-sm pr-md text-left font-normal">名称</th>
                <th className="py-sm pr-md text-left font-normal">类型</th>
                <th className="py-sm pr-md text-right font-normal">A → B</th>
                <th className="py-sm pr-md text-right font-normal">对齐</th>
                <th className="py-sm pr-md text-right font-normal">κ</th>
                <th className="py-sm text-right font-normal">创建</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr
                  key={c.id}
                  className="group border-b border-rule last:border-0 transition-colors duration-fast ease-out hover:bg-paper-2"
                >
                  <td className="py-sm pr-md font-mono tabular-nums text-ink-3">#{c.id}</td>
                  <td className="py-sm pr-md">
                    <Link
                      href={`/comparisons/${c.id}`}
                      className="text-ink transition-colors duration-fast ease-out group-hover:text-accent"
                    >
                      {c.name || `${c.type} #${c.id}`}
                    </Link>
                  </td>
                  <td className="py-sm pr-md">
                    <span className="badge badge-info">{TYPE_LABEL[c.type] || c.type}</span>
                  </td>
                  <td className="py-sm pr-md text-right font-mono tabular-nums">
                    #{c.run_a_id} → #{c.run_b_id ?? "—"}
                  </td>
                  <td className="py-sm pr-md text-right font-mono tabular-nums">{c.payload.aligned_count}</td>
                  <td className="py-sm pr-md text-right font-mono tabular-nums">
                    {c.payload.kappa == null ? "—" : c.payload.kappa.toFixed(3)}
                  </td>
                  <td className="py-sm text-right font-mono text-xs tabular-nums text-ink-3">
                    {new Date(c.created_at).toLocaleDateString()}
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
