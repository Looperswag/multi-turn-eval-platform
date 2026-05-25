/* Hallmark · macrostructure: Quote-Led · theme: EvalKit Studio (custom)
 * The single most important number (Kappa for judge, Δ weighted_score otherwise)
 * is centered as the page quote; A / B meta hang below; radar + movement follow.
 */

import Link from "next/link";
import { api, type ComparisonOut } from "@/lib/api";
import { ComparisonRadar } from "@/components/comparison-radar";
import { SessionMovement, DimensionMovementTabs } from "@/components/movement-tabs";
import { SectionHead } from "@/components/section-head";

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

function kappaVerbiage(k: number | null): string {
  if (k == null) return "样本不足";
  if (k >= 0.8) return "几乎完全一致";
  if (k >= 0.6) return "显著一致";
  if (k >= 0.4) return "中等一致";
  if (k >= 0.2) return "弱一致";
  return "差或反向";
}

export default async function ComparisonDetailPage({ params }: { params: { id: string } }) {
  const c = await getComparison(params.id);
  if (!c) {
    return (
      <div className="mx-auto flex max-w-[1200px] min-w-0 flex-col gap-md pb-4xl">
        <h1 className="m-0 font-display text-h1 text-ink">未找到该对比</h1>
        <p className="m-0 text-lede italic-display text-ink-2">comparison #{params.id} 不存在或已被删除。</p>
        <Link
          href="/comparisons"
          className="self-start border-b border-rule pb-[1px] text-sm text-ink-2 transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
        >
          ← 返回对比任务
        </Link>
      </div>
    );
  }

  const { payload } = c;
  const dimCodes = payload.dim_deltas.map((d) => d.dim_code);

  // The "quote" — what should we elevate as the page-defining number?
  // For judge comparisons we have Cohen's κ; for others use Δ weighted_score.
  const aScore = payload.run_a_summary.weighted_score;
  const bScore = payload.run_b_summary.weighted_score;
  const deltaScore =
    aScore != null && bScore != null ? bScore - aScore : null;

  const quoteValue =
    c.type === "judge"
      ? payload.kappa
      : deltaScore;
  const quoteLabel = c.type === "judge" ? "Cohen's κ" : "Δ weighted score";
  const quoteCaption =
    c.type === "judge"
      ? kappaVerbiage(payload.kappa)
      : deltaScore == null
        ? "—"
        : deltaScore > 0
          ? "Run B 整体优于 Run A"
          : deltaScore < 0
            ? "Run B 整体差于 Run A"
            : "完全持平";

  const quoteColor =
    c.type === "judge"
      ? quoteValue != null && quoteValue >= 0.6
        ? "var(--color-accent)"
        : "var(--color-warn)"
      : quoteValue != null && quoteValue > 0
        ? "var(--color-accent)"
        : quoteValue != null && quoteValue < 0
          ? "var(--color-warn)"
          : "var(--color-ink-2)";

  return (
    <div className="mx-auto flex max-w-[1200px] min-w-0 flex-col gap-3xl pb-4xl">
      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="text-caption uppercase tracking-[0.08em] text-ink-3">
        <Link href="/comparisons" className="transition-colors duration-fast ease-out hover:text-ink">
          对比任务
        </Link>
        <span aria-hidden className="px-xs text-ink-4">/</span>
        <span className="font-mono tracking-normal text-ink-2">#{c.id}</span>
      </nav>

      {/* Title strip */}
      <header className="flex flex-col gap-md">
        <div className="flex flex-wrap items-baseline gap-md">
          <h1 className="m-0 font-display text-h1 text-ink">{c.name || `${c.type} #${c.id}`}</h1>
          <span className="badge badge-info">{TYPE_LABEL[c.type] || c.type}</span>
        </div>
        <p className="m-0 max-w-[68ch] text-lede italic-display text-ink-2">
          对齐样本 <span className="font-mono not-italic tabular-nums">{payload.aligned_count}</span> 条 · 计算于{" "}
          {payload.computed_at ? new Date(payload.computed_at).toLocaleString() : "—"}
        </p>
      </header>

      {/* ── The QUOTE — centered single number ─────────────────── */}
      <figure className="my-md flex flex-col items-center gap-md border-y border-rule py-2xl text-center">
        <div className="text-caption uppercase tracking-[0.08em] text-ink-3">{quoteLabel}</div>
        <div
          className="font-display tabular-nums leading-none"
          style={{
            fontSize: "var(--text-display)",
            color: quoteColor,
          }}
        >
          {quoteValue == null
            ? "—"
            : c.type === "judge"
              ? quoteValue.toFixed(3)
              : `${quoteValue > 0 ? "+" : ""}${quoteValue.toFixed(3)}`}
        </div>
        <figcaption className="max-w-[42ch] text-lede italic-display text-ink-2">
          {quoteCaption}
        </figcaption>
      </figure>

      {/* A | B hanging strips */}
      <section className="grid grid-cols-1 gap-xl border-t border-rule pt-lg lg:grid-cols-2">
        <RunStrip
          summary={payload.run_a_summary}
          label="Run A"
          align="left"
        />
        <RunStrip
          summary={payload.run_b_summary}
          label="Run B"
          align="right"
        />
      </section>

      {/* Radar overlay */}
      <section className="flex flex-col gap-lg">
        <SectionHead eyebrow="六维" title="雷达叠加 · 差异表" />
        <div className="grid grid-cols-1 gap-xl lg:grid-cols-[5fr_7fr]">
          <div className="min-w-0">
            <ComparisonRadar
              deltas={payload.dim_deltas}
              labelA={payload.run_a_summary.name}
              labelB={payload.run_b_summary.name}
            />
          </div>
          <div className="min-w-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-rule text-caption uppercase tracking-[0.08em] text-ink-3">
                  <th className="py-sm pr-md text-left font-normal">维度</th>
                  <th className="py-sm pr-md text-right font-normal">A 均值</th>
                  <th className="py-sm pr-md text-right font-normal">B 均值</th>
                  <th className="py-sm pr-md text-right font-normal">Δ</th>
                  <th className="py-sm text-right font-normal">p</th>
                </tr>
              </thead>
              <tbody>
                {payload.dim_deltas.map((d) => {
                  const deltaCls =
                    d.delta == null
                      ? "text-ink-3"
                      : d.delta > 0
                        ? "text-accent"
                        : d.delta < 0
                          ? "text-warn"
                          : "text-ink";
                  return (
                    <tr key={d.dim_code} className="border-b border-rule last:border-0">
                      <td className="py-sm pr-md">
                        <div className="text-ink">{d.dim_name}</div>
                        <div className="font-mono text-xs text-ink-3">{d.dim_code}</div>
                      </td>
                      <td className="py-sm pr-md text-right font-mono tabular-nums">
                        {d.avg_a == null ? "—" : d.avg_a.toFixed(3)}
                      </td>
                      <td className="py-sm pr-md text-right font-mono tabular-nums">
                        {d.avg_b == null ? "—" : d.avg_b.toFixed(3)}
                      </td>
                      <td className={`py-sm pr-md text-right font-mono tabular-nums ${deltaCls}`}>
                        {d.delta == null
                          ? "—"
                          : `${d.delta > 0 ? "+" : ""}${d.delta.toFixed(3)}`}
                      </td>
                      <td className="py-sm text-right text-xs">
                        {d.chi_square_pvalue == null ? (
                          <span className="text-ink-4">n={d.sample_size}</span>
                        ) : (
                          <span
                            className={`font-mono tabular-nums ${
                              d.chi_square_pvalue < 0.05 ? "text-accent" : "text-ink-3"
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
        </div>
      </section>

      {/* Session-level movement */}
      <section className="flex flex-col gap-md">
        <SectionHead
          eyebrow="会话级"
          title="Movement"
          caption="按加权总分阈值 0.6 划线 — 哪些 case 从未通过升到通过、哪些倒退。"
          meta={`进步 ${payload.session_movement.improved.length} · 回退 ${payload.session_movement.regressed.length}`}
        />
        <SessionMovement movement={payload.session_movement} />
      </section>

      {/* Dim-level movement */}
      <section className="flex flex-col gap-md">
        <SectionHead
          eyebrow="维度级"
          title="Movement (per dim)"
          caption="单维 dim_score ≥ 0.6 判为通过；切换 tab 查看每维 case 迁移。"
        />
        <DimensionMovementTabs movements={payload.dimension_movements} dimCodes={dimCodes} />
      </section>

      {/* Judge 类型专属：一致率 */}
      {c.type === "judge" && (
        <section className="flex flex-col gap-md">
          <SectionHead
            eyebrow="一致率"
            title="Cohen's weighted κ · 混淆矩阵"
            caption="quadratic weights · 三档（0 / 0.5 / 1）。"
          />
          <div className="grid grid-cols-1 gap-xl lg:grid-cols-[1fr_2fr]">
            <div className="flex flex-col gap-sm border-r-0 border-rule lg:border-r lg:pr-xl">
              <div className="text-caption uppercase tracking-[0.08em] text-ink-3">κ 值</div>
              <div
                className="font-display tabular-nums leading-none"
                style={{ fontSize: "var(--text-display-s)", color: "var(--color-ink)" }}
              >
                {payload.kappa == null ? "—" : payload.kappa.toFixed(3)}
              </div>
              <div className="text-sm italic-display text-ink-3">
                {kappaVerbiage(payload.kappa)}
              </div>
            </div>
            <div>
              <div className="mb-sm text-caption uppercase tracking-[0.08em] text-ink-3">混淆矩阵</div>
              {payload.confusion_matrix ? (
                <table className="text-sm">
                  <thead>
                    <tr>
                      <th className="px-sm py-2xs text-left text-caption uppercase tracking-[0.08em] text-ink-3 font-normal">
                        A \ B
                      </th>
                      {LEVEL_LABEL.map((l) => (
                        <th key={l} className="px-md py-2xs text-caption uppercase tracking-[0.08em] text-ink-3 font-normal">
                          {l}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {payload.confusion_matrix.map((row, i) => (
                      <tr key={i}>
                        <td className="px-sm py-xs text-ink-3 font-mono text-xs">{LEVEL_LABEL[i]}</td>
                        {row.map((v, j) => (
                          <td
                            key={j}
                            className={`border border-rule px-md py-xs text-center font-mono tabular-nums ${
                              i === j ? "bg-accent-soft text-accent font-medium" : "text-ink-2"
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
                <div className="text-sm italic-display text-ink-3">无数据</div>
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function RunStrip({
  summary,
  label,
  align,
}: {
  summary: ComparisonOut["payload"]["run_a_summary"];
  label: string;
  align: "left" | "right";
}) {
  return (
    <article
      className={`flex flex-col gap-sm border-l-2 ${
        align === "left" ? "border-l-accent pl-md" : "border-l-warn pl-md"
      }`}
    >
      <div className="flex items-baseline justify-between gap-sm">
        <div className="text-caption uppercase tracking-[0.08em] text-ink">
          <span style={{ color: align === "left" ? "var(--color-accent)" : "var(--color-warn)" }}>
            {label}
          </span>
        </div>
        <div className="font-mono text-xs tabular-nums text-ink-3">#{summary.id}</div>
      </div>
      <div className="font-display text-h2 text-ink">{summary.name}</div>
      <dl className="grid grid-cols-2 gap-x-md gap-y-2xs text-xs font-mono text-ink-2">
        <dt className="text-ink-3">加权总分</dt>
        <dd className="m-0 text-right tabular-nums">
          {summary.weighted_score == null ? "—" : summary.weighted_score.toFixed(3)}
        </dd>
        <dt className="text-ink-3">通过率</dt>
        <dd className="m-0 text-right tabular-nums">
          {summary.pass_rate == null ? "—" : `${(summary.pass_rate * 100).toFixed(1)}%`}
        </dd>
        <dt className="text-ink-3">Dataset</dt>
        <dd className="m-0 text-right">#{summary.dataset_id}</dd>
        <dt className="text-ink-3">Bot</dt>
        <dd className="m-0 text-right">#{summary.bot_version_id}</dd>
        <dt className="text-ink-3">Judge</dt>
        <dd className="m-0 text-right">#{summary.judge_model_id}</dd>
        <dt className="text-ink-3 self-start">Prompts</dt>
        <dd className="m-0 truncate text-right">
          {Object.entries(summary.judge_prompt_version_ids)
            .map(([d, v]) => `${d}=${v}`)
            .join(", ")}
        </dd>
      </dl>
    </article>
  );
}
