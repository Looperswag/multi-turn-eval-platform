"use client";
import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from "recharts";
import type { DimensionSummary } from "@/lib/api";

export function DimensionRadar({ dimensions }: { dimensions: DimensionSummary[] }) {
  const data = dimensions.map((d) => ({
    dim: d.dimension_name,
    score: d.avg_score ?? 0,
  }));
  return (
    <div style={{ width: "100%", height: 320 }}>
      <ResponsiveContainer>
        <RadarChart data={data} outerRadius="75%">
          <PolarGrid stroke="rgba(26,24,21,0.10)" />
          <PolarAngleAxis dataKey="dim" tick={{ fill: "#5C5650", fontSize: 11 }} />
          <Radar
            dataKey="score"
            stroke="#4A7C59"
            fill="#4A7C59"
            fillOpacity={0.25}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
