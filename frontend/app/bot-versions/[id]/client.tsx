"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type RewriteStat = {
  dataset_id: number;
  dataset_name: string;
  rewrite_count: number;
  total_turns: number;
};

type Dataset = {
  id: number;
  name: string;
  conversation_count: number;
};

type Tab = "overview" | "upload";

// Client Component 只在浏览器跑，直接用 NEXT_PUBLIC_*；INTERNAL_API_BASE_URL 仅服务端可见。
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function BotVersionDetailClient({
  botId,
  initialStats,
  datasets,
}: {
  botId: number;
  initialStats: RewriteStat[];
  datasets: Dataset[];
}) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("overview");
  const [stats, setStats] = useState<RewriteStat[]>(initialStats);
  const [refreshing, setRefreshing] = useState(false);

  async function refresh() {
    setRefreshing(true);
    try {
      const d = await api<{ rewrite_stats: RewriteStat[] }>(
        `/api/bot-versions/${botId}`,
      );
      setStats(d.rewrite_stats);
    } catch {
      // swallow; user will see stale data
    } finally {
      setRefreshing(false);
    }
    router.refresh();
  }

  return (
    <>
      <div className="flex gap-1 border-b border-[var(--rule)] mb-6">
        <TabButton active={tab === "overview"} onClick={() => setTab("overview")}>
          Rewrite 数据统计
        </TabButton>
        <TabButton active={tab === "upload"} onClick={() => setTab("upload")}>
          上传 Rewrite 数据
        </TabButton>
        {refreshing && <span className="ml-auto text-ink-3 text-xs self-center">刷新中…</span>}
      </div>

      {tab === "overview" ? (
        <RewriteStatsCard stats={stats} />
      ) : (
        <UploadPanel
          botId={botId}
          datasets={datasets}
          onDone={async () => {
            await refresh();
            setTab("overview");
          }}
        />
      )}
    </>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "px-4 py-2 text-sm -mb-px border-b-2 " +
        (active
          ? "border-moss text-moss font-medium"
          : "border-transparent text-ink-2 hover:text-ink")
      }
    >
      {children}
    </button>
  );
}

function RewriteStatsCard({ stats }: { stats: RewriteStat[] }) {
  if (stats.length === 0) {
    return (
      <div className="bg-card border border-[var(--rule)] rounded px-8 py-16 text-center text-ink-3">
        系统中暂无 dataset，无法展示覆盖统计。
      </div>
    );
  }
  return (
    <div className="bg-card border border-[var(--rule)] rounded">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--rule)] text-ink-3 uppercase-label">
            <th className="px-5 py-3 text-left">数据集</th>
            <th className="px-5 py-3 text-right">已改写 Turn</th>
            <th className="px-5 py-3 text-right">总 Turn</th>
            <th className="px-5 py-3 text-right w-[40%]">覆盖率</th>
          </tr>
        </thead>
        <tbody>
          {stats.map((s) => {
            const ratio = s.total_turns > 0 ? s.rewrite_count / s.total_turns : 0;
            const pct = (ratio * 100).toFixed(1);
            const tone =
              ratio >= 0.99
                ? "var(--moss)"
                : ratio >= 0.5
                  ? "var(--ink-blue)"
                  : "var(--amber)";
            return (
              <tr key={s.dataset_id} className="border-b border-[var(--rule)] last:border-0">
                <td className="px-5 py-3">
                  <div className="text-ink">{s.dataset_name}</div>
                  <div className="text-ink-3 text-xs font-mono-feat">#{s.dataset_id}</div>
                </td>
                <td className="px-5 py-3 text-right font-mono-feat tabular-nums">
                  {s.rewrite_count}
                </td>
                <td className="px-5 py-3 text-right font-mono-feat tabular-nums text-ink-3">
                  {s.total_turns}
                </td>
                <td className="px-5 py-3">
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-2 bg-[var(--rule)] rounded overflow-hidden">
                      <div
                        style={{
                          width: `${Math.min(100, ratio * 100)}%`,
                          background: tone,
                          height: "100%",
                        }}
                      />
                    </div>
                    <span className="font-mono-feat tabular-nums text-xs text-ink-2 w-12 text-right">
                      {pct}%
                    </span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function UploadPanel({
  botId,
  datasets,
  onDone,
}: {
  botId: number;
  datasets: Dataset[];
  onDone: () => void;
}) {
  const [datasetId, setDatasetId] = useState<number>(datasets[0]?.id ?? 0);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ attached: number; skipped: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!datasetId || !file) {
      setError("请选择 dataset 与 JSON 文件");
      return;
    }
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(
        `${API_BASE}/api/bot-versions/${botId}/attach/${datasetId}`,
        { method: "POST", body: fd },
      );
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`${res.status}: ${text}`);
      }
      const json = (await res.json()) as { attached: number; skipped: number };
      setResult(json);
      setTimeout(onDone, 600);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="bg-card border border-[var(--rule)] rounded p-6 space-y-5 max-w-[640px]"
    >
      <div>
        <div className="font-display text-xl mb-1">上传该 bot 版本对某 dataset 的改写输出</div>
        <p className="text-ink-3 text-xs">
          支持两种 JSON schema：
          <br />
          1. 与 <code className="font-mono-feat">mock_multi_turn_queries</code> 同格式（含{" "}
          <code className="font-mono-feat">turns[].rewritten_query</code>）
          <br />
          2. 扁平：
          <code className="font-mono-feat">
            [{`{conversation_id, turn_index, rewritten_query}`}]
          </code>
        </p>
      </div>

      <label className="block">
        <span className="block uppercase-label text-ink-3 mb-1.5">目标数据集</span>
        <select
          value={datasetId}
          onChange={(e) => setDatasetId(parseInt(e.target.value, 10))}
          className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
        >
          {datasets.length === 0 && <option value={0}>—</option>}
          {datasets.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name} ({d.conversation_count} 会话)
            </option>
          ))}
        </select>
      </label>

      <label className="block">
        <span className="block uppercase-label text-ink-3 mb-1.5">JSON 文件</span>
        <input
          type="file"
          accept="application/json,.json"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-ink-2 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-[var(--rule)] file:text-ink file:font-mono-feat"
        />
      </label>

      {error && <div className="text-tomato text-sm">{error}</div>}
      {result && (
        <div className="text-moss text-sm">
          已写入 {result.attached} 条改写，跳过 {result.skipped} 条（dataset 中找不到对应 turn）。
        </div>
      )}

      <div className="flex justify-end gap-3 pt-3 border-t border-[var(--rule)]">
        <button
          type="submit"
          disabled={submitting}
          className="px-5 py-2 bg-moss text-white text-sm rounded hover:opacity-90 disabled:opacity-50"
        >
          {submitting ? "上传中…" : "上传并写入"}
        </button>
      </div>
    </form>
  );
}
