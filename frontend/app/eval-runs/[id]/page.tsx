/* Hallmark · macrostructure: Stat-Led · theme: EvalKit Studio (custom)
 * Anchor page. Weighted score is the primary hero number; meta strip follows;
 * radar + dim table second; dim bar + distribution third; exports/drilldown last.
 */

import Link from "next/link";
import { api, type EvalRunDashboard } from "@/lib/api";
import { DimensionRadar } from "@/components/dimension-radar";
import { DimensionBar } from "@/components/dimension-bar";
import { ScoreDistribution } from "@/components/score-distribution";
import { LiveProgress } from "@/components/live-progress";
import { PageShell } from "@/components/page-shell";
import { SectionHead } from "@/components/section-head";

const BROWSER_API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function getDashboard(id: string): Promise<EvalRunDashboard | null> {
  try {
    return await api<EvalRunDashboard>(`/api/eval-runs/${id}/dashboard`);
  } catch (err) {
    console.error(`[getDashboard ${id}]`, err);
    return null;
  }
}

function statusBadgeClass(status: string): string {
  if (status === "success") return "badge badge-pass";
  if (status === "failed") return "badge badge-fail";
  if (status === "partial") return "badge badge-warn";
  if (status === "cancelled") return "badge badge-neutral";
  return "badge badge-info";
}

