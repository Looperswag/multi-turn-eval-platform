"use client";
/* Hallmark · component: issue-cluster-bar · theme: EvalKit Studio (custom) */

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
import type { DimensionIssueCluster } from "@/lib/api";
import { chartColors, tooltipStyle } from "@/lib/chart-colors";

export function IssueClusterBar({ clusters }: { clusters: DimensionIssueCluster[] }) {
  if (!clusters.length) {
    return (
      <div className="py-xl text-center text-sm italic-display text-ink-3">
        本维度 prompt 未输出 explanation 字段（session-level prompt 通常不产生 per-row 解释）。
      </div>
    );
  }
  const data = clusters.map((c) => ({ key: c.key, count: c.count }));
  return (
    <div style={{ width: "100%", height: 200, minWidth: 0 }}>
      <ResponsiveContainer>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 40, bottom: 4, left: 4 }}
        >
          <CartesianGrid stroke={chartColors.rule} horizontal={false} />
          <XAxis
            type="number"
            allowDecimals={false}
            tick={{ fill: chartColors.ink3, fontSize: 10, fontFamily: "var(--font-mono)" }}
            stroke={chartColors.rule}
          />
          <YAxis
            type="category"
            dataKey="key"
            tick={{ fill: chartColors.ink2, fontSize: 11, fontFamily: "var(--font-body)" }}
            width={72}
            stroke={chartColors.rule}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v: number) => `${v} 次`}
            cursor={{ fill: chartColors.noteSoft, opacity: 0.4 }}
          />
          <Bar dataKey="count" radius={[0, 2, 2, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={chartColors.note} />
            ))}
            <LabelList
              dataKey="count"
              position="right"
              style={{ fill: chartColors.ink2, fontSize: 10, fontFamily: "var(--font-mono)" }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
