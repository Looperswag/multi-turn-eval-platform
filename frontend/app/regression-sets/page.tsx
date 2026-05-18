import Link from "next/link";
import { api, RegressionSetOut } from "@/lib/api";

async function getSets(): Promise<RegressionSetOut[]> {
  return api<RegressionSetOut[]>("/api/regression-sets");
}

export default async function RegressionSetsPage() {
  const sets = await getSets();
  return (
    <div className="max-w-[1100px]">
      <div className="mb-8">
        <div className="uppercase-label text-ink-3 mb-2">数据 / 回归集</div>
        <h1 className="font-display text-4xl font-medium tracking-tight mb-2">回归集</h1>
        <p className="text-ink-2 max-w-2xl">
          人工策划的「必须能跑过」的对话集合。在新建评测任务时可选「仅跑回归集」，
          快速验证某一 prompt/bot 改动是否触发已知 bad pattern 的回归。
        </p>
      </div>

      <div className="mb-6 flex justify-end">
        <Link
          href="/regression-sets/new"
          className="inline-flex items-center px-4 py-2 bg-moss text-white text-sm font-medium rounded hover:opacity-90 transition-opacity"
        >
          + 新建回归集
        </Link>
      </div>

      <div className="bg-card border border-[var(--rule)] rounded">
        {sets.length === 0 ? (
          <div className="px-8 py-16 text-center text-ink-3">
            还没有回归集。点击右上角新建。
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--rule)] text-ink-3 uppercase-label">
                <th className="px-5 py-3 text-left">ID</th>
                <th className="px-5 py-3 text-left">名称</th>
                <th className="px-5 py-3 text-right">条数</th>
                <th className="px-5 py-3 text-right">创建时间</th>
              </tr>
            </thead>
            <tbody>
              {sets.map((s) => (
                <tr key={s.id} className="border-b border-[var(--rule)] last:border-0">
                  <td className="px-5 py-3 font-mono-feat text-ink-3">#{s.id}</td>
                  <td className="px-5 py-3">
                    <Link
                      href={`/regression-sets/${s.id}`}
                      className="text-moss hover:underline"
                    >
                      {s.name}
                    </Link>
                    {s.description && (
                      <div className="text-ink-3 text-xs">{s.description}</div>
                    )}
                  </td>
                  <td className="px-5 py-3 text-right font-mono-feat tabular-nums">
                    {s.item_count}
                  </td>
                  <td className="px-5 py-3 text-right text-ink-3 text-xs">
                    {new Date(s.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
