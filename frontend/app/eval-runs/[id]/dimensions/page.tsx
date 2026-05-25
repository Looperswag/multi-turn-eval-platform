/* Hallmark · macrostructure: Stat-Led (sub-variant) · theme: EvalKit Studio (custom) */

import Link from "next/link";
import { api, type DimensionSliceResponse, type EvalRun } from "@/lib/api";
import { DimHistogram } from "@/components/dim-histogram";
import { IssueClusterBar } from "@/components/issue-cluster-bar";
import { SectionHead } from "@/components/section-head";

const DIM_CODES = ["dim1", "dim2", "dim3", "dim4", "dim5", "dim6"] as const;
type DimCode = (typeof DIM_CODES)[number];

function isDimCode(v: string | undefined): v is DimCode {
  return !!v && (DIM_CODES as readonly string[]).includes(v);
}

async function getRun(id: string): Promise<EvalRun | null> {
  try {
    return await api<EvalRun>(`/api/eval-runs/${id}`);
  } catch (err) {
    console.error(`[getRun ${id}]`, err);
    return null;
  }
}

async function getSlice(id: string, code: DimCode): Promise<DimensionSliceResponse | null> {
  try {
    return await api<DimensionSliceResponse>(`/api/eval-runs/${id}/dimensions/${code}`);
  } catch (err) {
    console.error(`[getSlice ${id}/${code}]`, err);
    return null;
  }
}

function fmtScore(v: number | null | undefined, digits = 3): string {
  if (v == null) return "—";
  return v.toFixed(digits);
}

function fmtPercent(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function statusBadgeClass(status: string): string {
  if (status === "success") return "badge badge-pass";
  if (status === "failed") return "badge badge-fail";
  if (status === "partial") return "badge badge-warn";
  if (status === "cancelled") return "badge badge-neutral";
  return "badge badge-info";
}

export default async function DimensionDetailPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams?: { dim?: string };
}) {
  const activeDim: DimCode = isDimCode(searchParams?.dim) ? searchParams!.dim! : "dim1";

  const [run, ...slices] = await Promise.all([
    getRun(params.id),
    ...DIM_CODES.map((code) => getSlice(params.id, code)),
  ]);

  if (!run) {
    return (
      <div className="mx-auto flex max-w-[1200px] min-w-0 flex-col gap-md pb-4xl">
        <h1 className="m-0 font-display text-h1 text-ink">未找到该评测</h1>
        <Link href="/eval-runs" className="self-start border-b border-rule pb-[1px] text-sm text-ink-2 hover:border-ink hover:text-ink">
          ← 返回评测任务
        </Link>
      </div>
    );
  }

  const sliceByCode = new Map<DimCode, DimensionSliceResponse>();
  DIM_CODES.forEach((code, idx) => {
    const s = slices[idx];
    if (s) sliceByCode.set(code, s);
  });
  const slice = sliceByCode.get(activeDim);

  return (
    <div className="mx-auto flex max-w-[1200px] min-w-0 flex-col gap-3xl pb-4xl">
      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="text-caption uppercase tracking-[0.08em] text-ink-3">
        <Link href="/eval-runs" className="transition-colors duration-fast ease-out hover:text-ink">
          评测任务
        </Link>
        <span aria-hidden className="px-xs text-ink-4">/</span>
        <Link href={`/eval-runs/${run.id}`} className="font-mono normal-case tracking-normal text-ink-3 transition-colors duration-fast ease-out hover:text-ink">
          #{run.id}
        </Link>
        <span aria-hidden className="px-xs text-ink-4">/</span>
        <span className="text-ink-2">维度详情</span>
      </nav>

      {/* Title strip */}
      <header className="flex flex-col gap-md">
        <div className="flex flex-wrap items-baseline gap-md">
          <h1 className="m-0 font-display text-h1 text-ink">{run.name}</h1>
          <span className={statusBadgeClass(run.status)}>{run.status}</span>
        </div>
        <p className="m-0 max-w-[68ch] text-lede italic-display text-ink-2">
          逐维度切片 · 直方图 · 触发率 · 典型 badcase 与问题归类。
        </p>
      </header>

      {/* Dimension tabs — editorial, underline-based */}
      <nav aria-label="维度" className="flex min-w-0 flex-wrap gap-x-md gap-y-xs border-b border-rule pb-xs">
        {DIM_CODES.map((code) => {
          const s = sliceByCode.get(code);
          const avg = s?.stats.avg_score ?? null;
          const active = code === activeDim;
          const passColor =
            avg == null ? "text-ink-3" : avg >= 0.6 ? "text-accent" : "text-warn";
          return (
            <Link
              key={code}
              href={`/eval-runs/${run.id}/dimensions?dim=${code}`}
              className={`flex items-baseline gap-xs border-b-2 py-xs text-sm transition-colors duration-fast ease-out ${
                active
                  ? "border-b-ink text-ink"
                  : "border-b-transparent text-ink-2 hover:border-b-rule-strong hover:text-ink"
              }`}
            >
              <span className="font-mono text-xs text-ink-3">{code}</span>
              <span>{s?.dim_name ?? code}</span>
              <span className={`font-mono text-xs tabular-nums ${passColor}`}>{fmtScore(avg)}</span>
            </Link>
          );
        })}
      </nav>

      {!slice ? (
        <div className="py-xl text-center text-lede italic-display text-ink-3">该维度切片加载失败。</div>
      ) : (
        <DimensionView slice={slice} runId={run.id} />
      )}
    </div>
  );
}

