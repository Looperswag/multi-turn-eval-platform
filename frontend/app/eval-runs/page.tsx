import Link from "next/link";
import { api, type EvalRun } from "@/lib/api";
import { EvalRunsTrend } from "@/components/eval-runs-trend";

async function getRuns(): Promise<EvalRun[]> {
  return api<EvalRun[]>("/api/eval-runs");
}

// 浏览器侧下载用的 origin（与 lib/api.ts 的 client 分支一致）
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
    <div className="max-w-[1200px]">
      <div className="mb-8">
        <div className="uppercase-label text-ink-3 mb-2">评测 / 任务队列</div>
        <h1 className="font-display text-4xl font-medium tracking-tight mb-2">评测任务</h1>
        <p className="text-ink-2 max-w-2xl">
          每个 run 绑定一份评测集、一个 bot 版本、一套 prompt 版本和一个 judge 模型。
          创建后由 Celery worker 异步执行，可在详情页看实时进度。
        </p>
      </div>

      {/* 历史趋势 mini chart */}
      <div className="mb-6 bg-card border border-[var(--rule)] rounded">
        <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--rule)]">
          <div className="uppercase-label text-ink-3">加权总分历史趋势</div>
          <div className="text-ink-3 text-xs">
            {completedCount} 个已完成 run · 红线 = 准出门槛 0.6
          </div>
        </div>
        <EvalRunsTrend runs={runs} />
      </div>

      <div className="mb-6 flex justify-end">
        <Link
          href="/eval-runs/new"
          className="inline-flex items-center px-4 py-2 bg-moss text-white text-sm font-medium rounded hover:opacity-90 transition-opacity"
        >
          + 新建评测
        </Link>
      </div>

      <div className="bg-card border border-[var(--rule)] rounded">
        {runs.length === 0 ? (
          <div className="px-8 py-16 text-center text-ink-3">
            还没有评测任务。<Link className="text-moss underline" href="/eval-runs/new">创建一个</Link>。
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--rule)] text-ink-3 uppercase-label">
                <th className="px-5 py-3 text-left">ID</th>
                <th className="px-5 py-3 text-left">名称</th>
                <th className="px-5 py-3 text-left">状态</th>
                <th className="px-5 py-3 text-right">进度</th>
                <th className="px-5 py-3 text-right">加权总分</th>
                <th className="px-5 py-3 text-right">通过率</th>
                <th className="px-5 py-3 text-right">创建时间</th>
                <th className="px-5 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => {
                const canExport = r.status === "success" || r.status === "partial";
                return (
                  <tr key={r.id} className="border-b border-[var(--rule)] last:border-0 hover:bg-[var(--bg)]">
                    <td className="px-5 py-3 font-mono-feat text-ink-3">#{r.id}</td>
                    <td className="px-5 py-3">
                      <Link className="text-ink hover:text-moss" href={`/eval-runs/${r.id}`}>
                        {r.name}
                      </Link>
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="px-5 py-3 text-right font-mono-feat">
                      {r.completed}/{r.total}
                      {r.failed > 0 && <span className="text-tomato"> ·{r.failed}失败</span>}
                    </td>
                    <td className="px-5 py-3 text-right font-mono-feat tabular-nums">
                      {r.weighted_score == null ? "—" : r.weighted_score.toFixed(3)}
                    </td>
                    <td className="px-5 py-3 text-right font-mono-feat tabular-nums">
                      {r.pass_rate == null ? "—" : `${(r.pass_rate * 100).toFixed(1)}%`}
                    </td>
                    <td className="px-5 py-3 text-right text-ink-3 text-xs">
                      {new Date(r.created_at).toLocaleString()}
                    </td>
                    <td className="px-5 py-3 text-right">
                      {/* 列表导出仅 xlsx; 详情页可选 md/pdf */}
                      {canExport ? (
                        <a
                          href={`${BROWSER_API_BASE}/api/eval-runs/${r.id}/export?format=xlsx`}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs border border-[var(--rule-strong)] rounded hover:bg-moss hover:text-white hover:border-moss no-underline transition-colors"
                          title="导出 Excel 报告（详情页可选 MD/PDF）"
                        >
                          导出
                        </a>
                      ) : (
                        <span className="text-ink-3 text-xs">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
