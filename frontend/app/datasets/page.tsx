/* Hallmark · macrostructure: Catalogue · theme: EvalKit Studio (custom) */

import Link from "next/link";
import { api } from "@/lib/api";
import { PageShell } from "@/components/page-shell";

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
    <PageShell
      eyebrow={{ label: "数据" }}
      title="评测集"
      lede="原始多轮 query 集合。与 bot 改写解耦：同一份 dataset 可对接多个 bot 版本，从而支持 bot 模型横向对比。"
      meta={`共 ${datasets.length} 份`}
      actions={
        <Link
          href="/datasets/upload"
          className="inline-flex items-center gap-2xs border-b border-accent pb-[1px] text-sm font-medium text-accent transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
        >
          上传新评测集 <span aria-hidden>→</span>
        </Link>
      }
    >
      {datasets.length === 0 ? (
        <div className="border-t border-rule py-2xl text-center text-lede italic-display text-ink-3">
          尚无评测集。先跑 <code className="font-mono not-italic text-ink-2">make seed</code> 灌入种子，或上传一份。
        </div>
      ) : (
        <div className="min-w-0 overflow-x-auto border-t border-rule">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule text-caption uppercase tracking-[0.08em] text-ink-3">
                <th className="py-sm pr-md text-left font-normal">ID</th>
                <th className="py-sm pr-md text-left font-normal">名称</th>
                <th className="py-sm pr-md text-left font-normal">版本</th>
                <th className="py-sm pr-md text-right font-normal">会话数</th>
                <th className="py-sm text-right font-normal">创建</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr
                  key={d.id}
                  className="group border-b border-rule last:border-0 transition-colors duration-fast ease-out hover:bg-paper-2"
                >
                  <td className="py-sm pr-md">
                    <Link href={`/datasets/${d.id}`} className="block font-mono tabular-nums text-ink-3 transition-colors duration-fast ease-out group-hover:text-ink">
                      #{d.id}
                    </Link>
                  </td>
                  <td className="py-sm pr-md">
                    <Link href={`/datasets/${d.id}`} className="block">
                      <div className="text-ink transition-colors duration-fast ease-out group-hover:text-accent">
                        {d.name}
                      </div>
                      {d.description ? (
                        <div className="mt-2xs text-xs italic-display text-ink-3">{d.description}</div>
                      ) : null}
                    </Link>
                  </td>
                  <td className="py-sm pr-md">
                    <span className="badge badge-neutral font-mono">{d.version}</span>
                  </td>
                  <td className="py-sm pr-md text-right font-mono tabular-nums">{d.conversation_count}</td>
                  <td className="py-sm text-right font-mono text-xs tabular-nums text-ink-3">
                    {new Date(d.created_at).toLocaleDateString()}
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
