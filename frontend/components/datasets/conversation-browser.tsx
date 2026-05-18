"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import ConversationRow, { type MatchedTurn } from "./conversation-row";

export type ConversationLite = {
  id: number;
  conversation_id_src: string;
  dimension_tag: string | null;
  quality_label: string | null;
  issue_type: string | null;
  total_turns: number;
};

type SearchItem = ConversationLite & { matched_turns?: MatchedTurn[] };

type SearchResult = {
  dataset_id: number;
  q: string;
  total: number;
  truncated: boolean;
  items: SearchItem[];
};

type Props = {
  datasetId: number;
  initial: ConversationLite[];
};

const DEBOUNCE_MS = 250;

export default function ConversationBrowser({ datasetId, initial }: Props) {
  const [q, setQ] = useState("");
  const [activeQ, setActiveQ] = useState(""); // 已生效的关键字（去抖后）
  const [items, setItems] = useState<SearchItem[]>(initial);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [truncated, setTruncated] = useState(false);
  const reqIdRef = useRef(0);

  useEffect(() => {
    const trimmed = q.trim();
    const timer = setTimeout(async () => {
      // 空查询：直接显示初始全量
      if (!trimmed) {
        setItems(initial);
        setActiveQ("");
        setTruncated(false);
        setError(null);
        return;
      }
      const myReq = ++reqIdRef.current;
      setLoading(true);
      setError(null);
      try {
        const res = await api<SearchResult>(
          `/api/datasets/${datasetId}/search?q=${encodeURIComponent(trimmed)}`,
        );
        // 防止过时响应覆盖最新结果
        if (reqIdRef.current !== myReq) return;
        setItems(res.items);
        setActiveQ(res.q);
        setTruncated(res.truncated);
      } catch (e) {
        if (reqIdRef.current !== myReq) return;
        setError((e as Error).message);
      } finally {
        if (reqIdRef.current === myReq) setLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [q, datasetId, initial]);

  const summary = useMemo(() => {
    if (activeQ) return `匹配 ${items.length} 条${truncated ? "（已截断）" : ""}`;
    return `共 ${items.length} 条`;
  }, [activeQ, items.length, truncated]);

  return (
    <section>
      <div className="flex items-center justify-between gap-4 mb-2">
        <h2 className="uppercase-label text-ink-3">会话列表（点击展开查看 turns）</h2>
        <span className="text-ink-3 text-xs">
          {loading ? "搜索中…" : summary}
        </span>
      </div>

      <div className="mb-2 flex items-center gap-2">
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索 conversation_id / dimension_tag / issue_type / user_query"
            className="w-full px-3 py-2 pr-8 border border-[var(--rule-strong)] rounded bg-card-2 text-sm focus:outline-none focus:border-moss"
          />
          {q && (
            <button
              type="button"
              onClick={() => setQ("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-3 hover:text-ink-2 text-sm"
              aria-label="清空"
            >
              ✕
            </button>
          )}
        </div>
        {error && <span className="text-[#A33] text-xs">{error}</span>}
      </div>

      <div className="bg-card border border-[var(--rule)] rounded overflow-hidden">
        {items.length === 0 ? (
          <div className="px-8 py-16 text-center text-ink-3">
            {activeQ ? `没有匹配 "${activeQ}" 的会话` : "该评测集没有任何 conversation。"}
          </div>
        ) : (
          <div className="max-h-[640px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--card-2)] sticky top-0 z-10">
                <tr className="border-b border-[var(--rule)] text-ink-3 uppercase-label">
                  <th className="px-4 py-2.5 w-10"></th>
                  <th className="px-4 py-2.5 text-left">conversation_id_src</th>
                  <th className="px-4 py-2.5 text-left">dimension_tag</th>
                  <th className="px-4 py-2.5 text-left">quality</th>
                  <th className="px-4 py-2.5 text-left">issue_type</th>
                  <th className="px-4 py-2.5 text-right">turns</th>
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <ConversationRow
                    key={c.id}
                    datasetId={datasetId}
                    conv={c}
                    matchedTurns={c.matched_turns}
                    highlight={activeQ || undefined}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
