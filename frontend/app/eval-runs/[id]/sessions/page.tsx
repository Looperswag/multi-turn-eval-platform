"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

const DIM_LABELS: Record<string, string> = {
  dim1: "改写忠实性",
  dim2: "跨轮记忆保留",
  dim3: "意图边界识别",
  dim4: "指代消解准确性",
  dim5: "重复请求处理",
  dim6: "用户纠错响应",
};

type SessionItem = {
  case_id: number;
  conversation_id: number;
  meta_id: string;
  total_turns: number;
  weighted_score: number | null;
  lowest_dim_code: string | null;
  dim_scores: Record<string, number | null>;
  error: string | null;
};

type SessionListResponse = {
  total: number;
  items: SessionItem[];
};

function fmtScore(s: number | null | undefined): string {
  return s == null ? "—" : s.toFixed(2);
}

function scoreCellClass(s: number | null | undefined): string {
  if (s == null) return "text-ink-3";
  if (s < 0.6) return "text-tomato font-mono-feat";
  if (s < 0.8) return "text-amber font-mono-feat";
  return "text-moss font-mono-feat";
}

type SortKey =
  | "weighted_score"
  | "dim1_score"
  | "dim2_score"
  | "dim3_score"
  | "dim4_score"
  | "dim5_score"
  | "dim6_score"
  | "total_turns"
  | "meta_id";

