import Link from "next/link";
import { api } from "@/lib/api";

type Dataset = {
  id: number;
  name: string;
  description: string | null;
  version: string;
  conversation_count: number;
  created_at: string;
};

async function getDatasets(): Promise<Dataset[]> {
  return api<Dataset[]>("/api/datasets");
}

export default async function DatasetsPage() {
  const datasets = await getDatasets();
  return (
    <div className="max-w-[1100px]">
      <div className="mb-8">
        <div className="uppercase-label text-ink-3 mb-2">数据 / 评测集</div>
        <h1 className="font-display text-4xl font-medium tracking-tight mb-2">评测集</h1>
        <p className="text-ink-2 max-w-2xl">
          原始多轮 query 集合。与 bot 改写解耦：同一个 dataset 可对接多个 bot 版本，从而支持「bot 模型横向对比」。
        </p>
      </div>

      <div className="mb-6 flex justify-end">
        <Link
          href="/datasets/upload"
          className="inline-flex items-center px-4 py-2 bg-moss text-white text-sm font-medium rounded hover:opacity-90 transition-opacity"
        >
          + 上传新评测集
        </Link>
      </div>

      <div className="bg-card border border-[var(--rule)] rounded">
        {datasets.length === 0 ? (
          <div className="px-8 py-16 text-center text-ink-3">
            还没有评测集。请运行 <code className="font-mono-feat bg-[var(--rule)] px-1.5">make seed</code> 灌入种子数据，或通过 API 上传。
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--rule)] text-ink-3 uppercase-label">
                <th className="px-5 py-3 text-left">ID</th>
                <th className="px-5 py-3 text-left">名称</th>
                <th className="px-5 py-3 text-left">版本</th>
                <th className="px-5 py-3 text-right">会话数</th>
                <th className="px-5 py-3 text-right">创建时间</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={d.id} className="border-b border-[var(--rule)] last:border-0">
                  <td className="px-5 py-3 font-mono-feat text-ink-3">#{d.id}</td>
                  <td className="px-5 py-3">
                    <div className="text-ink">{d.name}</div>
                    {d.description && <div className="text-ink-3 text-xs">{d.description}</div>}
                  </td>
                  <td className="px-5 py-3">
                    <span className="badge badge-neutral">{d.version}</span>
                  </td>
                  <td className="px-5 py-3 text-right font-mono-feat tabular-nums">{d.conversation_count}</td>
                  <td className="px-5 py-3 text-right text-ink-3 text-xs">
                    {new Date(d.created_at).toLocaleString()}
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
