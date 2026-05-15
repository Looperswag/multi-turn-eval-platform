"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Progress = { completed: number; total: number; failed: number };

export function LiveProgress({ runId, initial }: { runId: number; initial: Progress }) {
  const [progress, setProgress] = useState<Progress>(initial);
  const router = useRouter();

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || "";
    const url = `${base}/api/eval-runs/${runId}/stream`;
    const es = new EventSource(url);
    es.addEventListener("progress", (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data);
        if (payload.completed != null) {
          setProgress({
            completed: payload.completed,
            total: payload.total ?? progress.total,
            failed: payload.failed ?? progress.failed,
          });
        }
        if (["run_finished", "run_failed", "run_cancelled"].includes(payload.event)) {
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
  }, [runId, router, progress.total, progress.failed]);

  const pct = progress.total > 0 ? Math.min(100, (progress.completed / progress.total) * 100) : 0;
  return (
    <div className="mb-8 p-4 bg-[var(--ink-blue-bg)] border border-[var(--ink-blue)] rounded">
      <div className="flex items-center justify-between mb-2 text-xs">
        <span className="uppercase-label text-ink-blue">实时进度</span>
        <span className="font-mono-feat text-ink-2 tabular-nums">
          {progress.completed}/{progress.total} ({pct.toFixed(0)}%) · 失败 {progress.failed}
        </span>
      </div>
      <div className="h-1.5 bg-white rounded overflow-hidden">
        <div
          className="h-full bg-[var(--ink-blue)] transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
