"use client";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import type { EvalRun } from "@/lib/api";

/**
 * 历史趋势 mini chart：所有已完成 run 的 weighted_score 时间序列。
 * X = created_at（升序），Y = 0..1。pending/running 的 run 跳过。
 */
export function EvalRunsTrend({ runs }: { runs: EvalRun[] }) {
  const points = runs
    .filter((r) => r.weighted_score != null && (r.status === "success" || r.status === "partial"))
    .slice()
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    .map((r) => ({
      id: r.id,
      name: r.name,
      score: r.weighted_score as number,
      label: new Date(r.created_at).toLocaleDateString(),
    }));

  if (points.length === 0) {
    return (
      <div className="text-ink-3 text-xs px-4 py-3">
        暂无已完成评测，趋势图待数据。
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: 80 }}>
      <ResponsiveContainer>
        <LineChart data={points} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="label"
            tick={{ fill: "#8B847C", fontSize: 10 }}
            stroke="rgba(26,24,21,0.10)"
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fill: "#8B847C", fontSize: 10 }}
            stroke="rgba(26,24,21,0.10)"
            width={28}
          />
          <ReferenceLine y={0.6} stroke="#C66" strokeDasharray="3 3" strokeOpacity={0.5} />
          <Tooltip
            contentStyle={{
              background: "#FFFFFF",
              border: "1px solid rgba(26,24,21,0.15)",
              fontSize: 11,
            }}
            formatter={(v: number) => v.toFixed(3)}
            labelFormatter={(_, payload) => {
              const p = payload?.[0]?.payload;
              return p ? `#${p.id} ${p.name}` : "";
            }}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#4A7C59"
            strokeWidth={1.5}
            dot={{ r: 2, fill: "#4A7C59" }}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
