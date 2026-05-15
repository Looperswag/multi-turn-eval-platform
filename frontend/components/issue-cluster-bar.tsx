"use client";
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

/**
 * Issue cluster 横向柱：按关键词频次排序，仅前 5。
 */
export function IssueClusterBar({ clusters }: { clusters: DimensionIssueCluster[] }) {
  if (!clusters.length) {
    return (
      <div className="text-ink-3 text-xs text-center py-8">
        暂未在 explanation 中匹配到典型关键词。
      </div>
    );
  }
  const data = clusters.map((c) => ({ key: c.key, count: c.count }));
  return (
    <div style={{ width: "100%", height: 180 }}>
      <ResponsiveContainer>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 36, bottom: 4, left: 4 }}
        >
          <CartesianGrid stroke="rgba(26,24,21,0.06)" horizontal={false} />
          <XAxis
            type="number"
            allowDecimals={false}
            tick={{ fill: "#8B847C", fontSize: 10 }}
            stroke="rgba(26,24,21,0.10)"
          />
          <YAxis
            type="category"
            dataKey="key"
            tick={{ fill: "#5C5650", fontSize: 11 }}
            width={68}
            stroke="rgba(26,24,21,0.10)"
          />
          <Tooltip
            contentStyle={{
              background: "#FFFFFF",
              border: "1px solid rgba(26,24,21,0.15)",
              fontSize: 11,
            }}
            formatter={(v: number) => `${v} 次`}
          />
          <Bar dataKey="count" radius={[0, 2, 2, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill="#D4A55C" />
            ))}
            <LabelList
              dataKey="count"
              position="right"
              style={{ fill: "#5C5650", fontSize: 10 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
