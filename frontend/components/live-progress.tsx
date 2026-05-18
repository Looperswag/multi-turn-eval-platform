"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { LiveProgressEvent } from "@/lib/api";

type Progress = { completed: number; total: number; failed: number };
type RunStatus = "pending" | "running" | "success" | "partial" | "failed" | "cancelled";

type FailedCase = {
  conversation_id: number;
  error_message: string;
};

type DimAccum = { sum: number; count: number };

const DIM_LABELS: Record<string, string> = {
  dim1: "改写忠实",
  dim2: "跨轮记忆",
  dim3: "意图边界",
  dim4: "指代消解",
  dim5: "重复请求",
  dim6: "纠错响应",
};

const DIM_CODES = ["dim1", "dim2", "dim3", "dim4", "dim5", "dim6"] as const;

function colorFor(score: number): string {
  // 沿用 dimension-bar 的色阶
  if (score < 0.6) return "#C66";
  if (score < 0.8) return "#D4A55C";
  return "#4A7C59";
}

function formatEta(seconds: number | null | undefined): string {
  if (seconds == null || seconds < 0) return "—";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m${s.toString().padStart(2, "0")}s`;
}

function truncate(s: string, n = 60): string {
  if (!s) return "";
  return s.length > n ? s.slice(0, n) + "…" : s;
}

export function LiveProgress({
  runId,
  initial,
  status,
}: {
  runId: number;
  initial: Progress;
  status?: RunStatus;
}) {
  const isTerminal =
    status === "success" || status === "partial" || status === "failed" || status === "cancelled";
  const [progress, setProgress] = useState<Progress>(initial);
  const [etaSeconds, setEtaSeconds] = useState<number | null>(null);
  const [dimAvg, setDimAvg] = useState<Record<string, DimAccum>>({});
  const [failedList, setFailedList] = useState<FailedCase[]>([]);
  const [finished, setFinished] = useState<boolean>(isTerminal);
  const [retryBusy, setRetryBusy] = useState(false);
  const [retryMsg, setRetryMsg] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    // C.3 reviewer Risk G 修复：依赖 `finished` state（可被 handleRetry 重置）
    // 而不是 prop-derived `isTerminal`（status 不变则不会触发重新订阅）
    if (finished) return;
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || "";
    const url = `${base}/api/eval-runs/${runId}/stream`;
    const es = new EventSource(url);

    es.addEventListener("progress", (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data) as LiveProgressEvent;

        // 进度数据
        if (payload.completed != null || payload.failed != null || payload.total != null) {
          setProgress((prev) => ({
            completed: payload.completed ?? prev.completed,
            total: payload.total ?? prev.total,
            failed: payload.failed ?? prev.failed,
          }));
        }

        if (payload.eta_seconds !== undefined) {
          setEtaSeconds(payload.eta_seconds);
        }

        // 累积 per-dim 平均
        if (payload.event === "case_completed" && payload.dim_scores) {
          setDimAvg((prev) => {
            const next = { ...prev };
            for (const [code, score] of Object.entries(payload.dim_scores!)) {
              if (score == null) continue;
              const cur = next[code] ?? { sum: 0, count: 0 };
              next[code] = { sum: cur.sum + score, count: cur.count + 1 };
            }
            return next;
          });
        }

        // 失败 case
        if (payload.event === "case_failed") {
          setFailedList((prev) => [
            {
              conversation_id: payload.conversation_id ?? -1,
              error_message: payload.error_message ?? "unknown error",
            },
            ...prev,
          ].slice(0, 20));
        }

        if (
          payload.event === "run_finished" ||
          payload.event === "run_failed" ||
          payload.event === "run_cancelled"
        ) {
          setFinished(true);
          es.close();
          router.refresh();
        }
      } catch {
        // ignore parse errors
      }
    });

    es.onerror = () => {
      es.close();
    };
    return () => es.close();
  }, [runId, router, finished]);

  const pct = progress.total > 0 ? Math.min(100, (progress.completed / progress.total) * 100) : 0;

  const dimAvgList = useMemo(
    () =>
      DIM_CODES.map((code) => {
        const acc = dimAvg[code];
        const avg = acc && acc.count > 0 ? acc.sum / acc.count : null;
        return { code, name: DIM_LABELS[code], avg, count: acc?.count ?? 0 };
      }),
    [dimAvg]
  );

  async function handleRetry() {
    setRetryBusy(true);
    setRetryMsg(null);
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE_URL || "";
      const res = await fetch(`${base}/api/eval-runs/${runId}/retry-failed`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await res.json();
      if (!res.ok) {
        setRetryMsg(data?.detail ?? `HTTP ${res.status}`);
      } else {
        setRetryMsg(data?.message ?? `queued ${data?.queued ?? 0}`);
        // 清空失败列表（再次开始接收新事件）
        setFailedList([]);
        setFinished(false);
        router.refresh();
      }
    } catch (err) {
      setRetryMsg(err instanceof Error ? err.message : "retry failed");
    } finally {
      setRetryBusy(false);
    }
  }

  const showRetry = finished && progress.failed > 0;

  return (
    <div className="mb-8 p-4 bg-[var(--ink-blue-bg)] border border-[var(--ink-blue)] rounded">
      {/* 顶栏：标题 + 进度数字 + ETA */}
      <div className="flex items-center justify-between mb-2 text-xs">
        <span className="uppercase-label text-ink-blue">实时进度</span>
        <span className="font-mono-feat text-ink-2 tabular-nums">
          {progress.completed}/{progress.total} ({pct.toFixed(0)}%) · 失败 {progress.failed}
          {!finished && (
            <span className="ml-3 text-ink-3">
              · 预计剩余 {formatEta(etaSeconds)}
            </span>
          )}
          {finished && <span className="ml-3 text-moss">· 完成</span>}
        </span>
      </div>

      {/* 主进度条 */}
      <div className="h-1.5 bg-white rounded overflow-hidden mb-4">
        <div
          className="h-full bg-[var(--ink-blue)] transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* per-dim mini bars */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 mb-1">
        {dimAvgList.map(({ code, name, avg, count }) => {
          const widthPct = avg == null ? 0 : Math.max(2, avg * 100);
          const color = avg == null ? "#D8D2C8" : colorFor(avg);
          return (
            <div key={code} className="flex items-center gap-2 text-[11px]">
              <span className="text-ink-3 w-16 shrink-0">{name}</span>
              <div className="flex-1 h-1 bg-white rounded overflow-hidden">
                <div
                  className="h-full transition-all duration-500"
                  style={{ width: `${widthPct}%`, background: color }}
                />
              </div>
              <span className="font-mono-feat tabular-nums text-ink-2 w-14 text-right">
                {avg == null ? "—" : `${avg.toFixed(2)} · ${count}`}
              </span>
            </div>
          );
        })}
      </div>

      {/* 失败 case 实时列表 */}
      {failedList.length > 0 && (
        <div className="mt-4 pt-3 border-t border-[var(--ink-blue)]">
          <div className="uppercase-label text-tomato text-[10px] mb-2">
            失败 case（最新 {failedList.length} 条）
          </div>
          <ul className="space-y-1 text-[11px] max-h-32 overflow-y-auto">
            {failedList.map((f, i) => (
              <li key={i} className="flex items-start gap-2 font-mono-feat">
                <span className="text-ink-3 shrink-0">#{f.conversation_id}</span>
                <span className="text-tomato">{truncate(f.error_message, 60)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 重试按钮 */}
      {showRetry && (
        <div className="mt-4 pt-3 border-t border-[var(--ink-blue)] flex items-center gap-3">
          <button
            type="button"
            onClick={handleRetry}
            disabled={retryBusy}
            className="px-3 py-1.5 bg-tomato text-white text-xs font-medium rounded hover:opacity-90 disabled:opacity-50"
          >
            {retryBusy ? "重试中…" : `重试 ${progress.failed} 个失败 case`}
          </button>
          {retryMsg && (
            <span className="text-[11px] text-ink-2">{retryMsg}</span>
          )}
        </div>
      )}
    </div>
  );
}
