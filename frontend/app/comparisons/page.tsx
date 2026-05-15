import Link from "next/link";
import { api, type ComparisonOut } from "@/lib/api";

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
    <div className="max-w-[1200px]">
      <div className="mb-8">
        <div className="uppercase-label text-ink-3 mb-2">对比 / 列表</div>
        <h1 className="font-display text-4xl font-medium tracking-tight mb-2">对比任务</h1>
        <p className="text-ink-2 max-w-2xl">
          Prompt / Bot / Judge 模型三类机评对比，结果含 6 维差异、Movement 双视图、Cohen&apos;s κ 一致率。
          创建即时计算（同步 &lt; 1s for 100 case）；后续若两 run 重跑，详情页会自动失效缓存重算。
        </p>
      </div>

      <div className="mb-6 flex justify-end">
        <Link
          href="/comparisons/new"
          className="inline-flex items-center px-4 py-2 bg-moss text-white text-sm font-medium rounded hover:opacity-90 transition-opacity"
        >
          + 新建对比
        </Link>
      </div>

      <div className="bg-card border border-[var(--rule)] rounded">
        {items.length === 0 ? (
          <div className="px-8 py-16 text-center text-ink-3">
            还没有对比任务。<Link className="text-moss underline" href="/comparisons/new">创建一个</Link>。
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--rule)] text-ink-3 uppercase-label">
                <th className="px-5 py-3 text-left">ID</th>
                <th className="px-5 py-3 text-left">名称</th>
                <th className="px-5 py-3 text-left">类型</th>
                <th className="px-5 py-3 text-right">Run A → Run B</th>
                <th className="px-5 py-3 text-right">对齐样本</th>
                <th className="px-5 py-3 text-right">κ</th>
                <th className="px-5 py-3 text-right">创建时间</th>
                <th className="px-5 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} className="border-b border-[var(--rule)] last:border-0 hover:bg-[var(--bg)]">
                  <td className="px-5 py-3 font-mono-feat text-ink-3">#{c.id}</td>
                  <td className="px-5 py-3">
                    <Link href={`/comparisons/${c.id}`} className="text-ink hover:text-moss">
                      {c.name || `${c.type} #${c.id}`}
                    </Link>
                  </td>
                  <td className="px-5 py-3">
                    <span className="badge badge-info">{TYPE_LABEL[c.type] || c.type}</span>
                  </td>
                  <td className="px-5 py-3 text-right font-mono-feat tabular-nums">
                    #{c.run_a_id} → #{c.run_b_id ?? "—"}
                  </td>
                  <td className="px-5 py-3 text-right font-mono-feat">
                    {c.payload.aligned_count}
                  </td>
                  <td className="px-5 py-3 text-right font-mono-feat tabular-nums">
                    {c.payload.kappa == null ? "—" : c.payload.kappa.toFixed(3)}
                  </td>
                  <td className="px-5 py-3 text-right text-ink-3 text-xs">
                    {new Date(c.created_at).toLocaleString()}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <Link
                      href={`/comparisons/${c.id}`}
                      className="text-xs px-2 py-1 border border-[var(--rule-strong)] rounded hover:bg-moss hover:text-white hover:border-moss"
                    >
                      查看
                    </Link>
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
