"use client";
/* Hallmark · component: score-distribution · theme: EvalKit Studio (custom) */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { chartColors, tooltipStyle } from "@/lib/chart-colors";

export function ScoreDistribution({
  distribution,
}: {
  distribution: Record<string, number>;
}) {
  const data = Object.entries(distribution)
    .sort(([a], [b]) => parseFloat(a) - parseFloat(b))
    .map(([bucket, count]) => {
      const lo = parseFloat(bucket.split("-")[0]);
      return {
        bucket,
        count,
        fill: lo < 0.6 ? chartColors.warn : chartColors.accent,
      };
    });
  const total = data.reduce((s, d) => s + d.count, 0);

  if (total === 0) {
    return (
      <div className="py-xl text-center text-sm italic-display text-ink-3">
        暂无 case 分数数据。
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: 220, minWidth: 0 }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 16, right: 8, bottom: 4, left: 0 }}>
          <CartesianGrid stroke={chartColors.rule} vertical={false} />
          <XAxis
            dataKey="bucket"
            tick={{ fill: chartColors.ink3, fontSize: 9, fontFamily: "var(--font-mono)" }}
            stroke={chartColors.rule}
            interval={0}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: chartColors.ink3, fontSize: 10, fontFamily: "var(--font-mono)" }}
            stroke={chartColors.rule}
            width={28}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v: number) => `${v} 个 case`}
            cursor={{ fill: chartColors.accentSoft, opacity: 0.4 }}
          />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.fill} />
            ))}
            <LabelList
              dataKey="count"
              position="top"
              style={{ fill: chartColors.ink2, fontSize: 10, fontFamily: "var(--font-mono)" }}
              formatter={(v: number) => (v > 0 ? String(v) : "")}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