function DimensionView({ slice, runId }: { slice: DimensionSliceResponse; runId: number }) {
  const { stats, histogram, top_badcases, issue_clusters, prompt_version } = slice;
  const passing = (stats.avg_score ?? 0) >= 0.6;
  const heroColor = passing ? "var(--color-accent)" : "var(--color-warn)";

  return (
    <>
      {/* Hero — 单数字主导 */}
      <header className="grid grid-cols-1 gap-xl border-t border-rule pt-lg md:grid-cols-[auto_minmax(0,1fr)]">
        <div className="flex flex-col gap-2xs">
          <span className="text-caption uppercase tracking-[0.08em] text-ink-3">平均分</span>
          <span
            className="font-display tabular-nums leading-none"
            style={{ fontSize: "var(--text-display)", color: heroColor }}
          >
            {fmtScore(stats.avg_score)}
          </span>
          <span className="font-mono text-xs tabular-nums text-ink-3">
            min {fmtScore(stats.min_score, 2)} · max {fmtScore(stats.max_score, 2)}
          </span>
        </div>
        <dl className="grid grid-cols-2 content-end gap-y-md text-sm md:grid-cols-3 md:gap-x-xl">
          <div className="flex flex-col gap-2xs">
            <dt className="text-caption uppercase tracking-[0.08em] text-ink-3">通过率</dt>
            <dd className="m-0 font-mono tabular-nums text-h3 text-ink">{fmtPercent(stats.pass_rate)}</dd>
            <span className="font-mono text-xs tabular-nums text-ink-3">
              {stats.pass_count}/{stats.applicable_count} · 阈值 0.6
            </span>
          </div>
          <div className="flex flex-col gap-2xs">
            <dt className="text-caption uppercase tracking-[0.08em] text-ink-3">触发率</dt>
            <dd className="m-0 font-mono tabular-nums text-h3 text-ink">{fmtPercent(stats.trigger_rate)}</dd>
            <span className="font-mono text-xs tabular-nums text-ink-3">
              适用 {stats.applicable_count}/{stats.total_cases}
            </span>
          </div>
          <div className="flex flex-col gap-2xs">
            <dt className="text-caption uppercase tracking-[0.08em] text-ink-3">样本数</dt>
            <dd className="m-0 font-mono tabular-nums text-h3 text-ink">{stats.total_cases}</dd>
            <span className="font-mono text-xs tabular-nums text-ink-3">权重 {(slice.weight * 100).toFixed(0)}%</span>
          </div>
        </dl>
      </header>

      {/* 直方图 + Prompt 版本 */}
      <section className="flex flex-col gap-lg">
        <SectionHead eyebrow="分布" title={`分数分布 · ${slice.dim_name}`} />
        <div className="grid grid-cols-1 gap-xl lg:grid-cols-[2fr_1fr]">
          <div className="min-w-0">
            <DimHistogram buckets={histogram} />
          </div>
          <div className="flex flex-col gap-sm border-l-0 border-rule lg:border-l lg:pl-xl">
            <div className="text-caption uppercase tracking-[0.08em] text-ink-3">Prompt 版本</div>
            {prompt_version ? (
              <>
                <div className="flex items-baseline gap-sm">
                  <span className="font-display text-h2 text-ink">{prompt_version.version_tag}</span>
                  <span className="font-mono text-xs tabular-nums text-ink-3">#{prompt_version.id}</span>
                </div>
                <p className="m-0 text-xs leading-relaxed text-ink-2">{prompt_version.notes || "—"}</p>
              </>
            ) : (
              <div className="text-xs italic-display text-ink-3">未绑定 prompt 版本</div>
            )}
          </div>
        </div>
      </section>

      {/* Top badcase 表 */}
      <section className="flex flex-col gap-md">
        <SectionHead eyebrow="Badcase" title={`Top 5 · ${slice.dim_name} 最低分`} />
        {top_badcases.length === 0 ? (
          <div className="py-xl text-center text-lede italic-display text-ink-3">该维度暂无适用样本。</div>
        ) : (
          <div className="min-w-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-rule text-caption uppercase tracking-[0.08em] text-ink-3">
                  <th className="py-sm pr-md text-left font-normal">case</th>
                  <th className="py-sm pr-md text-left font-normal">conv_id</th>
                  <th className="py-sm pr-md text-right font-normal">维度分</th>
                  <th className="py-sm pr-md text-right font-normal">加权分</th>
                  <th className="py-sm text-left font-normal">解释</th>
                </tr>
              </thead>
              <tbody>
                {top_badcases.map((b) => (
                  <tr key={b.case_id} className="border-b border-rule last:border-0 transition-colors duration-fast ease-out hover:bg-paper-2">
                    <td className="py-sm pr-md">
                      <Link
                        href={`/eval-runs/${runId}/badcases?case_id=${b.case_id}`}
                        className="border-b border-rule pb-[1px] font-mono text-xs text-accent transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
                      >
                        #{b.case_id}
                      </Link>
                    </td>
                    <td className="py-sm pr-md font-mono text-xs text-ink-2">{b.conversation_id_src}</td>
                    <td className="py-sm pr-md text-right font-mono tabular-nums">
                      <span className={(b.dim_score ?? 0) >= 0.6 ? "text-ink" : "text-warn"}>
                        {fmtScore(b.dim_score)}
                      </span>
                    </td>
                    <td className="py-sm pr-md text-right font-mono tabular-nums text-ink-2">{fmtScore(b.weighted_score)}</td>
                    <td className="py-sm text-xs italic-display leading-relaxed text-ink-2">
                      {b.explanation
                        ? b.explanation.length > 80
                          ? b.explanation.slice(0, 80) + "…"
                          : b.explanation
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Issue cluster */}
      <section className="flex flex-col gap-md">
        <SectionHead eyebrow="问题归类" title="关键词频次" />
        <IssueClusterBar clusters={issue_clusters} />
      </section>

      {/* Footer · navigation */}
      <section className="flex flex-col gap-md border-t border-rule pt-lg">
        <div className="text-caption uppercase tracking-[0.08em] text-ink-3">下一步</div>
        <div className="flex flex-wrap items-center gap-xl text-sm">
          <Link
            href={`/eval-runs/${runId}`}
            className="inline-flex items-center gap-2xs border-b border-rule pb-[1px] text-ink-2 transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
          >
            <span aria-hidden>←</span> 返回看板
          </Link>
          <Link
            href={`/eval-runs/${runId}/badcases`}
            className="inline-flex items-center gap-2xs border-b border-rule pb-[1px] text-ink-2 transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
          >
            钻取 Badcase <span aria-hidden>→</span>
          </Link>
        </div>
      </section>
    </>
  );
}
