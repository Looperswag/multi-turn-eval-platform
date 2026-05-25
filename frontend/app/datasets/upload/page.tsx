"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

// 浏览器侧 API origin（multipart 用裸 fetch，不走 lib/api 因其强 Content-Type）
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type TurnIndexSource = "turn_index" | "timestamp";

type Mapping = {
  conversation_id: string | null;
  turn_index: string | null;
  user_query: string | null;
  rewritten_query: string | null;
  dimension_tag: string | null;
  quality_label: string | null;
  issue_type: string | null;
  turn_index_source: TurnIndexSource;
};

type ParseResult = {
  parse_session_id: string;
  columns: string[];
  sample_rows: Record<string, unknown>[];
  suggested_mapping: Mapping;
  format: string;
  total_rows: number;
};

type ValidationIssue = {
  severity: "error" | "warning" | "info";
  code: string;
  message: string;
  count: number;
  sample: string[];
};

type ValidationReport = {
  issues: ValidationIssue[];
  total_conversations: number;
  total_turns: number;
  is_passable: boolean;
};

type ConversationPreview = {
  conversation_id: string;
  dimension_tag: string | null;
  quality_label: string | null;
  issue_type: string | null;
  total_turns: number;
  turns: {
    turn_index: number;
    user_query: string;
    rewritten_query?: string | null;
    timestamp?: string | null;
  }[];
};

type PreviewResult = {
  validation_report: ValidationReport;
  preview_conversations: ConversationPreview[];
};

type BotVersion = { id: number; name: string; version_tag: string };

type MappingFieldKey = Exclude<keyof Mapping, "turn_index_source">;

const TARGET_FIELDS: { key: MappingFieldKey; label: string; required: boolean; hint?: string }[] = [
  { key: "conversation_id", label: "Conversation ID", required: true, hint: "会话唯一标识" },
  { key: "turn_index", label: "轮次序号", required: true, hint: "数字序号 或 用于排序的时间戳" },
  { key: "user_query", label: "User Query", required: true, hint: "用户输入文本" },
  { key: "rewritten_query", label: "Rewritten Query", required: false, hint: "Bot 改写（可选）" },
  { key: "dimension_tag", label: "Dimension Tag", required: false, hint: "维度标签（可选）" },
  { key: "quality_label", label: "Quality Label", required: false, hint: "good/bad（可选）" },
  { key: "issue_type", label: "Issue Type", required: false, hint: "问题类型（可选）" },
];

const STEPS = [
  { id: 1, name: "选文件" },
  { id: 2, name: "字段映射" },
  { id: 3, name: "预览校验" },
  { id: 4, name: "确认入库" },
];

