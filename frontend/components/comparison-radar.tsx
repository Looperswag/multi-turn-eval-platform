"use client";
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

/**
 * 双 series 雷达图：A vs B 同框叠加。
 * - moss（实线）= A
 * - tomato（实线）= B
 */
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
    <div style={{ width: "100%", height: 360 }}>
      <ResponsiveContainer>
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke="rgba(26,24,21,0.10)" />
          <PolarAngleAxis dataKey="dim" tick={{ fill: "#5C5650", fontSize: 11 }} />
          <Radar
            name={labelA}
            dataKey="A"
            stroke="#4A7C59"
            fill="#4A7C59"
            fillOpacity={0.18}
            strokeWidth={2}
          />
          <Radar
            name={labelB}
            dataKey="B"
            stroke="#D14A3E"
            fill="#D14A3E"
            fillOpacity={0.18}
            strokeWidth={2}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              fontSize: 12,
              borderRadius: 4,
              border: "1px solid var(--rule)",
            }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
