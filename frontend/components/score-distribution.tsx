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

/**
 * 分数分布直方图：10 个桶（0.0-0.1 ... 0.9-1.0），y = case 数。
 * 数据来自 dashboard 端点的 `score_distribution`。
 */
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
        // 桶起点 <0.6 视为「未通过区」染番茄；其余苔藓绿
        fill: lo < 0.6 ? "#C66" : "#4A7C59",
      };
    });
  const total = data.reduce((s, d) => s + d.count, 0);

  if (total === 0) {
    return (
      <div className="text-ink-3 text-xs text-center py-8">
        暂无 case 分数数据。
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: 200 }}>
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
