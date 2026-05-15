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
import type { DimensionHistBucket } from "@/lib/api";

/**
 * 单维度分数 10 桶直方图。<0.6 染番茄红，≥0.6 苔藓绿。
 */
export function DimHistogram({ buckets }: { buckets: DimensionHistBucket[] }) {
  const data = buckets.map((b) => {
    const lo = parseFloat(b.bucket.split("-")[0]);
    return {
      bucket: b.bucket,
      count: b.count,
      fill: lo < 0.6 ? "#C66" : "#4A7C59",
    };
  });
  const total = data.reduce((s, d) => s + d.count, 0);
  if (total === 0) {
    return (
      <div className="text-ink-3 text-xs text-center py-8">
        该维度暂无适用样本。
      </div>
    );
  }
  return (
    <div style={{ width: "100%", height: 220 }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 12, right: 8, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="rgba(26,24,21,0.06)" vertical={false} />
          <XAxis
            dataKey="bucket"
            tick={{ fill: "#8B847C", fontSize: 9 }}
            stroke="rgba(26,24,21,0.10)"
            interval={0}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: "#8B847C", fontSize: 10 }}
            stroke="rgba(26,24,21,0.10)"
            width={28}
          />
          <Tooltip
            contentStyle={{
              background: "#FFFFFF",
              border: "1px solid rgba(26,24,21,0.15)",
              fontSize: 11,
            }}
            formatter={(v: number) => `${v} 个 case`}
          />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.fill} />
            ))}
            <LabelList
              dataKey="count"
              position="top"
              style={{ fill: "#5C5650", fontSize: 10 }}
              formatter={(v: number) => (v > 0 ? String(v) : "")}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
