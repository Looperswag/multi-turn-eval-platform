"use client";
/* Hallmark · component: dimension-radar · theme: EvalKit Studio (custom) */

import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from "recharts";
import type { DimensionSummary } from "@/lib/api";
import { chartColors } from "@/lib/chart-colors";

// 平台 schema 固定 6 维：dim1 改写忠实 / dim2 跨轮记忆 / dim3 意图边界 /
// dim4 指代消解 / dim5 重复请求 / dim6 用户纠错。后端 dashboard 只返回已启用维度，
// 雷达需对照全集判断是否"残缺"以加注释。
const TOTAL_DIM_COUNT = 6;

export function DimensionRadar({ dimensions }: { dimensions: DimensionSummary[] }) {
  // 仅在雷达上渲染有效维度（avg_score 为 null 视为未启用），
  // 否则空维度会被画为 0 score 顶点，让形状看起来像"故障残缺"。
  const enabled = dimensions.filter((d) => d.avg_score != null);
  const data = enabled.map((d) => ({
    dim: d.dimension_name,
    score: d.avg_score as number,
  }));
  return (
    <div className="flex flex-col gap-xs" style={{ width: "100%", minWidth: 0 }}>
      <div style={{ width: "100%", height: 320 }}>
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
      {enabled.length < TOTAL_DIM_COUNT && (
        <div className="text-center text-xs italic-display text-ink-3">
          本次评测仅启用 {enabled.length} / {TOTAL_DIM_COUNT} 个维度，其余未参与评分
        </div>
      )}
    </div>
  );
}
