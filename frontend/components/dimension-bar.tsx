"use client";
/* Hallmark · component: dimension-bar · theme: EvalKit Studio (custom) */

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
import { chartColors, scoreColor, tooltipStyle } from "@/lib/chart-colors";

export function DimensionBar({ dimensions }: { dimensions: DimensionSummary[] }) {
  const data = dimensions.map((d) => ({
    dim: d.dimension_name,
    code: d.dimension_code,
    score: d.avg_score ?? 0,
  }));
  return (
    <div style={{ width: "100%", height: 260, minWidth: 0 }}>
      <ResponsiveContainer>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 40, bottom: 4, left: 4 }}
        >
          <CartesianGrid stroke={chartColors.rule} horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 1]}
            tick={{ fill: chartColors.ink3, fontSize: 10, fontFamily: "var(--font-mono)" }}
            stroke={chartColors.rule}
          />
          <YAxis
            type="category"
            dataKey="dim"
            tick={{ fill: chartColors.ink2, fontSize: 11, fontFamily: "var(--font-body)" }}
            width={92}
            stroke={chartColors.rule}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v: number) => v.toFixed(3)}
            cursor={{ fill: chartColors.accentSoft, opacity: 0.4 }}
          />
          <Bar dataKey="score" radius={[0, 2, 2, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={scoreColor(d.score)} />
            ))}
            <LabelList
              dataKey="score"
              position="right"
              formatter={(v: number) => v.toFixed(3)}
              style={{ fill: chartColors.ink2, fontSize: 10, fontFamily: "var(--font-mono)" }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
