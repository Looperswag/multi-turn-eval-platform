"use client";
/* Hallmark · component: eval-runs-trend · theme: EvalKit Studio (custom) */

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { EvalRun } from "@/lib/api";
import { chartColors, tooltipStyle } from "@/lib/chart-colors";

export function EvalRunsTrend({ runs }: { runs: EvalRun[] }) {
  const points = runs
    .filter(
      (r) => r.weighted_score != null && (r.status === "success" || r.status === "partial"),
    )
    .slice()
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    .map((r) => ({
      id: r.id,
      name: r.name,
      score: r.weighted_score as number,
      label: new Date(r.created_at).toLocaleDateString(),
    }));

  if (points.length === 0) {
    return (
      <div className="py-md text-sm italic-display text-ink-3">
        暂无已完成评测，趋势图待数据。
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: 96, minWidth: 0 }}>
      <ResponsiveContainer>
        <LineChart data={points} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="label"
            tick={{ fill: chartColors.ink3, fontSize: 10, fontFamily: "var(--font-mono)" }}
            stroke={chartColors.rule}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fill: chartColors.ink3, fontSize: 10, fontFamily: "var(--font-mono)" }}
            stroke={chartColors.rule}
            width={28}
          />
          <ReferenceLine y={0.6} stroke={chartColors.warn} strokeDasharray="3 3" strokeOpacity={0.5} />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v: number) => v.toFixed(3)}
            labelFormatter={(_, payload) => {
              const p = payload?.[0]?.payload;
              return p ? `#${p.id} ${p.name}` : "";
            }}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke={chartColors.accent}
            strokeWidth={1.5}
            dot={{ r: 2, fill: chartColors.accent }}
            activeDot={{ r: 4, fill: chartColors.accent }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
