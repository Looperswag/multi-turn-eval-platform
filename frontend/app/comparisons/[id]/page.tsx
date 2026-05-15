import Link from "next/link";
import { api, type ComparisonOut } from "@/lib/api";
import { ComparisonRadar } from "@/components/comparison-radar";
import { SessionMovement, DimensionMovementTabs } from "@/components/movement-tabs";

async function getComparison(id: string): Promise<ComparisonOut | null> {
  try {
    return await api<ComparisonOut>(`/api/comparisons/${id}`);
  } catch (err) {
    console.error(`[getComparison ${id}]`, err);
    return null;
  }
}

const TYPE_LABEL: Record<string, string> = {
  prompt: "Prompt 对比",
  bot: "Bot 对比",
  judge: "Judge 模型对比",
  human: "机评 vs 人工",
};

const LEVEL_LABEL = ["低 (0)", "中 (0.5)", "高 (1)"];

export default async function ComparisonDetailPage({ params }: { params: { id: string } }) {
  const c = await getComparison(params.id);
  if (!c) {
    return (
      <div className="text-ink-3">
        comparison #{params.id} 未找到。 <Link href="/comparisons" className="text-moss">返回列表</Link>
      </div>
    );
  }

  const { payload } = c;
  const dimCodes = payload.dim_deltas.map((d) => d.dim_code);

  return (
    <div className="max-w-[1200px]">
      <div className="mb-2 text-ink-3 text-xs">
        <Link href="/comparisons" className="text-ink-2 hover:text-ink">对比任务</Link> /
        <span className="ml-2">#{c.id}</span>
      </div>
      <div className="flex items-baseline gap-4 mb-2">
        <h1 className="font-display text-4xl font-medium tracking-tight">
          {c.name || `${c.type} #${c.id}`}
        </h1>
        <span className="badge badge-info">{TYPE_LABEL[c.type] || c.type}</span>
      </div>
      <p className="text-ink-2 mb-8">
        对齐样本 <span className="font-mono-feat tabular-nums">{payload.aligned_count}</span> 条；
        计算于 {payload.computed_at ? new Date(payload.computed_at).toLocaleString() : "—"}
      </p>

      {/* Run summary 双卡 */}
      <section className="grid grid-cols-2 gap-6 mb-10">
        <RunCard summary={payload.run_a_summary} label="Run A" tone="moss" />
        <RunCard summary={payload.run_b_summary} label="Run B" tone="tomato" />
      </section>

      {/* 雷达图 + 维度差异表 */}
      <section className="grid grid-cols-[1fr_1.4fr] gap-6 mb-10">
        <div className="bg-card border border-[var(--rule)] rounded p-6">
          <div className="uppercase-label text-ink-3 mb-4">六维雷达叠加</div>
          <ComparisonRadar
            deltas={payload.dim_deltas}
            labelA={payload.run_a_summary.name}
            labelB={payload.run_b_summary.name}
          />
        </div>
        <div className="bg-card border border-[var(--rule)] rounded p-6">
          <div className="uppercase-label text-ink-3 mb-4">维度差异</div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-ink-3 uppercase-label border-b border-[var(--rule)]">
                <th className="text-left py-2">维度</th>
                <th className="text-right py-2">A 均值</th>
                <th className="text-right py-2">B 均值</th>
                <th className="text-right py-2">Δ</th>
                <th className="text-right py-2">显著性</th>
              </tr>
            </thead>
            <tbody>
              {payload.dim_deltas.map((d) => {
                const deltaCls =
                  d.delta == null
                    ? "text-ink-3"
                    : d.delta > 0
                    ? "text-moss"
                    : d.delta < 0
                    ? "text-tomato"
                    : "text-ink";
                return (
                  <tr key={d.dim_code} className="border-b border-[var(--rule)] last:border-0">
                    <td className="py-2">
                      <div className="text-ink">{d.dim_name}</div>
                      <div className="text-ink-3 text-xs font-mono-feat">{d.dim_code}</div>
                    </td>
                    <td className="py-2 text-right font-mono-feat tabular-nums">
                      {d.avg_a == null ? "—" : d.avg_a.toFixed(3)}
                    </td>
                    <td className="py-2 text-right font-mono-feat tabular-nums">
                      {d.avg_b == null ? "—" : d.avg_b.toFixed(3)}
                    </td>
                    <td className={`py-2 text-right font-mono-feat tabular-nums ${deltaCls}`}>
                      {d.delta == null
                        ? "—"
                        : `${d.delta > 0 ? "+" : ""}${d.delta.toFixed(3)}`}
                    </td>
                    <td className="py-2 text-right text-xs">
                      {d.chi_square_pvalue == null ? (
                        <span className="badge badge-neutral text-[10px]">sample 太小（n={d.sample_size}）</span>
                      ) : (
                        <span
                          className={`font-mono-feat tabular-nums ${
                            d.chi_square_pvalue < 0.05 ? "text-moss" : "text-ink-3"
                          }`}
                        >
                          p={d.chi_square_pvalue.toFixed(3)}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Session-level movement */}
      <section className="mb-10 bg-card border border-[var(--rule)] rounded p-6">
        <div className="flex items-baseline justify-between mb-4">
          <div className="uppercase-label text-ink-3">会话级 Movement（按加权总分阈值 0.6）</div>
          <div className="text-xs text-ink-3">
            进步 {payload.session_movement.improved.length} · 回退 {payload.session_movement.regressed.length}
          </div>
        </div>
        <SessionMovement movement={payload.session_movement} />
      </section>

      {/* Dimension-level movement tabs */}
      <section className="mb-10 bg-card border border-[var(--rule)] rounded p-6">
        <div className="uppercase-label text-ink-3 mb-4">维度级 Movement（各维 dim_score ≥ 0.6 判通过）</div>
        <DimensionMovementTabs movements={payload.dimension_movements} dimCodes={dimCodes} />
      </section>

      {/* Judge 类型专属：一致率视图 */}
      {c.type === "judge" && (
        <section className="mb-10 bg-card border border-[var(--rule)] rounded p-6">
          <div className="uppercase-label text-ink-3 mb-4">一致率视图（Cohen&apos;s weighted κ）</div>
          <div className="grid grid-cols-[200px_1fr] gap-6">
            <div>
              <div className="uppercase-label text-ink-3 mb-2">κ 值</div>
              <div className="font-display text-5xl font-medium tabular-nums">
                {payload.kappa == null ? "—" : payload.kappa.toFixed(3)}
              </div>
              <div className="text-ink-3 text-xs mt-3 leading-snug">
                quadratic weights · 三档（0 / 0.5 / 1）·{" "}
                {payload.kappa == null
                  ? "样本不足"
                  : payload.kappa >= 0.8
                  ? "几乎完全一致"
                  : payload.kappa >= 0.6
                  ? "显著一致"
                  : payload.kappa >= 0.4
                  ? "中等一致"
                  : payload.kappa >= 0.2
                  ? "弱一致"
                  : "差或反向"}
              </div>
            </div>
            <div>
              <div className="uppercase-label text-ink-3 mb-2">混淆矩阵</div>
              {payload.confusion_matrix ? (
                <table className="text-sm">
                  <thead>
                    <tr>
                      <th className="px-2 py-1 text-ink-3 text-left">A \ B</th>
                      {LEVEL_LABEL.map((l) => (
                        <th key={l} className="px-3 py-1 text-ink-3 font-normal">
                          {l}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {payload.confusion_matrix.map((row, i) => (
                      <tr key={i}>
                        <td className="px-2 py-1 text-ink-3">{LEVEL_LABEL[i]}</td>
                        {row.map((v, j) => (
                          <td
                            key={j}
                            className={`px-3 py-1 text-center font-mono-feat tabular-nums border border-[var(--rule)] ${
                              i === j ? "bg-[var(--moss-bg)] text-moss font-medium" : ""
                            }`}
                          >
                            {v}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="text-ink-3 text-sm">无数据</div>
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function RunCard({
  summary,
  label,
  tone,
}: {
  summary: ComparisonOut["payload"]["run_a_summary"];
  label: string;
  tone: "moss" | "tomato";
}) {
  return (
    <div className={`bg-card border border-[var(--rule)] rounded p-5 border-l-4 border-l-${tone}`}>
      <div className="flex items-baseline justify-between mb-2">
        <div className={`uppercase-label text-${tone} font-medium`}>{label}</div>
        <div className="text-ink-3 text-xs">#{summary.id}</div>
      </div>
      <div className="font-display text-xl text-ink mb-3">{summary.name}</div>
      <dl className="space-y-1 text-xs font-mono-feat text-ink-2">
        <div className="flex justify-between">
          <dt className="text-ink-3">加权总分</dt>
          <dd className="tabular-nums">
            {summary.weighted_score == null ? "—" : summary.weighted_score.toFixed(3)}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-ink-3">通过率</dt>
          <dd className="tabular-nums">
            {summary.pass_rate == null ? "—" : `${(summary.pass_rate * 100).toFixed(1)}%`}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-ink-3">Dataset</dt>
          <dd>#{summary.dataset_id}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-ink-3">Bot</dt>
          <dd>#{summary.bot_version_id}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-ink-3">Judge</dt>
          <dd>#{summary.judge_model_id}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-ink-3">Prompts</dt>
          <dd className="truncate text-right">
            {Object.entries(summary.judge_prompt_version_ids)
              .map(([d, v]) => `${d}=${v}`)
              .join(", ")}
          </dd>
        </div>
      </dl>
    </div>
  );
}
