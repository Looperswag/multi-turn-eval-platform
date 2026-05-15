import Link from "next/link";
import { api } from "@/lib/api";

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
    <div className="max-w-[1100px]">
      <div className="mb-8 flex items-start justify-between gap-6">
        <div>
          <div className="uppercase-label text-ink-3 mb-2">配置 / Judge 模型</div>
          <h1 className="font-display text-4xl font-medium tracking-tight mb-2">Judge 模型</h1>
          <p className="text-ink-2 max-w-2xl">
            评测平台支持的 LLM judge。每个 eval_run 绑定一个模型；可通过「新建对比」做 judge 模型一致性分析。
          </p>
        </div>
        <Link
          href="/judge-config/models/new"
          className="shrink-0 px-4 py-2 bg-moss text-white text-sm rounded hover:opacity-90"
        >
          + 注册新模型
        </Link>
      </div>

      {models.length === 0 ? (
        <div className="bg-card border border-[var(--rule)] rounded px-8 py-16 text-center text-ink-3">
          还没有注册任何 judge 模型。点击右上角「+ 注册新模型」开始。
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {models.map((m) => (
            <Link
              key={m.id}
              href={`/judge-config/models/${m.id}`}
              className="bg-card border border-[var(--rule)] rounded p-5 hover:border-[var(--rule-strong)] transition-colors block"
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <span className="badge badge-info">{m.provider}</span>
                {m.is_default && <span className="badge badge-pass">默认</span>}
              </div>
              <div className="font-display text-2xl font-medium text-ink mb-1.5 leading-tight">{m.name}</div>
              <div className="font-mono-feat text-xs text-ink-3 mb-4 break-all">{m.model_id}</div>
              <div className="flex items-center gap-4 text-xs text-ink-3 pt-3 border-t border-[var(--rule)]">
                <span>
                  <span className="uppercase-label">temp</span>{" "}
                  <span className="font-mono-feat tabular-nums text-ink-2">{m.temperature.toFixed(2)}</span>
                </span>
                <span>
                  <span className="uppercase-label">max</span>{" "}
                  <span className="font-mono-feat tabular-nums text-ink-2">{m.max_tokens ?? "—"}</span>
                </span>
                <span className="ml-auto text-ink-3">{new Date(m.created_at).toLocaleDateString()}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