export default async function EvalRunDashboardPage({ params }: { params: { id: string } }) {
  const dash = await getDashboard(params.id);
  if (!dash) {
    return (
      <PageShell title="未找到该评测" lede={`Run #${params.id} 不存在或已被删除。`}>
        <div className="border-t border-rule pt-md text-sm text-ink-2">
          <Link href="/eval-runs" className="border-b border-rule pb-[1px] hover:border-ink hover:text-ink">
            ← 返回评测任务
          </Link>
        </div>
      </PageShell>
    );
  }

  const { run, dimension_summary, score_distribution } = dash;
  const score = run.weighted_score;
  const passed = score != null && score >= 0.6;
  const showProgress =
    run.status === "pending" ||
    run.status === "running" ||
    ((run.status === "partial" || run.status === "failed") && run.failed > 0);
  const canExport = run.status === "success" || run.status === "partial";

  const createdShort = run.created_at?.replace("T", " ").slice(0, 16) ?? "—";

  return (
    <div className="mx-auto flex max-w-[1200px] min-w-0 flex-col gap-3xl pb-4xl">
      {/* breadcrumb */}
      <nav aria-label="Breadcrumb" className="text-caption uppercase tracking-[0.08em] text-ink-3">
        <Link href="/eval-runs" className="text-ink-3 transition-colors duration-fast ease-out hover:text-ink">
          评测任务
        </Link>
        <span aria-hidden className="px-xs text-ink-4">/</span>
        <span className="font-mono tracking-normal text-ink-2">#{run.id}</span>
      </nav>

      {/* ── Hero · the primary stat ───────────────────────────── */}
      <header className="flex flex-col gap-md">
        <div className="flex flex-wrap items-baseline gap-md">
          <h1 className="m-0 font-display text-display-s text-ink">{run.name}</h1>
          <span className={statusBadgeClass(run.status)}>{run.status}</span>
        </div>
        <div className="grid grid-cols-1 gap-xl border-t border-rule pt-lg md:grid-cols-[auto_minmax(0,1fr)]">
          <div className="flex flex-col gap-2xs">
            <span className="text-caption uppercase tracking-[0.08em] text-ink-3">加权总分</span>
            <span
              className="font-display tabular-nums leading-none"
              style={{
                fontSize: "var(--text-display)",
                color: passed ? "var(--color-accent)" : "var(--color-warn)",
              }}
            >
              {score == null ? "—" : score.toFixed(3)}
            </span>
            <span className="font-mono text-xs tabular-nums text-ink-3">
              准出 0.600 · {score == null ? "—" : passed ? "通过" : "未通过"}
            </span>
          </div>
          <dl className="grid grid-cols-2 content-end gap-y-sm text-sm md:grid-cols-3 md:gap-x-xl">
            <div className="flex flex-col gap-2xs">
              <dt className="text-caption uppercase tracking-[0.08em] text-ink-3">通过率</dt>
              <dd className="m-0 font-mono tabular-nums text-h3 text-ink">
                {run.pass_rate == null ? "—" : `${(run.pass_rate * 100).toFixed(1)}%`}
              </dd>
            </div>
            <div className="flex flex-col gap-2xs">
              <dt className="text-caption uppercase tracking-[0.08em] text-ink-3">完成</dt>
              <dd className="m-0 font-mono tabular-nums text-h3 text-ink">
                {run.completed}<span className="text-ink-3">/{run.total}</span>
              </dd>
            </div>
            <div className="flex flex-col gap-2xs">
              <dt className="text-caption uppercase tracking-[0.08em] text-ink-3">失败</dt>
              <dd className="m-0 font-mono tabular-nums text-h3 text-ink">
                {run.failed}
              </dd>
            </div>
            <div className="flex flex-col gap-2xs md:col-span-3">
              <dt className="text-caption uppercase tracking-[0.08em] text-ink-3">创建于</dt>
              <dd className="m-0 font-mono text-sm tabular-nums text-ink-2">{createdShort}</dd>
            </div>
          </dl>
        </div>
      </header>

      {showProgress && (
        <LiveProgress
          runId={run.id}
          initial={{ completed: run.completed, total: run.total, failed: run.failed }}
          status={run.status as "pending" | "running" | "success" | "partial" | "failed" | "cancelled"}
        />
      )}

      {/* ── Section · 六维 ─────────────────────────────────────── */}
      <section className="flex flex-col gap-lg">
        <SectionHead
          eyebrow="维度"
          title="六维表现"
          caption="改写忠实 · 跨轮记忆 · 意图边界 · 指代消解 · 重复请求 · 纠错响应"
        />
        <div className="grid grid-cols-1 gap-xl lg:grid-cols-[5fr_7fr]">
          <div className="min-w-0">
            <DimensionRadar dimensions={dimension_summary} />
          </div>
          <div className="min-w-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-rule text-caption uppercase tracking-[0.08em] text-ink-3">
                  <th className="py-xs text-left font-normal">维度</th>
                  <th className="py-xs text-right font-normal">均值</th>
                  <th className="py-xs text-right font-normal">通过率</th>
                  <th className="py-xs text-right font-normal">样本</th>
                  <th className="py-xs text-right font-normal">min / max</th>
                </tr>
              </thead>
              <tbody>
                {dimension_summary.map((d) => {
                  const enabled = d.avg_score != null;
                  return (
                    <tr
                      key={d.dimension_code}
                      className="border-b border-rule last:border-0 transition-colors duration-fast ease-out hover:bg-paper-2"
                    >
                      <td className="py-sm">
                        <div className="text-ink">{d.dimension_name}</div>
                        <div className="font-mono text-xs text-ink-3">{d.dimension_code}</div>
                      </td>
                      <td className="py-sm text-right font-mono tabular-nums" colSpan={enabled ? 1 : 4}>
                        {enabled ? (
                          d.avg_score!.toFixed(3)
                        ) : (
                          <span className="badge badge-neutral text-[10px]">未启用</span>
                        )}
                      </td>
                      {enabled && (
                        <>
                          <td className="py-sm text-right font-mono tabular-nums">
                            {d.pass_rate == null ? "—" : `${(d.pass_rate * 100).toFixed(1)}%`}
                          </td>
                          <td className="py-sm text-right font-mono tabular-nums text-ink-2">
                            {d.sample_count}
                          </td>
                          <td className="py-sm text-right font-mono text-xs tabular-nums text-ink-3">
                            {d.min_score == null
                              ? "—"
                              : `${d.min_score.toFixed(2)} / ${d.max_score?.toFixed(2) ?? "—"}`}
                          </td>
                        </>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── Section · 分布 ─────────────────────────────────────── */}
      <section className="flex flex-col gap-lg">
        <SectionHead eyebrow="分布" title="维度柱状 · 总分直方" />
        <div className="grid grid-cols-1 gap-xl lg:grid-cols-2">
          <div className="min-w-0">
            <DimensionBar dimensions={dimension_summary} />
          </div>
          <div className="min-w-0">
            <ScoreDistribution distribution={score_distribution} />
          </div>
        </div>
      </section>

      {/* ── Footer · drilldown + exports (link-style) ─────────── */}
      <section className="flex flex-col gap-md border-t border-rule pt-lg">
        <div className="text-caption uppercase tracking-[0.08em] text-ink-3">下一步</div>
        <div className="flex flex-wrap items-center gap-x-xl gap-y-md text-sm">
          <Link
            href={`/eval-runs/${run.id}/sessions`}
            className="inline-flex items-center gap-2xs border-b border-rule pb-[1px] text-ink transition-colors duration-fast ease-out hover:border-ink"
          >
            Sessions 概览 <span aria-hidden>→</span>
          </Link>
          <Link
            href={`/eval-runs/${run.id}/badcases`}
            className="inline-flex items-center gap-2xs border-b border-rule pb-[1px] text-ink transition-colors duration-fast ease-out hover:border-ink"
          >
            钻取 Badcase <span aria-hidden>→</span>
          </Link>
          <Link
            href={`/eval-runs/${run.id}/dimensions`}
            className="inline-flex items-center gap-2xs border-b border-rule pb-[1px] text-ink transition-colors duration-fast ease-out hover:border-ink"
          >
            维度详情 <span aria-hidden>→</span>
          </Link>
          {canExport && (
            <>
              <span aria-hidden className="text-ink-4">·</span>
              <a
                href={`${BROWSER_API_BASE}/api/eval-runs/${run.id}/export?format=xlsx`}
                className="inline-flex items-center gap-2xs border-b border-accent pb-[1px] text-accent transition-colors duration-fast ease-out hover:text-ink hover:border-ink"
                title="完整 4-sheet 报告"
              >
                导出 Excel <span aria-hidden>↓</span>
              </a>
              <a
                href={`${BROWSER_API_BASE}/api/eval-runs/${run.id}/export?format=md`}
                className="inline-flex items-center gap-2xs border-b border-rule pb-[1px] text-ink-2 transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
                title="Markdown 报告"
              >
                导出 MD <span aria-hidden>↓</span>
              </a>
              <a
                href={`${BROWSER_API_BASE}/api/eval-runs/${run.id}/export?format=pdf`}
                className="inline-flex items-center gap-2xs border-b border-rule pb-[1px] text-ink-2 transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
                title="简易 PDF（中文以占位符显示）"
              >
                导出 PDF <span aria-hidden>↓</span>
              </a>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
