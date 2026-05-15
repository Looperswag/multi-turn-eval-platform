import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { BotVersionDetailClient } from "./client";

type BotVersion = {
  id: number;
  name: string;
  version_tag: string;
  description: string | null;
  bot_provider: string | null;
  base_model: string | null;
  created_at: string;
};

type RewriteStat = {
  dataset_id: number;
  dataset_name: string;
  rewrite_count: number;
  total_turns: number;
};

type Detail = {
  bot_version: BotVersion;
  rewrite_stats: RewriteStat[];
};

type Dataset = {
  id: number;
  name: string;
  conversation_count: number;
};

export default async function BotVersionDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const id = parseInt(params.id, 10);
  if (Number.isNaN(id)) notFound();

  let detail: Detail;
  let datasets: Dataset[] = [];
  try {
    [detail, datasets] = await Promise.all([
      api<Detail>(`/api/bot-versions/${id}`),
      api<Dataset[]>("/api/datasets"),
    ]);
  } catch (err) {
    const msg = (err as Error).message;
    if (msg.includes("404")) notFound();
    return <div className="text-tomato">加载失败：{msg}</div>;
  }

  const bv = detail.bot_version;

  return (
    <div className="max-w-[1100px]">
      <div className="mb-6">
        <div className="uppercase-label text-ink-3 mb-2">
          <Link href="/bot-versions" className="no-underline text-ink-3 hover:text-ink">
            Bot 版本
          </Link>
          <span className="mx-1.5">/</span>
          <span className="font-mono-feat">#{bv.id}</span>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="font-display text-4xl font-medium tracking-tight">{bv.name}</h1>
          <span className="badge badge-info font-mono-feat">{bv.version_tag}</span>
        </div>
      </div>

      <div className="bg-card border border-[var(--rule)] rounded p-6 mb-6 grid grid-cols-2 gap-x-8 gap-y-4">
        <Meta label="描述" value={bv.description} />
        <Meta label="创建时间" value={new Date(bv.created_at).toLocaleString()} />
        <Meta label="Bot Provider" value={bv.bot_provider} />
        <Meta label="基础模型" value={bv.base_model} mono />
      </div>

      <BotVersionDetailClient
        botId={id}
        initialStats={detail.rewrite_stats}
        datasets={datasets}
      />
    </div>
  );
}

function Meta({
  label,
  value,
  mono,
}: {
  label: string;
  value: string | null;
  mono?: boolean;
}) {
  return (
    <div>
      <div className="uppercase-label text-ink-3 mb-1">{label}</div>
      <div className={mono ? "font-mono-feat text-ink" : "text-ink"}>
        {value ?? <span className="text-ink-3">—</span>}
      </div>
    </div>
  );
}
