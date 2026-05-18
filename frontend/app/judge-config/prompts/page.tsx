import Link from "next/link";
import { api } from "@/lib/api";
import PromptVersionRow from "@/components/prompts/prompt-version-row";

type PromptVersion = {
  id: number;
  dimension_code: string;
  version_tag: string;
  weight: number;
  notes: string | null;
  is_active: boolean;
  parent_version_id: number | null;
  created_at: string;
  updated_at: string;
  in_use_count: number;
};

const DIM_NAMES: Record<string, string> = {
  dim1: "改写忠实性",
  dim2: "跨轮记忆保留",
  dim3: "意图边界识别",
  dim4: "指代消解准确性",
  dim5: "重复请求处理",
  dim6: "用户纠错响应",
};

const DIM_ORDER = ["dim1", "dim2", "dim3", "dim4", "dim5", "dim6"];

async function getPrompts(): Promise<PromptVersion[]> {
  return api<PromptVersion[]>("/api/judge-config/prompts");
}

export default async function PromptsPage() {
  const prompts = await getPrompts();
  const byDim: Record<string, PromptVersion[]> = {};
  for (const p of prompts) {
    (byDim[p.dimension_code] ||= []).push(p);
  }
  // 每维度版本按 updated_at 倒序
  for (const code of Object.keys(byDim)) {
    byDim[code].sort(
      (a, b) =>
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    );
  }

  return (
    <div className="max-w-[1100px]">
      <div className="mb-8 flex items-start justify-between gap-6">
        <div>
          <div className="uppercase-label text-ink-3 mb-2">配置 / Prompt 版本</div>
          <h1 className="font-display text-4xl font-medium tracking-tight mb-2">
            Prompt 全功能管理
          </h1>
          <p className="text-ink-2 max-w-2xl">
            六大维度的判官 prompt 历史版本。一旦被 run 引用即不可改，需克隆为新草稿后编辑；每个维度恒有一个 active 版本，新建评测默认使用该版本。
          </p>
        </div>
        <Link
          href="/judge-config/prompts/new"
          className="shrink-0 px-4 py-2 bg-moss text-white text-sm rounded hover:opacity-90 no-underline"
        >
          + 新建草稿
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {DIM_ORDER.map((code) => {
          const name = DIM_NAMES[code];
          const list = byDim[code] || [];
          const active = list.find((p) => p.is_active);
          const draftCount = list.filter(
            (p) => !p.is_active && p.parent_version_id !== null,
          ).length;
          return (
            <div
              key={code}
              className="bg-card border border-[var(--rule)] rounded p-5 flex flex-col gap-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-display text-xl text-ink truncate">{name}</div>
                  <div className="font-mono-feat text-ink-3 text-xs mt-0.5">{code}</div>
                </div>
                <span className="text-ink-3 text-xs whitespace-nowrap">
                  {list.length} 个版本
                </span>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                {active ? (
                  <>
                    <span className="badge badge-pass font-mono-feat">
                      Active · {active.version_tag}
                    </span>
                    <span className="text-ink-3 text-xs">
                      权重 {active.weight}
                    </span>
                  </>
                ) : (
                  <span className="badge badge-warn">无 active 版本</span>
                )}
                {draftCount > 0 && (
                  <span className="badge badge-info">{draftCount} 草稿</span>
                )}
              </div>

              {active?.notes && (
                <div className="text-ink-2 text-xs leading-relaxed border-l-2 border-[var(--rule-strong)] pl-3 line-clamp-3">
                  {active.notes}
                </div>
              )}

              <div className="mt-auto pt-3 border-t border-[var(--rule)] flex items-center gap-3">
                {active && (
                  <Link
                    href={`/judge-config/prompts/${active.id}`}
                    className="text-sm text-ink-blue no-underline hover:underline"
                  >
                    查看 active 详情 →
                  </Link>
                )}
                <Link
                  href={`/judge-config/prompts/new?dim=${code}`}
                  className="ml-auto text-sm text-ink-3 no-underline hover:text-ink"
                >
                  新建草稿
                </Link>
              </div>

              {list.length > 0 && (
                <details className="text-xs" open={list.length <= 4}>
                  <summary className="cursor-pointer text-ink-3 hover:text-ink select-none">
                    所有版本（{list.length}）· hover 显示操作
                  </summary>
                  <ul className="mt-2">
                    {list.map((p) => (
                      <PromptVersionRow key={p.id} p={p} />
                    ))}
                  </ul>
                </details>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
