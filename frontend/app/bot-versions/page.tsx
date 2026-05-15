import Link from "next/link";
import { api } from "@/lib/api";

type BotVersion = {
  id: number;
  name: string;
  version_tag: string;
  description: string | null;
  bot_provider: string | null;
  base_model: string | null;
  created_at: string;
};

async function getBotVersions(): Promise<BotVersion[]> {
  return api<BotVersion[]>("/api/bot-versions");
}

export default async function BotVersionsPage() {
  const bots = await getBotVersions();
  return (
    <div className="max-w-[1100px]">
      <div className="flex items-start justify-between mb-8 gap-6">
        <div>
          <div className="uppercase-label text-ink-3 mb-2">数据 / Bot 版本</div>
          <h1 className="font-display text-4xl font-medium tracking-tight mb-2">Bot 版本</h1>
          <p className="text-ink-2 max-w-2xl">
            Bot 改写器的版本登记。每个 bot 版本可对接多份 dataset，从而做「模型横向对比」与「同模型迭代纵向追踪」。
          </p>
        </div>
        <Link
          href="/bot-versions/new"
          className="shrink-0 px-4 py-2 bg-moss text-white text-sm rounded hover:opacity-90 no-underline"
        >
          + 新建 Bot 版本
        </Link>
      </div>

      <div className="bg-card border border-[var(--rule)] rounded">
        {bots.length === 0 ? (
          <div className="px-8 py-16 text-center text-ink-3">
            还没有 bot 版本。点右上角「+ 新建 Bot 版本」开始登记，或运行{" "}
            <code className="font-mono-feat bg-[var(--rule)] px-1.5">make seed</code> 灌入种子数据。
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--rule)] text-ink-3 uppercase-label">
                <th className="px-5 py-3 text-left">ID</th>
                <th className="px-5 py-3 text-left">名称</th>
                <th className="px-5 py-3 text-left">版本标签</th>
                <th className="px-5 py-3 text-left">Provider</th>
                <th className="px-5 py-3 text-left">基础模型</th>
                <th className="px-5 py-3 text-right">创建时间</th>
              </tr>
            </thead>
            <tbody>
              {bots.map((b) => (
                <tr
                  key={b.id}
                  className="border-b border-[var(--rule)] last:border-0 hover:bg-[var(--rule)]/40"
                >
                  <td className="px-5 py-3 font-mono-feat text-ink-3">
                    <Link href={`/bot-versions/${b.id}`} className="no-underline text-ink-3 hover:text-ink">
                      #{b.id}
                    </Link>
                  </td>
                  <td className="px-5 py-3">
                    <Link href={`/bot-versions/${b.id}`} className="no-underline text-ink hover:text-moss">
                      <div>{b.name}</div>
                      {b.description && (
                        <div className="text-ink-3 text-xs">{b.description}</div>
                      )}
                    </Link>
                  </td>
                  <td className="px-5 py-3">
                    <span className="badge badge-info font-mono-feat">{b.version_tag}</span>
                  </td>
                  <td className="px-5 py-3 text-ink-2">{b.bot_provider ?? "—"}</td>
                  <td className="px-5 py-3 text-ink-2 font-mono-feat text-xs">
                    {b.base_model ?? "—"}
                  </td>
                  <td className="px-5 py-3 text-right text-ink-3 text-xs">
                    {new Date(b.created_at).toLocaleString()}
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
