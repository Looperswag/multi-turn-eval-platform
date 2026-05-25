/* Hallmark · macrostructure: Catalogue · theme: EvalKit Studio (custom) */

import Link from "next/link";
import { api, type EvalRun } from "@/lib/api";
import { EvalRunsTrend } from "@/components/eval-runs-trend";
import { PageShell } from "@/components/page-shell";
import { SectionHead } from "@/components/section-head";

async function getRuns(): Promise<EvalRun[]> {
  return api<EvalRun[]>("/api/eval-runs");
}

const BROWSER_API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    success: "badge-pass",
    running: "badge-info",
    pending: "badge-neutral",
    partial: "badge-warn",
    failed: "badge-fail",
    cancelled: "badge-neutral",
  };
  return <span className={`badge ${map[status] || "badge-neutral"}`}>{status}</span>;
}

export default async function EvalRunsPage() {
  const runs = await getRuns();
  const completedCount = runs.filter(
    (r) => r.weighted_score != null && (r.status === "success" || r.status === "partial"),
  ).length;

  return (
    <PageShell
      eyebrow={{ label: "评测" }}
      title="评测任务"
      lede="每个 run 绑定一份评测集、一个 bot 版本、一套 prompt 版本与一个 judge 模型。创建后由 Celery worker 异步执行。"
      meta={`共 ${runs.length} 个 · 已完成 ${completedCount}`}
      actions={
        <Link
          href="/eval-runs/new"
          className="inline-flex items-center gap-2xs border-b border-accent pb-[1px] text-sm font-medium text-accent transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
        >
          新建评测 <span aria-hidden>→</span>
        </Link>
      }
    >
      <section className="flex flex-col gap-md">
        <SectionHead
          eyebrow="历史"
          title="加权总分趋势"
          caption="红线为准出门槛 0.6；横向序号 = run.id 升序。"
          meta={`${completedCount} 个已完成`}
        />
        <div className="min-w-0">
          <EvalRunsTrend runs={runs} />
        </div>
      </section>

      <section className="flex flex-col gap-md">
        <SectionHead eyebrow="队列" title="所有 run" />
        {runs.length === 0 ? (
          <div className="py-2xl text-center text-lede italic-display text-ink-3">
            尚无评测任务。
            <Link href="/eval-runs/new" className="ml-xs border-b border-rule pb-[1px] text-ink-2 hover:border-ink hover:text-ink">
              创建第一个 →
            </Link>
          </div>
        ) : (
          <div className="min-w-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-rule text-caption uppercase tracking-[0.08em] text-ink-3">
                  <th className="py-sm pr-md text-left font-normal">ID</th>
                  <th className="py-sm pr-md text-left font-normal">名称</th>
                  <th className="py-sm pr-md text-left font-normal">状态</th>
                  <th className="py-sm pr-md text-right font-normal">进度</th>
                  <th className="py-sm pr-md text-right font-normal">加权</th>
                  <th className="py-sm pr-md text-right font-normal">通过率</th>
                  <th className="py-sm pr-md text-right font-normal">创建</th>
                  <th className="py-sm text-right font-normal">导出</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => {
                  const canExport = r.status === "success" || r.status === "partial";
                  return (
                    <tr
                      key={r.id}
                      className="border-b border-rule last:border-0 transition-colors duration-fast ease-out hover:bg-paper-2"
                    >
                      <td className="py-sm pr-md font-mono tabular-nums text-ink-3">#{r.id}</td>
                      <td className="py-sm pr-md">
                        <Link
                          href={`/eval-runs/${r.id}`}
                          className="text-ink transition-colors duration-fast ease-out hover:text-accent"
                        >
                          {r.name}
                        </Link>
                      </td>
                      <td className="py-sm pr-md">
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="py-sm pr-md text-right font-mono tabular-nums">
                        {r.completed}<span className="text-ink-3">/{r.total}</span>
                        {r.failed > 0 && <span className="text-warn"> ·{r.failed}失败</span>}
                      </td>
                      <td className="py-sm pr-md text-right font-mono tabular-nums">
                        {r.weighted_score == null ? "—" : r.weighted_score.toFixed(3)}
                      </td>
                      <td className="py-sm pr-md text-right font-mono tabular-nums">
                        {r.pass_rate == null ? "—" : `${(r.pass_rate * 100).toFixed(1)}%`}
                      </td>
                      <td className="py-sm pr-md text-right font-mono text-xs tabular-nums text-ink-3">
                        {new Date(r.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-sm text-right">
                        {canExport ? (
                          <a
                            href={`${BROWSER_API_BASE}/api/eval-runs/${r.id}/export?format=xlsx`}
                            className="inline-flex items-center gap-2xs border-b border-rule pb-[1px] text-xs text-ink-2 transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
                          >
                            xlsx ↓
                          </a>
                        ) : (
                          <span className="text-xs text-ink-4">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </PageShell>
  );
}
