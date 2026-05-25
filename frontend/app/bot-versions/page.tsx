/* Hallmark · macrostructure: Catalogue · theme: EvalKit Studio (custom) */

import Link from "next/link";
import { api } from "@/lib/api";
import { PageShell } from "@/components/page-shell";

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
    <PageShell
      eyebrow={{ label: "数据" }}
      title="Bot 版本"
      lede="Bot 改写器的版本登记。每个 bot 版本可对接多份 dataset，从而做模型横向对比与同模型迭代纵向追踪。"
      meta={`共 ${bots.length} 个`}
      actions={
        <Link
          href="/bot-versions/new"
          className="inline-flex items-center gap-2xs border-b border-accent pb-[1px] text-sm font-medium text-accent transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
        >
          新建 Bot 版本 <span aria-hidden>→</span>
        </Link>
      }
    >
      {bots.length === 0 ? (
        <div className="border-t border-rule py-2xl text-center text-lede italic-display text-ink-3">
          尚无 bot 版本。点上方「新建 Bot 版本」开始登记，或 <code className="font-mono not-italic text-ink-2">make seed</code> 灌入种子。
        </div>
      ) : (
        <div className="min-w-0 overflow-x-auto border-t border-rule">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule text-caption uppercase tracking-[0.08em] text-ink-3">
                <th className="py-sm pr-md text-left font-normal">ID</th>
                <th className="py-sm pr-md text-left font-normal">名称</th>
                <th className="py-sm pr-md text-left font-normal">版本</th>
                <th className="py-sm pr-md text-left font-normal">Provider</th>
                <th className="py-sm pr-md text-left font-normal">基础模型</th>
                <th className="py-sm text-right font-normal">创建</th>
              </tr>
            </thead>
            <tbody>
              {bots.map((b) => (
                <tr
                  key={b.id}
                  className="group border-b border-rule last:border-0 transition-colors duration-fast ease-out hover:bg-paper-2"
                >
                  <td className="py-sm pr-md">
                    <Link href={`/bot-versions/${b.id}`} className="block font-mono tabular-nums text-ink-3 transition-colors duration-fast ease-out group-hover:text-ink">
                      #{b.id}
                    </Link>
                  </td>
                  <td className="py-sm pr-md">
                    <Link href={`/bot-versions/${b.id}`} className="block">
                      <div className="text-ink transition-colors duration-fast ease-out group-hover:text-accent">{b.name}</div>
                      {b.description ? (
                        <div className="mt-2xs text-xs italic-display text-ink-3">{b.description}</div>
                      ) : null}
                    </Link>
                  </td>
                  <td className="py-sm pr-md">
                    <span className="badge badge-info font-mono">{b.version_tag}</span>
                  </td>
                  <td className="py-sm pr-md text-ink-2">{b.bot_provider ?? "—"}</td>
                  <td className="py-sm pr-md font-mono text-xs text-ink-2">{b.base_model ?? "—"}</td>
                  <td className="py-sm text-right font-mono text-xs tabular-nums text-ink-3">
                    {new Date(b.created_at).toLocaleDateString()}
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
