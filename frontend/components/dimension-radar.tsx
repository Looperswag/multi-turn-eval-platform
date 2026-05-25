"use client";
/* Hallmark · component: dimension-radar · theme: EvalKit Studio (custom) */

import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from "recharts";
import type { DimensionSummary } from "@/lib/api";
import { chartColors } from "@/lib/chart-colors";

export function DimensionRadar({ dimensions }: { dimensions: DimensionSummary[] }) {
  const data = dimensions.map((d) => ({
    dim: d.dimension_name,
    score: d.avg_score ?? 0,
  }));
  return (
    <div style={{ width: "100%", height: 320, minWidth: 0 }}>
      <ResponsiveContainer>
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke={chartColors.rule} />
          <PolarAngleAxis
            dataKey="dim"
            tick={{ fill: chartColors.ink2, fontSize: 11, fontFamily: "var(--font-body)" }}
          />
          <Radar
            dataKey="score"
            stroke={chartColors.accent}
            fill={chartColors.accent}
            fillOpacity={0.18}
            strokeWidth={1.5}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
