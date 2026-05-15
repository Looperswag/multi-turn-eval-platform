import Link from "next/link";
import { api, type DimensionSliceResponse, type EvalRun } from "@/lib/api";
import { DimHistogram } from "@/components/dim-histogram";
import { IssueClusterBar } from "@/components/issue-cluster-bar";

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

async function getSlice(
  id: string,
  code: DimCode,
): Promise<DimensionSliceResponse | null> {
  try {
    return await api<DimensionSliceResponse>(
      `/api/eval-runs/${id}/dimensions/${code}`,
    );
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

export default async function DimensionDetailPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams?: { dim?: string };
}) {
  const activeDim: DimCode = isDimCode(searchParams?.dim) ? searchParams!.dim! : "dim1";

  // 并发拉取 run + 全部 6 维（tab 头要均值徽章）+ 当前激活维度详情已包含在内
  const [run, ...slices] = await Promise.all([
    getRun(params.id),
    ...DIM_CODES.map((code) => getSlice(params.id, code)),
  ]);

  if (!run) {
    return (
      <div className="text-ink-3">
        run #{params.id} 未找到。{" "}
        <Link href="/eval-runs" className="text-moss">
          返回列表
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
    <div className="max-w-[1200px]">
      <div className="mb-2 text-ink-3 text-xs">
        <Link href="/eval-runs" className="text-ink-2 hover:text-ink">
          评测任务
        </Link>{" "}
        /{" "}
        <Link href={`/eval-runs/${run.id}`} className="text-ink-2 hover:text-ink">
          #{run.id}
        </Link>{" "}
        / <span className="ml-1">维度详情</span>
      </div>
      <div className="flex items-baseline gap-4 mb-2">
        <h1 className="font-display text-4xl font-medium tracking-tight">
          {run.name}
        </h1>
        <span
          className={`badge badge-${
            run.status === "success"
              ? "pass"
              : run.status === "failed"
                ? "fail"
                : "info"
          }`}
        >
          {run.status}
        </span>
      </div>
      <p className="text-ink-2 mb-6 text-sm">
        逐维度切片 · 直方图 · 触发率 · 典型 badcase 与问题归类
      </p>

      {/* Tab bar — 每个 tab 显示维度名 + 均值徽章 */}
      <div className="flex flex-wrap gap-2 mb-6 border-b border-[var(--rule)] pb-3">
        {DIM_CODES.map((code) => {
          const s = sliceByCode.get(code);
          const avg = s?.stats.avg_score ?? null;
          const active = code === activeDim;
          const passColor = avg == null
            ? "text-ink-3"
            : avg >= 0.6
              ? "text-moss"
              : "text-tomato";
          return (
            <Link
              key={code}
              href={`/eval-runs/${run.id}/dimensions?dim=${code}`}
              className={`px-3 py-1.5 rounded text-sm border transition-colors no-underline flex items-center gap-2 ${
                active
                  ? "border-moss bg-[var(--moss-bg)] text-ink"
                  : "border-[var(--rule)] text-ink-2 hover:bg-[var(--rule)]"
              }`}
            >
              <span className="font-mono-feat text-xs text-ink-3">{code}</span>
              <span>{s?.dim_name ?? code}</span>
              <span className={`text-xs font-mono-feat tabular-nums ${passColor}`}>
                {fmtScore(avg)}
              </span>
            </Link>
          );
        })}
      </div>

      {!slice ? (
        <div className="text-ink-3 text-sm py-8">该维度切片加载失败。</div>
      ) : (
        <DimensionView slice={slice} runId={run.id} />
      )}
    </div>
  );
}

function DimensionView({
  slice,
  runId,
}: {
  slice: DimensionSliceResponse;
  runId: number;
}) {
  const { stats, histogram, top_badcases, issue_clusters, prompt_version } = slice;
  const passColor = (stats.avg_score ?? 0) >= 0.6 ? "moss" : "tomato";

  return (
    <>
      {/* 4 大数字卡片 */}
      <section className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-card border border-[var(--rule)] rounded p-5">
          <div className="uppercase-label text-ink-3 mb-2">平均分</div>
          <div
            className={`font-display text-4xl font-medium tabular-nums text-${passColor}`}
          >
            {fmtScore(stats.avg_score)}
          </div>
          <div className="text-ink-3 text-xs mt-1">
            min {fmtScore(stats.min_score, 2)} · max{" "}
            {fmtScore(stats.max_score, 2)}
          </div>
        </div>
        <div className="bg-card border border-[var(--rule)] rounded p-5">
          <div className="uppercase-label text-ink-3 mb-2">通过率</div>
          <div className="font-display text-4xl font-medium tabular-nums text-ink">
            {fmtPercent(stats.pass_rate)}
          </div>
          <div className="text-ink-3 text-xs mt-1">
            {stats.pass_count}/{stats.applicable_count} · 阈值 0.6
          </div>
        </div>
        <div className="bg-card border border-[var(--rule)] rounded p-5">
          <div className="uppercase-label text-ink-3 mb-2">触发率</div>
          <div className="font-display text-4xl font-medium tabular-nums text-ink">
            {fmtPercent(stats.trigger_rate)}
          </div>
          <div className="text-ink-3 text-xs mt-1">
            适用 {stats.applicable_count} / 总 {stats.total_cases}
          </div>
        </div>
        <div className="bg-card border border-[var(--rule)] rounded p-5">
          <div className="uppercase-label text-ink-3 mb-2">样本数</div>
          <div className="font-display text-4xl font-medium tabular-nums text-ink">
            {stats.total_cases}
          </div>
          <div className="text-ink-3 text-xs mt-1">
            权重 {(slice.weight * 100).toFixed(0)}%
          </div>
        </div>
      </section>

      {/* 直方图 + Prompt 版本 */}
      <section className="grid grid-cols-[2fr_1fr] gap-6 mb-8">
        <div className="bg-card border border-[var(--rule)] rounded p-6">
          <div className="uppercase-label text-ink-3 mb-4">
            分数分布 · {slice.dim_name}
          </div>
          <DimHistogram buckets={histogram} />
        </div>
        <div className="bg-card border border-[var(--rule)] rounded p-6">
          <div className="uppercase-label text-ink-3 mb-3">Prompt 版本</div>
          {prompt_version ? (
            <div>
              <div className="flex items-baseline gap-2 mb-2">
                <span className="font-display text-2xl font-medium">
                  {prompt_version.version_tag}
                </span>
                <span className="text-ink-3 text-xs font-mono-feat">
                  #{prompt_version.id}
                </span>
              </div>
              <p className="text-ink-2 text-xs leading-relaxed">
                {prompt_version.notes || "—"}
              </p>
            </div>
          ) : (
            <div className="text-ink-3 text-xs">未绑定 prompt 版本</div>
          )}
        </div>
      </section>

      {/* Top 5 Badcase 表格 */}
      <section className="bg-card border border-[var(--rule)] rounded p-6 mb-8">
        <div className="uppercase-label text-ink-3 mb-4">
          Top 5 Badcase · {slice.dim_name} 最低分
        </div>
        {top_badcases.length === 0 ? (
          <div className="text-ink-3 text-xs py-4">暂无适用样本。</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-ink-3 uppercase-label border-b border-[var(--rule)]">
                <th className="text-left py-2">case</th>
                <th className="text-left py-2">conv_id</th>
                <th className="text-right py-2">维度分</th>
                <th className="text-right py-2">加权分</th>
                <th className="text-left py-2 pl-4">解释</th>
              </tr>
            </thead>
            <tbody>
              {top_badcases.map((b) => (
                <tr
                  key={b.case_id}
                  className="border-b border-[var(--rule)] last:border-0"
                >
                  <td className="py-2">
                    <Link
                      href={`/eval-runs/${runId}/badcases?case_id=${b.case_id}`}
                      className="text-moss hover:underline font-mono-feat text-xs"
                    >
                      #{b.case_id}
                    </Link>
                  </td>
                  <td className="py-2 font-mono-feat text-xs text-ink-2">
                    {b.conversation_id_src}
                  </td>
                  <td className="py-2 text-right font-mono-feat tabular-nums">
                    <span
                      className={
                        (b.dim_score ?? 0) >= 0.6 ? "text-ink" : "text-tomato"
                      }
                    >
                      {fmtScore(b.dim_score)}
                    </span>
                  </td>
                  <td className="py-2 text-right font-mono-feat tabular-nums text-ink-2">
                    {fmtScore(b.weighted_score)}
                  </td>
                  <td className="py-2 pl-4 text-ink-2 text-xs leading-relaxed">
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
        )}
      </section>

      {/* Issue cluster */}
      <section className="bg-card border border-[var(--rule)] rounded p-6 mb-8">
        <div className="uppercase-label text-ink-3 mb-4">
          常见问题归类 · 关键词频次
        </div>
        <IssueClusterBar clusters={issue_clusters} />
      </section>

      {/* 返回 */}
      <div className="flex gap-3 flex-wrap">
        <Link
          href={`/eval-runs/${runId}`}
          className="px-4 py-2 border border-[var(--rule-strong)] rounded text-sm hover:bg-[var(--rule)]"
        >
          ← 返回看板
        </Link>
        <Link
          href={`/eval-runs/${runId}/badcases`}
          className="px-4 py-2 border border-[var(--rule-strong)] rounded text-sm hover:bg-[var(--rule)]"
        >
          钻取 Badcase
        </Link>
      </div>
    </>
  );
}