export default function DatasetUploadWizardPage() {
  const router = useRouter();
  const [step, setStep] = useState<number>(1);

  // Step 1
  const [file, setFile] = useState<File | null>(null);
  const [parseLoading, setParseLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);

  // Step 2/3
  const [mapping, setMapping] = useState<Mapping>({
    conversation_id: null,
    turn_index: null,
    user_query: null,
    rewritten_query: null,
    dimension_tag: null,
    quality_label: null,
    issue_type: null,
    turn_index_source: "turn_index",
  });
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewResult, setPreviewResult] = useState<PreviewResult | null>(null);
  const [showIssueDetails, setShowIssueDetails] = useState(false);

  // Step 4
  const [datasetName, setDatasetName] = useState("");
  const [version, setVersion] = useState("v1");
  const [description, setDescription] = useState("");
  const [bots, setBots] = useState<BotVersion[]>([]);
  const [attachBotId, setAttachBotId] = useState<number | null>(null);
  const [confirming, setConfirming] = useState(false);

  // 拉 bot version 列表（仅用于 step 4 可选 attach）
  useEffect(() => {
    api<BotVersion[]>("/api/bot-versions")
      .then(setBots)
      .catch(() => setBots([]));
  }, []);

  // 文件名预填 dataset name
  useEffect(() => {
    if (file && !datasetName) {
      const base = file.name.replace(/\.(xlsx|csv|json|xls)$/i, "");
      setDatasetName(base);
    }
  }, [file, datasetName]);

  async function handleParse() {
    if (!file) {
      setError("请先选择文件");
      return;
    }
    setError(null);
    setParseLoading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/api/datasets/upload/parse`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`解析失败 (${res.status}): ${txt}`);
      }
      const data: ParseResult = await res.json();
      setParseResult(data);
      setMapping(data.suggested_mapping);
      setStep(2);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setParseLoading(false);
    }
  }

  async function fetchPreview(m: Mapping) {
    if (!parseResult) return;
    setPreviewLoading(true);
    setError(null);
    try {
      const data = await api<PreviewResult>("/api/datasets/upload/preview", {
        method: "POST",
        body: JSON.stringify({
          parse_session_id: parseResult.parse_session_id,
          mapping: m,
        }),
      });
      setPreviewResult(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleMappingNext() {
    await fetchPreview(mapping);
    setStep(3);
  }

  async function handleConfirm() {
    if (!parseResult) return;
    if (!datasetName.trim()) {
      setError("请填写评测集名称");
      return;
    }
    setError(null);
    setConfirming(true);
    try {
      const result = await api<{ id: number }>("/api/datasets/upload/confirm", {
        method: "POST",
        body: JSON.stringify({
          parse_session_id: parseResult.parse_session_id,
          mapping,
          dataset_name: datasetName.trim(),
          version: version.trim() || "v1",
          description: description.trim() || null,
          attach_bot_version_id: attachBotId,
        }),
      });
      router.push(`/datasets`);
      router.refresh();
      // 兜底 hard navigate（dev 模式下 refresh 偶发不触发）
      setTimeout(() => {
        window.location.href = "/datasets";
      }, 200);
      void result;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setConfirming(false);
    }
  }

  function applySuggested() {
    if (parseResult) setMapping(parseResult.suggested_mapping);
  }

  return (
    <div className="mx-auto flex max-w-[1100px] min-w-0 flex-col gap-2xl pb-4xl">
      <nav aria-label="Breadcrumb" className="text-caption uppercase tracking-[0.08em] text-ink-3">
        <Link href="/datasets" className="transition-colors duration-fast ease-out hover:text-ink">数据 / 评测集</Link>
        <span aria-hidden className="px-xs text-ink-4">/</span>
        <span className="text-ink-2">上传</span>
      </nav>
      <header className="flex flex-col gap-sm">
        <div className="text-caption uppercase tracking-[0.08em] text-ink-3">
          <span className="font-mono tabular-nums">{step}/4</span>
          <span aria-hidden className="px-xs text-ink-4">·</span>
          <span className="italic-display normal-case tracking-normal">上传向导</span>
        </div>
        <h1 className="m-0 font-display text-h1 text-ink">上传新评测集</h1>
        <p className="m-0 max-w-[68ch] text-lede italic-display text-ink-2">
          支持 Excel / CSV / JSON 多格式 · 自动字段映射 · 全量校验 · 5 条对话预览。
        </p>
      </header>

      <StepIndicator current={step} />

      {error && (
        <div className="my-4 border border-tomato bg-tomato/10 text-tomato text-sm px-4 py-2 rounded">
          {error}
        </div>
      )}

      <div className="mt-6">
        {step === 1 && (
          <Step1
            file={file}
            onSelect={setFile}
            onNext={handleParse}
            loading={parseLoading}
          />
        )}
        {step === 2 && parseResult && (
          <Step2
            parseResult={parseResult}
            mapping={mapping}
            setMapping={setMapping}
            onBack={() => setStep(1)}
            onNext={handleMappingNext}
            onApplySuggested={applySuggested}
            loading={previewLoading}
          />
        )}
        {step === 3 && previewResult && (
          <Step3
            preview={previewResult}
            showIssueDetails={showIssueDetails}
            setShowIssueDetails={setShowIssueDetails}
            onBack={() => setStep(2)}
            onNext={() => setStep(4)}
          />
        )}
        {step === 4 && (
          <Step4
            datasetName={datasetName}
            setDatasetName={setDatasetName}
            version={version}
            setVersion={setVersion}
            description={description}
            setDescription={setDescription}
            bots={bots}
            attachBotId={attachBotId}
            setAttachBotId={setAttachBotId}
            confirming={confirming}
            onBack={() => setStep(3)}
            onConfirm={handleConfirm}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function StepIndicator({ current }: { current: number }) {
  return (
    <ol className="flex items-center gap-3 border-b border-[var(--rule)] pb-4">
      {STEPS.map((s, i) => {
        const isDone = s.id < current;
        const isActive = s.id === current;
        return (
          <li key={s.id} className="flex items-center gap-3">
            <div
              className={`flex items-center gap-2 ${
                isActive ? "text-ink" : isDone ? "text-moss" : "text-ink-3"
              }`}
            >
              <span
                className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-mono-feat tabular-nums ${
                  isActive
                    ? "bg-moss text-white"
                    : isDone
                      ? "bg-moss/20 text-moss"
                      : "bg-[var(--rule)] text-ink-3"
                }`}
              >
                {isDone ? "✓" : s.id}
              </span>
              <span className="text-sm">{s.name}</span>
            </div>
            {i < STEPS.length - 1 && (
              <span className="text-ink-3">›</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

// ---------------------------------------------------------------------------

function Step1({
  file,
  onSelect,
  onNext,
  loading,
}: {
  file: File | null;
  onSelect: (f: File | null) => void;
  onNext: () => void;
  loading: boolean;
}) {
  const [drag, setDrag] = useState(false);
  return (
    <div className="space-y-6">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          const f = e.dataTransfer.files?.[0];
          if (f) onSelect(f);
        }}
        className={`border-2 border-dashed rounded-lg px-10 py-16 text-center transition-colors ${
          drag
            ? "border-moss bg-moss/5"
            : "border-[var(--rule-strong)] bg-card hover:bg-card-2"
        }`}
      >
        <div className="text-ink-2 mb-3">将文件拖到此处</div>
        <div className="text-ink-3 text-xs mb-4">支持 .xlsx / .csv / .json，单文件 ≤ 30MB</div>
        <label className="inline-block">
          <input
            type="file"
            accept=".xlsx,.csv,.json,.xls"
            className="hidden"
            onChange={(e) => onSelect(e.target.files?.[0] ?? null)}
          />
          <span className="cursor-pointer inline-flex items-center px-5 py-2 bg-moss text-white text-sm font-medium rounded hover:opacity-90 transition-opacity">
            点选文件
          </span>
        </label>
        {file && (
          <div className="mt-6 text-sm">
            <span className="text-ink-3">已选：</span>
            <span className="text-ink font-mono-feat">{file.name}</span>
            <span className="text-ink-3 ml-2">
              ({(file.size / 1024).toFixed(1)} KB)
            </span>
          </div>
        )}
      </div>

      <div className="flex justify-between pt-2">
        <Link
          href="/datasets"
          className="px-4 py-2 border border-[var(--rule-strong)] rounded text-sm hover:bg-card-2"
        >
          取消
        </Link>
        <button
          onClick={onNext}
          disabled={!file || loading}
          className="px-5 py-2 bg-moss text-white text-sm rounded hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "解析中…" : "下一步：字段映射"}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function Step2({
  parseResult,
  mapping,
  setMapping,
  onBack,
  onNext,
  onApplySuggested,
  loading,
}: {
  parseResult: ParseResult;
  mapping: Mapping;
  setMapping: (m: Mapping) => void;
  onBack: () => void;
  onNext: () => void;
  onApplySuggested: () => void;
  loading: boolean;
}) {
  const usedCols = new Set(Object.values(mapping).filter(Boolean) as string[]);
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between bg-card border border-[var(--rule)] rounded px-4 py-3">
        <div className="text-sm">
          <span className="uppercase-label text-ink-3 mr-2">检测格式</span>
          <span className="font-mono-feat">{parseResult.format}</span>
          <span className="text-ink-3 mx-3">·</span>
          <span className="uppercase-label text-ink-3 mr-2">总行数</span>
          <span className="font-mono-feat tabular-nums">{parseResult.total_rows}</span>
          <span className="text-ink-3 mx-3">·</span>
          <span className="uppercase-label text-ink-3 mr-2">列数</span>
          <span className="font-mono-feat tabular-nums">{parseResult.columns.length}</span>
        </div>
        <button
          onClick={onApplySuggested}
          className="text-sm text-moss hover:underline"
        >
          使用建议映射
        </button>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* 左：检测到的列 */}
        <div>
          <div className="uppercase-label text-ink-3 mb-2">检测到的列（含首行样本）</div>
          <div className="bg-card border border-[var(--rule)] rounded divide-y divide-[var(--rule)] max-h-[460px] overflow-y-auto">
            {parseResult.columns.map((col) => {
              const sample = parseResult.sample_rows[0]?.[col];
              const used = usedCols.has(col);
              const sampleStr =
                sample === null || sample === undefined
                  ? "—"
                  : String(sample);
              return (
                <div key={col} className="px-3 py-2 text-sm flex items-center gap-2">
                  <span
                    className={`font-mono-feat text-xs px-2 py-0.5 rounded ${
                      used ? "bg-moss/15 text-moss" : "bg-[var(--rule)] text-ink-3"
                    }`}
                  >
                    {col}
                  </span>
                  <span className="text-ink-3 text-xs truncate" title={sampleStr}>
                    {sampleStr.slice(0, 40)}
                    {sampleStr.length > 40 ? "…" : ""}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* 右：目标字段映射 */}
        <div>
          <div className="uppercase-label text-ink-3 mb-2">目标字段</div>
          <div className="bg-card border border-[var(--rule)] rounded divide-y divide-[var(--rule)]">
            {TARGET_FIELDS.map((t) => (
              <div key={t.key} className="px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <div className="text-sm text-ink">
                      {t.label}
                      {t.required && <span className="text-tomato ml-1">*</span>}
                    </div>
                    {t.hint && <div className="text-ink-3 text-xs">{t.hint}</div>}
                  </div>
                  <select
                    value={mapping[t.key] ?? ""}
                    onChange={(e) =>
                      setMapping({ ...mapping, [t.key]: e.target.value || null })
                    }
                    className="border border-[var(--rule-strong)] rounded bg-card-2 px-2 py-1 text-xs min-w-[160px]"
                  >
                    <option value="">— 不映射 —</option>
                    {parseResult.columns.map((col) => (
                      <option key={col} value={col}>
                        {col}
                      </option>
                    ))}
                  </select>
                </div>
                {t.key === "turn_index" && (
                  <TurnIndexSourceToggle
                    value={mapping.turn_index_source}
                    onChange={(src) => setMapping({ ...mapping, turn_index_source: src })}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex justify-between pt-2">
        <button
          onClick={onBack}
          className="px-4 py-2 border border-[var(--rule-strong)] rounded text-sm hover:bg-card-2"
        >
          上一步
        </button>
        <button
          onClick={onNext}
          disabled={
            loading ||
            !mapping.conversation_id ||
            !mapping.turn_index ||
            !mapping.user_query
          }
          className="px-5 py-2 bg-moss text-white text-sm rounded hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "校验中…" : "下一步：预览校验"}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function Step3({
  preview,
  showIssueDetails,
  setShowIssueDetails,
  onBack,
  onNext,
}: {
  preview: PreviewResult;
  showIssueDetails: boolean;
  setShowIssueDetails: (v: boolean) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const { validation_report: rep, preview_conversations: convs } = preview;
  const errs = rep.issues.filter((i) => i.severity === "error");
  const warns = rep.issues.filter((i) => i.severity === "warning");
  const infos = rep.issues.filter((i) => i.severity === "info");

  return (
    <div className="space-y-6">
      <div
        className={`border rounded px-4 py-3 ${
          rep.is_passable
            ? "border-moss bg-moss/5"
            : "border-tomato bg-tomato/5"
        }`}
      >
        <div className="flex items-center gap-4 text-sm">
          {rep.is_passable ? (
            <span className="text-moss font-medium">
              ✓ 校验通过 · {rep.total_conversations} 会话 / {rep.total_turns} 轮
            </span>
          ) : (
            <span className="text-tomato font-medium">
              ✗ 校验未通过：{errs.length} 个错误，不能入库
            </span>
          )}
          {warns.length > 0 && (
            <span className="text-yellow-700">⚠ {warns.length} 个警告</span>
          )}
          {infos.length > 0 && (
            <span className="text-ink-3">ℹ {infos.length} 个提示</span>
          )}
          {rep.issues.length > 0 && (
            <button
              className="ml-auto text-xs text-ink-3 hover:text-ink underline"
              onClick={() => setShowIssueDetails(!showIssueDetails)}
            >
              {showIssueDetails ? "收起详情" : "查看详情"}
            </button>
          )}
        </div>
        {showIssueDetails && rep.issues.length > 0 && (
          <div className="mt-3 pt-3 border-t border-[var(--rule)] space-y-2">
            {rep.issues.map((i, idx) => (
              <div key={idx} className="text-xs">
                <span
                  className={`inline-block px-2 py-0.5 rounded mr-2 font-mono-feat ${
                    i.severity === "error"
                      ? "bg-tomato/20 text-tomato"
                      : i.severity === "warning"
                        ? "bg-yellow-100 text-yellow-800"
                        : "bg-[var(--rule)] text-ink-3"
                  }`}
                >
                  {i.severity} · {i.code} · {i.count}
                </span>
                <span className="text-ink-2">{i.message}</span>
                {i.sample.length > 0 && (
                  <div className="ml-2 mt-1 text-ink-3 font-mono-feat">
                    示例: {i.sample.slice(0, 5).join(" · ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <div className="uppercase-label text-ink-3 mb-2">
          前 5 条对话预览
        </div>
        <div className="space-y-4">
          {convs.length === 0 && (
            <div className="bg-card border border-[var(--rule)] rounded px-6 py-10 text-center text-ink-3">
              无预览数据（请先修复校验错误）
            </div>
          )}
          {convs.map((c) => (
            <ConversationCard key={c.conversation_id} conv={c} />
          ))}
        </div>
      </div>

      <div className="flex justify-between pt-2">
        <button
          onClick={onBack}
          className="px-4 py-2 border border-[var(--rule-strong)] rounded text-sm hover:bg-card-2"
        >
          上一步：调整映射
        </button>
        <button
          onClick={onNext}
          disabled={!rep.is_passable}
          className="px-5 py-2 bg-moss text-white text-sm rounded hover:opacity-90 disabled:opacity-50"
          title={!rep.is_passable ? "存在错误，请先修复" : ""}
        >
          下一步：确认入库
        </button>
      </div>
    </div>
  );
}

function ConversationCard({ conv }: { conv: ConversationPreview }) {
  return (
    <div className="bg-card border border-[var(--rule)] rounded">
      <div className="px-4 py-2 border-b border-[var(--rule)] flex items-center gap-3 text-xs">
        <span className="font-mono-feat text-ink">{conv.conversation_id}</span>
        {conv.dimension_tag && (
          <span className="badge badge-neutral">{conv.dimension_tag}</span>
        )}
        {conv.quality_label && (
          <span
            className={`badge ${
              conv.quality_label === "good" ? "badge-pass" : "badge-fail"
            }`}
          >
            {conv.quality_label}
          </span>
        )}
        {conv.issue_type && (
          <span className="text-ink-3">· {conv.issue_type}</span>
        )}
        <span className="ml-auto text-ink-3">{conv.total_turns} 轮</span>
      </div>
      <div className="p-4 space-y-3">
        {conv.turns.map((t) => (
          <div key={t.turn_index} className="grid grid-cols-2 gap-3">
            <div className="bg-[var(--bg)] rounded px-3 py-2">
              <div className="uppercase-label text-ink-3 mb-1">
                T{t.turn_index} · User
              </div>
              <div className="text-sm text-ink">{t.user_query}</div>
            </div>
            <div
              className={`rounded px-3 py-2 ${
                t.rewritten_query
                  ? "bg-moss/10"
                  : "bg-[var(--bg)] opacity-50"
              }`}
            >
              <div className="uppercase-label text-ink-3 mb-1">
                Rewrite
              </div>
              <div className="text-sm text-ink">
                {t.rewritten_query || (
                  <span className="text-ink-3 italic">（无）</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function Step4({
  datasetName,
  setDatasetName,
  version,
  setVersion,
  description,
  setDescription,
  bots,
  attachBotId,
  setAttachBotId,
  confirming,
  onBack,
  onConfirm,
}: {
  datasetName: string;
  setDatasetName: (v: string) => void;
  version: string;
  setVersion: (v: string) => void;
  description: string;
  setDescription: (v: string) => void;
  bots: BotVersion[];
  attachBotId: number | null;
  setAttachBotId: (v: number | null) => void;
  confirming: boolean;
  onBack: () => void;
  onConfirm: () => void;
}) {
  const [enableAttach, setEnableAttach] = useState(false);

  useEffect(() => {
    if (!enableAttach) setAttachBotId(null);
    else if (attachBotId === null && bots[0]) setAttachBotId(bots[0].id);
  }, [enableAttach, bots, attachBotId, setAttachBotId]);

  return (
    <div className="max-w-[680px] space-y-5">
      <div className="bg-card border border-[var(--rule)] rounded p-6 space-y-5">
        <Field label="评测集名称 *">
          <input
            value={datasetName}
            onChange={(e) => setDatasetName(e.target.value)}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            placeholder="e.g. multi_turn_v2_2026Q2"
          />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="版本">
            <input
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
              placeholder="v1"
            />
          </Field>
        </div>

        <Field label="描述（可选）">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2"
            placeholder="本次评测集的来源、用途、覆盖维度等说明"
          />
        </Field>

        <div className="pt-4 border-t border-[var(--rule)] space-y-3">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={enableAttach}
              onChange={(e) => setEnableAttach(e.target.checked)}
            />
            <span>
              同时关联到 Bot 版本
              <span className="text-ink-3 ml-2 text-xs">
                （将 rewritten_query 写入该 bot 的改写表）
              </span>
            </span>
          </label>
          {enableAttach && (
            <select
              value={attachBotId ?? 0}
              onChange={(e) => setAttachBotId(parseInt(e.target.value, 10) || null)}
              className="w-full px-3 py-2 border border-[var(--rule-strong)] rounded bg-card-2 text-sm"
              disabled={bots.length === 0}
            >
              {bots.length === 0 && <option value={0}>— 暂无 bot 版本 —</option>}
              {bots.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} · {b.version_tag}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      <div className="flex justify-between pt-2">
        <button
          onClick={onBack}
          className="px-4 py-2 border border-[var(--rule-strong)] rounded text-sm hover:bg-card-2"
        >
          上一步
        </button>
        <button
          onClick={onConfirm}
          disabled={confirming || !datasetName.trim()}
          className="px-6 py-2 bg-moss text-white text-sm rounded hover:opacity-90 disabled:opacity-50"
        >
          {confirming ? "入库中…" : "确认入库"}
        </button>
      </div>
    </div>
  );
}

function TurnIndexSourceToggle({
  value,
  onChange,
}: {
  value: TurnIndexSource;
  onChange: (v: TurnIndexSource) => void;
}) {
  const OPTS: { v: TurnIndexSource; label: string; hint: string }[] = [
    { v: "turn_index", label: "数字序号", hint: "列值已经是 1/2/3…" },
    { v: "timestamp", label: "按时间戳排序", hint: "如 gmt_create，会自动派生 1..N" },
  ];
  return (
    <div className="mt-2 flex items-center gap-2 flex-wrap">
      <span className="text-ink-3 text-[11px] uppercase-label">来源</span>
      <div className="inline-flex border border-[var(--rule-strong)] rounded overflow-hidden">
        {OPTS.map((o) => {
          const active = o.v === value;
          return (
            <button
              key={o.v}
              type="button"
              onClick={() => onChange(o.v)}
              className={`px-2.5 py-1 text-xs transition-colors ${
                active
                  ? "bg-moss text-white"
                  : "bg-card-2 text-ink-2 hover:bg-[var(--moss-bg)]"
              }`}
              title={o.hint}
            >
              {o.label}
            </button>
          );
        })}
      </div>
      <span className="text-ink-3 text-[11px]">
        {value === "timestamp" ? "→ 按时间升序自动派生轮次" : "→ 直接读取列值"}
      </span>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block uppercase-label text-ink-3 mb-1.5">{label}</span>
      {children}
    </label>
  );
}