export default function SessionsPage({ params }: { params: { id: string } }) {
  const runId = parseInt(params.id, 10);

  const [data, setData] = useState<SessionListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [sortBy, setSortBy] = useState<SortKey>("weighted_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [searchQ, setSearchQ] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    const params = new URLSearchParams({
      sort_by: sortBy,
      sort_dir: sortDir,
      limit: "1000",
    });
    if (searchQ.trim()) params.set("q", searchQ.trim());
    api<SessionListResponse>(`/api/eval-runs/${runId}/sessions?${params}`)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [runId, sortBy, sortDir, searchQ]);

  function toggleSort(k: SortKey) {
    if (sortBy === k) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(k);
      setSortDir(k === "meta_id" || k === "total_turns" ? "asc" : "asc");
    }
  }

  const stats = useMemo(() => {
    if (!data) return null;
    const items = data.items;
    const pass = items.filter((i) => (i.weighted_score ?? 0) >= 0.6).length;
    const fail = items.filter((i) => (i.weighted_score ?? 0) < 0.6).length;
    const naN = items.filter((i) => i.weighted_score == null).length;
    return { total: items.length, pass, fail, na: naN };
  }, [data]);

  const sortHeader = (k: SortKey, label: string) => {
    const active = sortBy === k;
    return (
      <button
        type="button"
        onClick={() => toggleSort(k)}
        className={`text-left ${active ? "text-ink" : "text-ink-3"} hover:text-ink`}
      >
        {label} {active && <span>{sortDir === "asc" ? "↑" : "↓"}</span>}
      </button>
    );
  };

  return (
    <div className="max-w-[1400px]">
      <div className="mb-6">
        <nav className="uppercase-label text-ink-3 mb-2">
          <Link href="/eval-runs" className="no-underline text-ink-3 hover:text-ink">
            评测任务
          </Link>
          <span className="mx-1.5">/</span>
          <Link href={`/eval-runs/${runId}`} className="no-underline text-ink-3 hover:text-ink">
            #{runId}
          </Link>
          <span className="mx-1.5">/</span>
          <span>Sessions 概览</span>
        </nav>
        <h1 className="font-display text-3xl font-medium tracking-tight">Sessions 概览</h1>
        <p className="text-ink-2 mt-2 text-sm">
          按 session（meta_id）粒度看加权分 + 各维度分。点行跳 Badcase 钻取 drawer 看每轮细节。
        </p>
      </div>

      {err && <div className="text-tomato text-sm mb-4">{err}</div>}

      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="border border-[var(--rule)] rounded p-3 bg-card-2">
          <div className="uppercase-label text-ink-3">总数</div>
          <div className="font-mono-feat text-2xl mt-1">{stats?.total ?? "—"}</div>
        </div>
        <div className="border border-[var(--rule)] rounded p-3 bg-card-2">
          <div className="uppercase-label text-ink-3">通过 (≥0.6)</div>
          <div className="font-mono-feat text-2xl mt-1 text-moss">{stats?.pass ?? "—"}</div>
        </div>
        <div className="border border-[var(--rule)] rounded p-3 bg-card-2">
          <div className="uppercase-label text-ink-3">不通过</div>
          <div className="font-mono-feat text-2xl mt-1 text-tomato">{stats?.fail ?? "—"}</div>
        </div>
        <div className="border border-[var(--rule)] rounded p-3 bg-card-2">
          <div className="uppercase-label text-ink-3">N/A</div>
          <div className="font-mono-feat text-2xl mt-1 text-ink-3">{stats?.na ?? "—"}</div>
        </div>
      </div>

      <div className="mb-4">
        <input
          value={searchQ}
          onChange={(e) => setSearchQ(e.target.value)}
          placeholder="搜 meta_id（子串模糊）…"
          className="w-72 px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 font-mono-feat text-xs"
        />
        {loading && <span className="ml-3 text-ink-3 text-xs">loading…</span>}
      </div>

      <div className="border border-[var(--rule)] rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-card-2 border-b border-[var(--rule)]">
            <tr className="text-ink-3 uppercase-label">
              <th className="text-left px-3 py-2">{sortHeader("meta_id", "META ID")}</th>
              <th className="text-right px-3 py-2">{sortHeader("total_turns", "轮数")}</th>
              <th className="text-right px-3 py-2">{sortHeader("weighted_score", "加权")}</th>
              <th className="text-left px-3 py-2">最低维</th>
              <th className="text-right px-3 py-2">{sortHeader("dim1_score", "DIM1")}</th>
              <th className="text-right px-3 py-2">{sortHeader("dim2_score", "DIM2")}</th>
              <th className="text-right px-3 py-2">{sortHeader("dim3_score", "DIM3")}</th>
              <th className="text-right px-3 py-2">{sortHeader("dim4_score", "DIM4")}</th>
              <th className="text-right px-3 py-2">{sortHeader("dim5_score", "DIM5")}</th>
              <th className="text-right px-3 py-2">{sortHeader("dim6_score", "DIM6")}</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((s) => (
              <tr
                key={s.case_id}
                onClick={() =>
                  window.location.assign(
                    `/eval-runs/${runId}/badcases?case_id=${s.case_id}`,
                  )
                }
                className="border-t border-[var(--rule)] hover:bg-card-2 cursor-pointer"
              >
                <td className="px-3 py-2 font-mono-feat text-xs">{s.meta_id}</td>
                <td className="px-3 py-2 text-right font-mono-feat">{s.total_turns}</td>
                <td className={`px-3 py-2 text-right ${scoreCellClass(s.weighted_score)}`}>
                  {fmtScore(s.weighted_score)}
                </td>
                <td className="px-3 py-2 text-ink-3 text-xs">
                  {s.lowest_dim_code ? (
                    <span title={DIM_LABELS[s.lowest_dim_code]}>{s.lowest_dim_code}</span>
                  ) : (
                    "—"
                  )}
                </td>
                {(["dim1", "dim2", "dim3", "dim4", "dim5", "dim6"] as const).map((d) => (
                  <td
                    key={d}
                    className={`px-3 py-2 text-right ${scoreCellClass(s.dim_scores[d])}`}
                  >
                    {fmtScore(s.dim_scores[d])}
                  </td>
                ))}
              </tr>
            ))}
            {!loading && data?.items.length === 0 && (
              <tr>
                <td colSpan={10} className="px-3 py-12 text-center text-ink-3">
                  无匹配 session
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
