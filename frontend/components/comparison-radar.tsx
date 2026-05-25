"use client";
/* Hallmark · component: comparison-radar · theme: EvalKit Studio (custom) */

import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { DimDelta } from "@/lib/api";
import { chartColors, tooltipStyle } from "@/lib/chart-colors";

export function ComparisonRadar({
  deltas,
  labelA = "Run A",
  labelB = "Run B",
}: {
  deltas: DimDelta[];
  labelA?: string;
  labelB?: string;
}) {
  const data = deltas.map((d) => ({
    dim: d.dim_name,
    A: d.avg_a ?? 0,
    B: d.avg_b ?? 0,
  }));
  return (
    <div style={{ width: "100%", height: 360, minWidth: 0 }}>
      <ResponsiveContainer>
        <RadarChart data={data} outerRadius="70%">
          <PolarGrid stroke={chartColors.rule} />
          <PolarAngleAxis
            dataKey="dim"
            tick={{ fill: chartColors.ink2, fontSize: 11, fontFamily: "var(--font-body)" }}
          />
          <Radar
            name={labelA}
            dataKey="A"
            stroke={chartColors.accent}
            fill={chartColors.accent}
            fillOpacity={0.16}
            strokeWidth={1.8}
          />
          <Radar
            name={labelB}
            dataKey="B"
            stroke={chartColors.warn}
            fill={chartColors.warn}
            fillOpacity={0.14}
            strokeWidth={1.8}
          />
          <Legend
            wrapperStyle={{
              fontSize: 12,
              fontFamily: "var(--font-body)",
              color: chartColors.ink2,
            }}
          />
          <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => v.toFixed(3)} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
