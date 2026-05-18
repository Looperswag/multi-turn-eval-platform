"use client";

import { useState } from "react";
import { api } from "@/lib/api";

type Turn = {
  id: number;
  turn_index: number;
  user_query: string;
  timestamp: string | null;
};

type ConversationDetail = {
  id: number;
  conversation_id_src: string;
  dimension_tag: string | null;
  quality_label: string | null;
  issue_type: string | null;
  total_turns: number;
  turns: Turn[];
};

export type MatchedTurn = {
  turn_index: number;
  user_query: string;
};

type Props = {
  datasetId: number;
  conv: {
    id: number;
    conversation_id_src: string;
    dimension_tag: string | null;
    quality_label: string | null;
    issue_type: string | null;
    total_turns: number;
  };
  matchedTurns?: MatchedTurn[];
  highlight?: string;
};

function qualityBadge(q: string | null) {
  if (q === "good") return <span className="badge badge-pass">good</span>;
  if (q === "bad") return <span className="badge badge-warn">bad</span>;
  if (q) return <span className="badge badge-neutral">{q}</span>;
  return <span className="text-ink-3 text-xs">—</span>;
}

function renderWithHighlight(text: string, highlight?: string) {
  if (!highlight) return text;
  const needle = highlight.trim();
  if (!needle) return text;
  const re = new RegExp(`(${needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "ig");
  const parts = text.split(re);
  return parts.map((p, i) =>
    re.test(p) && p.toLowerCase() === needle.toLowerCase() ? (
      <mark key={i} className="bg-[var(--moss-bg)] text-moss px-0.5 rounded-sm">
        {p}
      </mark>
    ) : (
      <span key={i}>{p}</span>
    ),
  );
}

export default function ConversationRow({ datasetId, conv, matchedTurns, highlight }: Props) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !detail && !loading) {
      setLoading(true);
      setError(null);
      try {
        const data = await api<ConversationDetail>(
          `/api/datasets/${datasetId}/conversations/${conv.id}`,
        );
        setDetail(data);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    }
  }

  return (
    <>
      <tr
        onClick={toggle}
        className="border-b border-[var(--rule)] last:border-0 cursor-pointer hover:bg-[var(--moss-bg)]/40 transition-colors"
      >
        <td className="px-4 py-3 font-mono-feat text-ink-3 w-10 text-center align-top">
          <span className="inline-block transition-transform" style={{ transform: open ? "rotate(90deg)" : "none" }}>
            ▸
          </span>
        </td>
        <td className="px-4 py-3 font-mono-feat text-ink-2 text-xs align-top">
          <div>{renderWithHighlight(conv.conversation_id_src, highlight)}</div>
          {matchedTurns && matchedTurns.length > 0 && (
            <div className="mt-1.5 space-y-0.5 text-ink-3 font-normal">
              {matchedTurns.map((t) => (
                <div key={t.turn_index} className="text-[11px] leading-snug">
                  <span className="text-moss font-mono-feat mr-1">#{t.turn_index}</span>
                  {renderWithHighlight(t.user_query, highlight)}
                </div>
              ))}
            </div>
          )}
        </td>
        <td className="px-4 py-3 text-ink-2 text-xs align-top">
          {conv.dimension_tag ? (
            renderWithHighlight(conv.dimension_tag, highlight)
          ) : (
            <span className="text-ink-3">—</span>
          )}
        </td>
        <td className="px-4 py-3 align-top">{qualityBadge(conv.quality_label)}</td>
        <td className="px-4 py-3 text-ink-2 text-xs align-top">
          {conv.issue_type ? (
            renderWithHighlight(conv.issue_type, highlight)
          ) : (
            <span className="text-ink-3">—</span>
          )}
        </td>
        <td className="px-4 py-3 text-right font-mono-feat tabular-nums text-ink-2 align-top">{conv.total_turns}</td>
      </tr>
      {open && (
        <tr className="bg-[var(--card-2)] border-b border-[var(--rule)] last:border-0">
          <td colSpan={6} className="px-6 py-4">
            {loading && <div className="text-ink-3 text-xs">加载中…</div>}
            {error && (
              <div className="text-[#A33] text-xs">
                加载失败：{error}
              </div>
            )}
            {detail && !loading && (
              <div>
                <div className="uppercase-label text-ink-3 mb-2">
                  Turns · {detail.turns.length}
                </div>
                <ol className="space-y-2">
                  {detail.turns.map((t) => (
                    <li
                      key={t.id}
                      className="flex gap-3 items-start border-l-2 border-[var(--rule)] pl-3 py-1"
                    >
                      <span className="font-mono-feat text-xs text-ink-3 shrink-0 w-8 text-right pt-0.5">
                        #{t.turn_index}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-ink text-sm whitespace-pre-wrap break-words">
                          {t.user_query}
                        </div>
                        {t.timestamp && (
                          <div className="text-ink-3 text-[11px] font-mono-feat mt-0.5">
                            {t.timestamp}
                          </div>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
