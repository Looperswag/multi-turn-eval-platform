"use client";
import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  api,
  RegressionSetDetail,
  RegressionSetFromBadcasesResult,
} from "@/lib/api";

type EvalRunMini = { id: number; name: string };

export default function RegressionSetDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const rsId = parseInt(params.id, 10);

  const [detail, setDetail] = useState<RegressionSetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [showFromBadcase, setShowFromBadcase] = useState(false);

  const fetchDetail = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api<RegressionSetDetail>(`/api/regression-sets/${rsId}`);
      setDetail(d);
      setErr(null);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [rsId]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  async function deleteItem(itemId: number) {
    if (!confirm("确定移除？")) return;
    await api(`/api/regression-sets/${rsId}/items/${itemId}`, {
      method: "DELETE",
    });
    fetchDetail();
  }

  async function deleteSet() {
    if (!confirm("删除整个回归集？此操作不可撤销。")) return;
    await api(`/api/regression-sets/${rsId}`, { method: "DELETE" });
    router.push("/regression-sets");
  }

  if (loading && !detail) {
    return <div className="text-ink-3">加载中…</div>;
  }
  if (err) {
    return <div className="text-tomato">加载失败：{err}</div>;
  }
  if (!detail) return null;

  return (
    <div className="max-w-[1100px]">
      <div className="mb-8">
        <div className="uppercase-label text-ink-3 mb-2">回归集 / 详情</div>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-4xl font-medium tracking-tight mb-2">
              {detail.name}
            </h1>
            {detail.description && (
              <p className="text-ink-2 max-w-2xl">{detail.description}</p>
            )}
            <div className="text-ink-3 text-xs mt-1 font-mono-feat">
              #{detail.id} · 创建于 {new Date(detail.created_at).toLocaleString()}
            </div>
          </div>
          <button
            onClick={deleteSet}
            className="text-tomato hover:bg-[var(--rule)] px-3 py-1.5 rounded text-sm"
          >
            删除集合
          </button>
        </div>
      </div>

      <div className="mb-4 flex items-center justify-between">
        <div className="text-sm text-ink-2">
          共 <span className="font-mono-feat font-medium">{detail.items.length}</span> 条
        </div>
        <button
          onClick={() => setShowFromBadcase(true)}
          className="px-3 py-1.5 bg-moss text-white text-sm rounded hover:opacity-90"
        >
          + 从 badcase 一键加入
        </button>
      </div>

      <div className="bg-card border border-[var(--rule)] rounded">
        {detail.items.length === 0 ? (
          <div className="px-8 py-16 text-center text-ink-3 text-sm">
            集合为空。可在 <code className="font-mono-feat">/eval-runs/[id]/badcases</code> Drawer
            中加入，或点击右上角批量加入。
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--rule)] text-ink-3 uppercase-label">
                <th className="px-4 py-3 text-left">conv_id_src</th>
                <th className="px-4 py-3 text-left">维度标签</th>
                <th className="px-4 py-3 text-left">溯源 case</th>
                <th className="px-4 py-3 text-right">加入时间</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {detail.items.map((it) => (
                <tr key={it.id} className="border-b border-[var(--rule)] last:border-0">
                  <td className="px-4 py-2.5 font-mono-feat">
                    {it.conversation_id_src || `#${it.conversation_id}`}
                  </td>
                  <td className="px-4 py-2.5">
                    {it.dimension_tag ? (
                      <span className="badge badge-neutral text-xs">
                        {it.dimension_tag}
                      </span>
                    ) : (
                      <span className="text-ink-3 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-ink-3 text-xs font-mono-feat">
                    {it.source_case_id ? `case #${it.source_case_id}` : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right text-ink-3 text-xs">
                    {new Date(it.added_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      onClick={() => deleteItem(it.id)}
                      className="text-ink-3 hover:text-tomato"
                      title="移除"
                    >
                      ×
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showFromBadcase && (
        <FromBadcasesDialog
          rsId={rsId}
          onClose={() => setShowFromBadcase(false)}
          onDone={() => {
            setShowFromBadcase(false);
            fetchDetail();
          }}
        />
      )}
    </div>
  );
}

function FromBadcasesDialog({
  rsId,
  onClose,
  onDone,
}: {
  rsId: number;
  onClose: () => void;
  onDone: () => void;
}) {
  const [runs, setRuns] = useState<EvalRunMini[]>([]);
  const [runId, setRunId] = useState<number | "">("");
  const [tag, setTag] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<RegressionSetFromBadcasesResult | null>(null);

  useEffect(() => {
    api<EvalRunMini[]>("/api/eval-runs")
      .then((r) => {
        setRuns(r);
        if (r.length > 0) setRunId(r[0].id);
      })
      .catch((e) => setErr((e as Error).message));
  }, []);

  async function submit() {
    if (!runId || !tag.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await api<RegressionSetFromBadcasesResult>(
        `/api/regression-sets/${rsId}/items/from-badcases`,
        {
          method: "POST",
          body: JSON.stringify({
            eval_run_id: runId,
            tag: tag.trim(),
          }),
        },
      );
      setResult(res);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-card border border-[var(--rule)] rounded p-6 w-[440px]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="uppercase-label text-ink-3 mb-3">从 badcase 一键加入</div>
        <h2 className="font-display text-xl font-medium mb-4">选择 run 与 tag</h2>

        <label className="block mb-3">
          <span className="block uppercase-label text-ink-3 mb-1">评测 run</span>
          <select
            value={runId}
            onChange={(e) => setRunId(parseInt(e.target.value, 10))}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 text-sm"
          >
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                #{r.id} · {r.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block mb-4">
          <span className="block uppercase-label text-ink-3 mb-1">tag 名</span>
          <input
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 text-sm"
            placeholder="e.g. 抽指代失败"
          />
        </label>

        {result && (
          <div className="mb-4 p-3 rounded bg-[var(--moss-bg)] text-moss text-sm">
            匹配 {result.matched_cases} 条 · 新增 {result.added} 条 · 跳过 {result.skipped} 条
          </div>
        )}
        {err && <div className="mb-4 text-sm text-tomato">{err}</div>}

        <div className="flex justify-end gap-2">
          <button
            onClick={result ? onDone : onClose}
            className="px-4 py-2 border border-[var(--rule-strong)] rounded text-sm"
          >
            {result ? "完成" : "取消"}
          </button>
          {!result && (
            <button
              onClick={submit}
              disabled={busy || !runId || !tag.trim()}
              className="px-4 py-2 bg-moss text-white text-sm rounded hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "处理中…" : "提交"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
