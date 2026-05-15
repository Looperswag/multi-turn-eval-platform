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
import type { DimensionSummary } from "@/lib/api";

/**
 * 维度分布柱状图：6 维平均分横向柱（雷达图的互补视图）。
 * 低于 0.6 染番茄色，0.6-0.8 中性，>=0.8 苔藓绿。
 */
export function DimensionBar({ dimensions }: { dimensions: DimensionSummary[] }) {
  const data = dimensions.map((d) => ({
    dim: d.dimension_name,
    code: d.dimension_code,
    score: d.avg_score ?? 0,
  }));
  return (
    <div style={{ width: "100%", height: 240 }}>
      <ResponsiveContainer>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 36, bottom: 4, left: 4 }}
        >
          <CartesianGrid stroke="rgba(26,24,21,0.06)" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 1]}
            tick={{ fill: "#8B847C", fontSize: 10 }}
            stroke="rgba(26,24,21,0.10)"
          />
          <YAxis
            type="category"
            dataKey="dim"
            tick={{ fill: "#5C5650", fontSize: 11 }}
            width={92}
            stroke="rgba(26,24,21,0.10)"
          />
          <Tooltip
            contentStyle={{
              background: "#FFFFFF",
              border: "1px solid rgba(26,24,21,0.15)",
              fontSize: 11,
            }}
            formatter={(v: number) => v.toFixed(3)}
          />
          <Bar dataKey="score" radius={[0, 2, 2, 0]}>
            {data.map((d, i) => {
              const c = d.score < 0.6 ? "#C66" : d.score < 0.8 ? "#D4A55C" : "#4A7C59";
              return <Cell key={i} fill={c} />;
            })}
            <LabelList
              dataKey="score"
              position="right"
              formatter={(v: number) => v.toFixed(3)}
              style={{ fill: "#5C5650", fontSize: 10 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
