import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import ConversationBrowser from "@/components/datasets/conversation-browser";

type Conversation = {
  id: number;
  conversation_id_src: string;
  dimension_tag: string | null;
  quality_label: string | null;
  issue_type: string | null;
  total_turns: number;
};

type DatasetDetail = {
  id: number;
  name: string;
  description: string | null;
  version: string;
  conversation_count: number;
  created_at: string;
  conversations: Conversation[];
};

async function getDataset(id: string): Promise<DatasetDetail | null> {
  try {
    return await api<DatasetDetail>(`/api/datasets/${id}`);
  } catch (e) {
    if ((e as Error).message.includes("404")) return null;
    throw e;
  }
}

// 顶层 schema 描述：直接展示存储后字段，避免重新猜源文件结构
const SCHEMA_SNIPPET = `Dataset {
  id, name, description, version, conversation_count, created_at,
  conversations: Conversation[] {
    id, conversation_id_src, dimension_tag, quality_label, issue_type, total_turns,
    turns: Turn[] {
      id, turn_index, user_query, timestamp
    }
  }
}`;

function quickStats(conversations: Conversation[]) {
  const stats = {
    good: 0,
    bad: 0,
    unlabeled: 0,
    totalTurns: 0,
    dims: new Set<string>(),
  };
  for (const c of conversations) {
    if (c.quality_label === "good") stats.good += 1;
    else if (c.quality_label === "bad") stats.bad += 1;
    else stats.unlabeled += 1;
    stats.totalTurns += c.total_turns;
    if (c.dimension_tag) stats.dims.add(c.dimension_tag);
  }
  return stats;
}

export default async function DatasetDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const dataset = await getDataset(params.id);
  if (!dataset) notFound();

  const stats = quickStats(dataset.conversations);
  const avgTurns =
    dataset.conversations.length > 0
      ? (stats.totalTurns / dataset.conversations.length).toFixed(1)
      : "—";

  return (
    <div className="max-w-[1100px]">
      <div className="mb-6">
        <Link
          href="/datasets"
          className="text-ink-3 text-xs hover:text-ink-2 inline-flex items-center gap-1"
        >
          ← 评测集列表
        </Link>
      </div>

      <div className="mb-8 flex items-start justify-between gap-6">
        <div>
          <div className="uppercase-label text-ink-3 mb-2">数据 / 评测集 / 详情</div>
          <div className="flex items-baseline gap-3 flex-wrap">
            <h1 className="font-display text-4xl font-medium tracking-tight">{dataset.name}</h1>
            <span className="badge badge-neutral">{dataset.version}</span>
            <span className="font-mono-feat text-xs text-ink-3">#{dataset.id}</span>
          </div>
          {dataset.description && (
            <p className="text-ink-2 mt-2 max-w-2xl">{dataset.description}</p>
          )}
          <div className="text-ink-3 text-xs mt-2">
            创建于 {new Date(dataset.created_at).toLocaleString()}
          </div>
        </div>
        <a
          href={`${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/api/datasets/${dataset.id}/export`}
          className="shrink-0 inline-flex items-center gap-2 px-4 py-2 border border-[var(--rule-strong)] rounded text-sm text-ink hover:bg-[var(--card-2)] transition-colors"
          download
        >
          ↓ 导出 JSON
        </a>
      </div>

      {/* 概览统计 */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        <StatCell label="会话总数" value={dataset.conversation_count.toString()} />
        <StatCell label="平均轮次" value={avgTurns} />
        <StatCell
          label="质量分布"
          value={
            <span className="font-mono-feat text-base">
              <span className="text-moss">{stats.good}</span>
              <span className="text-ink-3"> / </span>
              <span className="text-[#A33]">{stats.bad}</span>
              {stats.unlabeled > 0 && (
                <>
                  <span className="text-ink-3"> / </span>
                  <span className="text-ink-3">{stats.unlabeled}</span>
                </>
              )}
            </span>
          }
          hint={stats.unlabeled > 0 ? "good / bad / 未标注" : "good / bad"}
        />
        <StatCell label="维度标签数" value={stats.dims.size.toString()} />
      </div>

      {/* 数据结构 */}
      <section className="mb-6">
        <h2 className="uppercase-label text-ink-3 mb-2">数据结构</h2>
        <pre className="bg-card border border-[var(--rule)] rounded p-4 text-xs font-mono-feat text-ink-2 overflow-x-auto whitespace-pre">
{SCHEMA_SNIPPET}
        </pre>
      </section>

      <ConversationBrowser datasetId={dataset.id} initial={dataset.conversations} />
    </div>
  );
}

function StatCell({
  label,
  value,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="bg-card border border-[var(--rule)] rounded p-4">
      <div className="uppercase-label text-ink-3 mb-1">{label}</div>
      <div className="font-display text-2xl font-medium text-ink leading-tight">{value}</div>
      {hint && <div className="text-ink-3 text-[11px] mt-1">{hint}</div>}
    </div>
  );
}
