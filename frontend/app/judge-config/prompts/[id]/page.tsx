import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { PromptDetailClient } from "./client";

type PromptDetail = {
  id: number;
  dimension_code: string;
  version_tag: string;
  prompt_template: string;
  weight: number;
  notes: string | null;
  is_active: boolean;
  parent_version_id: number | null;
  created_at: string;
  updated_at: string;
};

type PerformanceItem = {
  eval_run_id: number;
  run_name: string;
  weighted_score: number | null;
  dim_score: number | null;
  used_at: string;
};

type Performance = {
  prompt_version_id: number;
  dimension_code: string;
  version_tag: string;
  is_active: boolean;
  in_use_count: number;
  avg_weighted_score: number | null;
  avg_dim_score: number | null;
  items: PerformanceItem[];
};

type PromptOut = {
  id: number;
  dimension_code: string;
  version_tag: string;
  weight: number;
  notes: string | null;
  is_active: boolean;
  parent_version_id: number | null;
  created_at: string;
  updated_at: string;
};

const DIM_NAMES: Record<string, string> = {
  dim1: "改写忠实性",
  dim2: "跨轮记忆保留",
  dim3: "意图边界识别",
  dim4: "指代消解准确性",
  dim5: "重复请求处理",
  dim6: "用户纠错响应",
};

export default async function PromptDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const id = parseInt(params.id, 10);
  if (Number.isNaN(id)) notFound();

  let detail: PromptDetail;
  let performance: Performance;
  let siblings: PromptOut[];
  try {
    detail = await api<PromptDetail>(`/api/judge-config/prompts/${id}`);
    [performance, siblings] = await Promise.all([
      api<Performance>(`/api/judge-config/prompts/${id}/performance`),
      api<PromptOut[]>(
        `/api/judge-config/prompts?dimension_code=${detail.dimension_code}`,
      ),
    ]);
  } catch (err) {
    const msg = (err as Error).message;
    if (msg.includes("404")) notFound();
    return <div className="text-tomato">加载失败：{msg}</div>;
  }

  const dimName = DIM_NAMES[detail.dimension_code] || detail.dimension_code;
  const inUseCount = performance.in_use_count;
  const isDraft = !detail.is_active && inUseCount === 0;
  const isLocked = !detail.is_active && inUseCount > 0;

  // 状态徽章
  let statusBadge: React.ReactNode;
  if (detail.is_active) {
    statusBadge = <span className="badge badge-pass">Active</span>;
  } else if (isLocked) {
    statusBadge = (
      <span className="badge badge-neutral">
        已锁定 · 被 {inUseCount} 个 run 使用
      </span>
    );
  } else {
    statusBadge = <span className="badge badge-info">草稿（可编辑）</span>;
  }

  // 按 updated_at 倒序
  siblings.sort(
    (a, b) =>
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  );

  return (
    <div className="max-w-[1100px]">
      <div className="mb-6">
        <div className="uppercase-label text-ink-3 mb-2">
          <Link
            href="/judge-config/prompts"
            className="no-underline text-ink-3 hover:text-ink"
          >
            Prompt 版本
          </Link>
          <span className="mx-1.5">/</span>
          <span>{dimName}</span>
          <span className="mx-1.5">/</span>
          <span className="font-mono-feat">{detail.version_tag}</span>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="font-display text-4xl font-medium tracking-tight">
            {dimName}
          </h1>
          <span className="badge badge-info font-mono-feat">
            {detail.version_tag}
          </span>
          {statusBadge}
        </div>
        <div className="mt-2 text-ink-3 text-xs font-mono-feat">
          {detail.dimension_code} · 权重 {detail.weight} · 更新于{" "}
          {new Date(detail.updated_at).toLocaleString()}
          {detail.parent_version_id !== null && (
            <>
              {" · 派生自 "}
              <Link
                href={`/judge-config/prompts/${detail.parent_version_id}`}
                className="text-ink-2 hover:text-ink"
              >
                #{detail.parent_version_id}
              </Link>
            </>
          )}
        </div>
      </div>

      <PromptDetailClient
        promptId={id}
        isActive={detail.is_active}
        isDraft={isDraft}
        isLocked={isLocked}
        promptTemplate={detail.prompt_template}
        notes={detail.notes}
        performance={performance}
        siblings={siblings}
        dimName={dimName}
      />
    </div>
  );
}
