"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
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

type TestResult = {
  ok: boolean;
  elapsed_ms: number;
  raw_response: string | null;
  error: string | null;
  model_id: string;
  provider: string;
};

export default function JudgeModelDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = parseInt(params.id, 10);
  const idValid = !Number.isNaN(id);

  const [model, setModel] = useState<JudgeModel | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({
    name: "",
    temperature: 0.1,
    max_tokens: "" as string,
    is_default: false,
  });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const m = await api<JudgeModel>(`/api/judge-config/models/${id}`);
      setModel(m);
      setEditForm({
        name: m.name,
        temperature: m.temperature,
        max_tokens: m.max_tokens?.toString() ?? "",
        is_default: m.is_default,
      });
    } catch (err) {
      setLoadError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!idValid) {
      setLoadError("无效的模型 ID");
      setLoading(false);
      return;
    }
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, idValid]);

  async function runTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await api<TestResult>(`/api/judge-config/models/${id}/test`, {
        method: "POST",
      });
      setTestResult(result);
    } catch (err) {
      setTestResult({
        ok: false,
        elapsed_ms: 0,
        raw_response: null,
        error: (err as Error).message,
        model_id: model?.model_id ?? "",
        provider: model?.provider ?? "",
      });
    } finally {
      setTesting(false);
    }
  }

  async function saveEdit() {
    if (!model) return;
    setSaving(true);
    try {
      await api<JudgeModel>(`/api/judge-config/models/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: editForm.name,
          temperature: editForm.temperature,
          max_tokens: editForm.max_tokens ? parseInt(editForm.max_tokens, 10) : null,
          is_default: editForm.is_default,
        }),
      });
      setEditing(false);
      await load();
    } catch (err) {
      alert("保存失败：" + (err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!model) return;
    if (!confirm(`确认删除模型「${model.name}」？此操作不可撤销。`)) return;
    setDeleting(true);
    try {
      await api(`/api/judge-config/models/${id}`, { method: "DELETE" });
      router.push("/judge-config/models");
    } catch (err) {
      const msg = (err as Error).message;
      const m = msg.match(/in use by (\d+) runs/);
      if (m) {
        alert(`该模型已被 ${m[1]} 个 run 使用，无法删除。`);
      } else {
        alert("删除失败：" + msg);
      }
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return <div className="max-w-[900px] text-ink-3">加载中…</div>;
  }
  if (loadError || !model) {
    return (
      <div className="max-w-[900px]">
        <div className="bg-card border border-[var(--rule)] rounded px-8 py-16 text-center text-ink-3">
          加载失败：{loadError ?? "model not found"}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[900px]">
      <div className="mb-8">
        <div className="uppercase-label text-ink-3 mb-2">
          <Link href="/judge-config/models" className="hover:text-ink">
            配置 / Judge 模型
          </Link>
          {" / "}
          <span className="font-mono-feat">#{model.id}</span>
        </div>
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h1 className="font-display text-4xl font-medium tracking-tight">{model.name}</h1>
              <span className="badge badge-info">{model.provider}</span>
              {model.is_default && <span className="badge badge-pass">默认</span>}
            </div>
            <div className="font-mono-feat text-ink-3 text-sm">{model.model_id}</div>
          </div>
          <div className="flex gap-2 shrink-0">
            <button
              onClick={() => setEditing(!editing)}
              className="px-3 py-1.5 border border-[var(--rule-strong)] rounded text-sm hover:bg-card-2"
            >
              {editing ? "取消编辑" : "编辑"}
            </button>
            <button
              onClick={remove}
              disabled={deleting}
              className="px-3 py-1.5 border border-[var(--rule-strong)] rounded text-sm text-tomato hover:bg-[var(--tomato-bg)] disabled:opacity-50"
            >
              {deleting ? "删除中…" : "删除"}
            </button>
          </div>
        </div>
      </div>

      {/* 元信息卡片 */}
      <div className="bg-card border border-[var(--rule)] rounded p-5 mb-6">
        <div className="uppercase-label text-ink-3 mb-4">模型信息</div>
        {editing ? (
          <div className="space-y-4">
            <EditField label="展示名称">
              <input
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
              />
            </EditField>
            <div className="grid grid-cols-2 gap-4">
              <EditField label="Temperature">
                <input
                  type="number"
                  step={0.1}
                  min={0}
                  max={2}
                  value={editForm.temperature}
                  onChange={(e) =>
                    setEditForm({ ...editForm, temperature: parseFloat(e.target.value) })
                  }
                  className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 font-mono-feat"
                />
              </EditField>
              <EditField label="Max Tokens（可空）">
                <input
                  type="number"
                  min={1}
                  value={editForm.max_tokens}
                  onChange={(e) => setEditForm({ ...editForm, max_tokens: e.target.value })}
                  className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 font-mono-feat"
                  placeholder="留空"
                />
              </EditField>
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={editForm.is_default}
                onChange={(e) => setEditForm({ ...editForm, is_default: e.target.checked })}
              />
              <span className="text-ink">设为默认 judge 模型</span>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={saveEdit}
                disabled={saving}
                className="px-4 py-1.5 bg-moss text-white text-sm rounded hover:opacity-90 disabled:opacity-50"
              >
                {saving ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        ) : (
          <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm">
            <MetaRow label="Provider" value={model.provider} />
            <MetaRow label="Model ID" value={model.model_id} mono />
            <MetaRow label="Temperature" value={model.temperature.toFixed(2)} mono />
            <MetaRow label="Max Tokens" value={model.max_tokens?.toString() ?? "—"} mono />
            <MetaRow label="默认" value={model.is_default ? "是" : "否"} />
            <MetaRow label="创建时间" value={new Date(model.created_at).toLocaleString()} />
          </dl>
        )}
      </div>

      {/* 测试连通性面板 */}
      <div className="bg-card border border-[var(--rule)] rounded p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="uppercase-label text-ink-3 mb-1">测试连通性</div>
            <p className="text-ink-2 text-xs">
              发起一次最小测试调用（payload: 回复严格 JSON）。用于验证 API key、网络可达性与基本响应。
            </p>
          </div>
          <button
            onClick={runTest}
            disabled={testing}
            className="px-5 py-2 bg-ink text-white text-sm rounded hover:opacity-90 disabled:opacity-50 shrink-0"
          >
            {testing ? "调用中…" : "▶ 测试调用"}
          </button>
        </div>

        {testResult && (
          <div className="mt-4 pt-4 border-t border-[var(--rule)]">
            <div className="flex items-center gap-3 mb-3">
              <span className={`badge ${testResult.ok ? "badge-pass" : "badge-fail"} text-base`} style={{ padding: "4px 12px", fontSize: 13 }}>
                {testResult.ok ? "OK" : "FAIL"} · {(testResult.elapsed_ms / 1000).toFixed(1)}s
              </span>
              <span className="text-ink-3 text-xs font-mono-feat">
                {testResult.provider} / {testResult.model_id}
              </span>
            </div>

            {testResult.raw_response && (
              <div className="mb-3">
                <div className="uppercase-label text-ink-3 mb-1.5">Raw Response（截断 500 字符）</div>
                <pre className="bg-card-2 border border-[var(--rule)] rounded p-3 text-xs font-mono-feat whitespace-pre-wrap break-words text-ink-2 max-h-60 overflow-auto">
                  {testResult.raw_response}
                </pre>
              </div>
            )}

            {testResult.error && (
              <div>
                <div className="uppercase-label text-tomato mb-1.5">Error</div>
                <pre className="bg-[var(--tomato-bg)] border border-tomato/30 rounded p-3 text-xs font-mono-feat whitespace-pre-wrap break-words text-tomato">
                  {testResult.error}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function MetaRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline gap-3">
      <dt className="uppercase-label text-ink-3 w-24 shrink-0">{label}</dt>
      <dd className={`text-ink ${mono ? "font-mono-feat" : ""} break-all`}>{value}</dd>
    </div>
  );
}

function EditField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block uppercase-label text-ink-3 mb-1.5">{label}</span>
      {children}
    </label>
  );
}
