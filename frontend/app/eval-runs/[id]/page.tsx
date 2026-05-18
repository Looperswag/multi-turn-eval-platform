import Link from "next/link";
import { api, type EvalRunDashboard } from "@/lib/api";
import { DimensionRadar } from "@/components/dimension-radar";
import { DimensionBar } from "@/components/dimension-bar";
import { ScoreDistribution } from "@/components/score-distribution";
import { LiveProgress } from "@/components/live-progress";

// 浏览器侧下载用的 origin（与 lib/api.ts 的 client 分支一致）
const BROWSER_API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function getDashboard(id: string): Promise<EvalRunDashboard | null> {
  try {
    return await api<EvalRunDashboard>(`/api/eval-runs/${id}/dashboard`);
  } catch (err) {
    // 真实的 "未找到 run" 仍然走这个 null 分支让页面给出友好提示；
    // 但其他错误打到 stderr，方便 docker compose logs web 排查。
    console.error(`[getDashboard ${id}]`, err);
    return null;
  }
}

export default async function EvalRunDashboardPage({ params }: { params: { id: string } }) {
  const dash = await getDashboard(params.id);
  if (!dash) {
    return (
      <div className="text-ink-3">
        run #{params.id} 未找到。 <Link href="/eval-runs" className="text-moss">返回列表</Link>
      </div>
    );
  }
  const { run, dimension_summary, score_distribution } = dash;
  const passColor = (run.weighted_score ?? 0) >= 0.6 ? "moss" : "tomato";
  const canExport = run.status === "success" || run.status === "partial";
  return (
    <div className="max-w-[1200px]">
      <div className="mb-2 text-ink-3 text-xs">
        <Link href="/eval-runs" className="text-ink-2 hover:text-ink">评测任务</Link> /
        <span className="ml-2">#{run.id}</span>
      </div>
      <div className="flex items-baseline gap-4 mb-2">
        <h1 className="font-display text-4xl font-medium tracking-tight">{run.name}</h1>
        <span className={`badge badge-${run.status === "success" ? "pass" : run.status === "failed" ? "fail" : "info"}`}>
          {run.status}
        </span>
      </div>
      <p className="text-ink-2 mb-8">{run.description || "—"}</p>

      {/* 实时进度：pending/running 期间持续订阅 SSE；
          partial/failed 终态且仍有失败 case 时，挂载组件以暴露"重试失败"按钮。 */}
      {(run.status === "pending" ||
        run.status === "running" ||
        ((run.status === "partial" || run.status === "failed") && run.failed > 0)) && (
        <LiveProgress
          runId={run.id}
          initial={{ completed: run.completed, total: run.total, failed: run.failed }}
          status={run.status as "pending" | "running" | "success" | "partial" | "failed" | "cancelled"}
        />
      )}

      <section className="grid grid-cols-3 gap-6 mb-10">
        <div className="bg-card border border-[var(--rule)] rounded p-6">
          <div className="uppercase-label text-ink-3 mb-3">加权总分</div>
          <div className={`font-display text-6xl font-medium tabular-nums text-${passColor}`}>
            {run.weighted_score == null ? "—" : run.weighted_score.toFixed(3)}
          </div>
          <div className="text-ink-3 text-xs mt-2">
            准出门槛 0.600 · {run.weighted_score == null ? "—" : (run.weighted_score >= 0.6 ? "通过" : "未通过")}
          </div>
        </div>
        <div className="bg-card border border-[var(--rule)] rounded p-6">
          <div className="uppercase-label text-ink-3 mb-3">通过率</div>
          <div className="font-display text-6xl font-medium tabular-nums text-ink">
            {run.pass_rate == null ? "—" : `${(run.pass_rate * 100).toFixed(1)}%`}
          </div>
          <div className="text-ink-3 text-xs mt-2">会话 weighted_score ≥ 0.6 的占比</div>
        </div>
        <div className="bg-card border border-[var(--rule)] rounded p-6">
          <div className="uppercase-label text-ink-3 mb-3">进度</div>
          <div className="font-display text-6xl font-medium tabular-nums text-ink">
            {run.completed}/{run.total}
          </div>
          <div className="text-ink-3 text-xs mt-2">
            失败 {run.failed} 条
          </div>
        </div>
      </section>

      <section className="grid grid-cols-[1fr_2fr] gap-6 mb-10">
        <div className="bg-card border border-[var(--rule)] rounded p-6">
          <div className="uppercase-label text-ink-3 mb-4">六维雷达</div>
          <DimensionRadar dimensions={dimension_summary} />
        </div>
        <div className="bg-card border border-[var(--rule)] rounded p-6">
          <div className="uppercase-label text-ink-3 mb-4">维度详情</div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-ink-3 uppercase-label border-b border-[var(--rule)]">
                <th className="text-left py-2">维度</th>
                <th className="text-right py-2">均值</th>
                <th className="text-right py-2">通过率</th>
                <th className="text-right py-2">样本</th>
                <th className="text-right py-2">min / max</th>
              </tr>
            </thead>
            <tbody>
              {dimension_summary.map((d) => (
                <tr key={d.dimension_code} className="border-b border-[var(--rule)] last:border-0">
                  <td className="py-2">
                    <div className="text-ink">{d.dimension_name}</div>
                    <div className="text-ink-3 text-xs font-mono-feat">{d.dimension_code}</div>
                  </td>
                  <td className="py-2 text-right font-mono-feat tabular-nums">
                    {d.avg_score == null ? "—" : d.avg_score.toFixed(3)}
                  </td>
                  <td className="py-2 text-right font-mono-feat tabular-nums">
                    {d.pass_rate == null ? "—" : `${(d.pass_rate * 100).toFixed(1)}%`}
                  </td>
                  <td className="py-2 text-right font-mono-feat tabular-nums text-ink-2">
                    {d.sample_count}
                  </td>
                  <td className="py-2 text-right font-mono-feat tabular-nums text-ink-3 text-xs">
                    {d.min_score == null ? "—" : `${d.min_score.toFixed(2)} / ${d.max_score?.toFixed(2)}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* 新增：维度分布柱状图 + 分数分布直方图 */}
      <section className="grid grid-cols-2 gap-6 mb-10">
        <div className="bg-card border border-[var(--rule)] rounded p-6">
          <div className="uppercase-label text-ink-3 mb-4">维度分布（柱状）</div>
          <DimensionBar dimensions={dimension_summary} />
        </div>
        <div className="bg-card border border-[var(--rule)] rounded p-6">
          <div className="uppercase-label text-ink-3 mb-4">加权分数分布（直方图）</div>
          <ScoreDistribution distribution={score_distribution} />
        </div>
      </section>

      <div className="flex gap-3 flex-wrap">
        {canExport && (
          <>
            <a
              href={`${BROWSER_API_BASE}/api/eval-runs/${run.id}/export?format=xlsx`}
              className="inline-flex items-center px-4 py-2 bg-moss text-white text-sm font-medium rounded hover:opacity-90 transition-opacity no-underline"
              title="完整 4-sheet 报告（含原始返回片段）"
            >
              ⬇ 导出 Excel
            </a>
            <a
              href={`${BROWSER_API_BASE}/api/eval-runs/${run.id}/export?format=md`}
              className="inline-flex items-center px-4 py-2 border border-[var(--rule-strong)] text-sm font-medium rounded hover:bg-moss hover:text-white hover:border-moss no-underline transition-colors"
              title="Markdown 报告（UTF-8，含中文）"
            >
              ⬇ 导出 MD
            </a>
            <a
              href={`${BROWSER_API_BASE}/api/eval-runs/${run.id}/export?format=pdf`}
              className="inline-flex items-center px-4 py-2 border border-[var(--rule-strong)] text-sm font-medium rounded hover:bg-moss hover:text-white hover:border-moss no-underline transition-colors"
              title="简易 PDF 报告（中文以 ? 占位，建议正式分发用 MD/Excel）"
            >
              ⬇ 导出 PDF
            </a>
          </>
        )}
        <Link
          href={`/eval-runs/${run.id}/badcases`}
          className="px-4 py-2 border border-[var(--rule-strong)] rounded text-sm hover:bg-[var(--rule)]"
        >
          钻取 Badcase
        </Link>
        <Link
          href={`/eval-runs/${run.id}/dimensions`}
          className="px-4 py-2 border border-[var(--rule-strong)] rounded text-sm hover:bg-[var(--rule)]"
        >
          维度详情
        </Link>
      </div>
    </div>
  );
}
