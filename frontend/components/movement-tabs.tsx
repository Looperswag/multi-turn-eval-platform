"use client";
import { useState } from "react";
import type { DimensionMovement, MovementCase } from "@/lib/api";

const DIM_LABEL: Record<string, string> = {
  dim1: "改写忠实性",
  dim2: "跨轮记忆保留",
  dim3: "意图边界识别",
  dim4: "指代消解准确性",
  dim5: "重复请求处理",
  dim6: "用户纠错响应",
};

function MovementColumn({
  title,
  cases,
  tone,
}: {
  title: string;
  cases: MovementCase[];
  tone: "improved" | "regressed";
}) {
  const accent = tone === "improved" ? "text-moss" : "text-tomato";
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <h3 className={`uppercase-label ${accent}`}>{title}</h3>
        <span className="text-ink-3 text-xs font-mono-feat">{cases.length}</span>
      </div>
      {cases.length === 0 ? (
        <div className="text-ink-3 text-sm px-3 py-6 text-center border border-dashed border-[var(--rule)] rounded">
          无变化样本
        </div>
      ) : (
        <ul className="border border-[var(--rule)] rounded divide-y divide-[var(--rule)] max-h-[420px] overflow-auto">
          {cases.map((c) => (
            <li key={c.conversation_id} className="px-3 py-2 text-sm flex items-baseline justify-between">
              <span className="font-mono-feat text-ink-2 truncate max-w-[55%]" title={c.conversation_id_src}>
                {c.conversation_id_src}
              </span>
              <span className="font-mono-feat tabular-nums text-xs">
                <span className="text-ink-3">{c.score_a == null ? "—" : c.score_a.toFixed(2)}</span>
                <span className="mx-1 text-ink-3">→</span>
                <span className={accent}>{c.score_b == null ? "—" : c.score_b.toFixed(2)}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function SessionMovement({ movement }: { movement: DimensionMovement }) {
  return (
    <div className="grid grid-cols-2 gap-6">
      <MovementColumn title="A 未通过 → B 通过（进步）" cases={movement.improved} tone="improved" />
      <MovementColumn title="A 通过 → B 未通过（回退）" cases={movement.regressed} tone="regressed" />
    </div>
  );
}

export function DimensionMovementTabs({
  movements,
  dimCodes,
}: {
  movements: Record<string, DimensionMovement>;
  dimCodes: string[];
}) {
  const [active, setActive] = useState(dimCodes[0]);
  const current = movements[active];
  return (
    <div>
      <div className="flex gap-1 mb-4 border-b border-[var(--rule)]">
        {dimCodes.map((dim) => {
          const isActive = dim === active;
          const m = movements[dim];
          const total = (m?.improved.length ?? 0) + (m?.regressed.length ?? 0);
          return (
            <button
              key={dim}
              type="button"
              onClick={() => setActive(dim)}
              className={`px-3 py-2 text-sm border-b-2 transition-colors ${
                isActive
                  ? "border-moss text-moss font-medium"
                  : "border-transparent text-ink-2 hover:text-ink"
              }`}
            >
              {DIM_LABEL[dim] || dim}
              <span className="ml-2 text-xs text-ink-3 font-mono-feat">{total}</span>
            </button>
          );
        })}
      </div>
      {current ? (
        <SessionMovement movement={current} />
      ) : (
        <div className="text-ink-3 text-sm">该维度无数据</div>
      )}
    </div>
  );
}
