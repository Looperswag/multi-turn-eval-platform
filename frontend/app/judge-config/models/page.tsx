/* Hallmark · macrostructure: Catalogue (card-grid variant) · theme: EvalKit Studio (custom) */

import Link from "next/link";
import { api } from "@/lib/api";
import { PageShell } from "@/components/page-shell";

type JudgeModel = {
  id: number;
  name: string;
  provider: string;
  model_id: string;
  temperature: number;
  max_tokens: number | null;
  is_default: boolean;
  created_at: string;
};

async function getModels(): Promise<JudgeModel[]> {
  return api<JudgeModel[]>("/api/judge-config/models");
}

export default async function JudgeModelsPage() {
  const models = await getModels();
  return (
    <PageShell
      eyebrow={{ label: "配置" }}
      title="Judge 模型"
      lede="评测平台支持的 LLM judge。每个 eval_run 绑定一个模型；可通过「新建对比」做 judge 模型一致性分析。"
      meta={`共 ${models.length} 个`}
      actions={
        <Link
          href="/judge-config/models/new"
          className="inline-flex items-center gap-2xs border-b border-accent pb-[1px] text-sm font-medium text-accent transition-colors duration-fast ease-out hover:border-ink hover:text-ink"
        >
          注册新模型 <span aria-hidden>→</span>
        </Link>
      }
    >
      {models.length === 0 ? (
        <div className="border-t border-rule py-2xl text-center text-lede italic-display text-ink-3">
          尚无注册的 judge 模型。点上方「注册新模型」开始。
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-md border-t border-rule pt-lg md:grid-cols-2">
          {models.map((m) => (
            <Link
              key={m.id}
              href={`/judge-config/models/${m.id}`}
              className="group flex flex-col gap-md border-b border-rule pb-lg transition-colors duration-fast ease-out hover:border-rule-strong"
            >
              <div className="flex items-baseline justify-between gap-sm">
                <span className="badge badge-info font-mono">{m.provider}</span>
                {m.is_default && <span className="badge badge-pass">默认</span>}
              </div>
              <div>
                <div className="font-display text-h2 text-ink transition-colors duration-fast ease-out group-hover:text-accent">
                  {m.name}
                </div>
                <div className="mt-2xs break-all font-mono text-xs text-ink-3">{m.model_id}</div>
              </div>
              <dl className="flex items-baseline gap-xl border-t border-rule pt-sm text-xs">
                <div className="flex items-baseline gap-xs">
                  <dt className="text-caption uppercase tracking-[0.08em] text-ink-3">temp</dt>
                  <dd className="m-0 font-mono tabular-nums text-ink-2">{m.temperature.toFixed(2)}</dd>
                </div>
                <div className="flex items-baseline gap-xs">
                  <dt className="text-caption uppercase tracking-[0.08em] text-ink-3">max</dt>
                  <dd className="m-0 font-mono tabular-nums text-ink-2">{m.max_tokens ?? "—"}</dd>
                </div>
                <span className="ml-auto font-mono text-ink-3">
                  {new Date(m.created_at).toLocaleDateString()}
                </span>
              </dl>
            </Link>
          ))}
        </div>
      )}
    </PageShell>
  );
}
