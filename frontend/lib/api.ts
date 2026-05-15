/** API client 薄封装。
 *
 * 双 origin 设计：
 * - 浏览器侧（client component / browser fetch）走 NEXT_PUBLIC_API_BASE_URL（如 http://localhost:8000）
 * - Server Component / SSR 跑在 web 容器内，必须走 INTERNAL_API_BASE_URL（如 http://api:8000），
 *   因为容器内的 localhost 指向 web 容器自己，触不到 api 容器。
 */
const isServer = typeof window === "undefined";
const BASE = isServer
  ? process.env.INTERNAL_API_BASE_URL || "http://api:8000"
  : process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${path} -> ${res.status}: ${text}`);
  }
  return res.json();
}

export const fetcher = (path: string) => api(path);

export type EvalRun = {
  id: number;
  name: string;
  status: string;
  total: number;
  completed: number;
  failed: number;
  weighted_score: number | null;
  pass_rate: number | null;
  created_at: string;
  baseline_run_id: number | null;
};

export type DimensionSummary = {
  dimension_code: string;
  dimension_name: string;
  avg_score: number | null;
  sample_count: number;
  pass_count: number;
  pass_rate: number | null;
  min_score: number | null;
  max_score: number | null;
};

export type EvalRunDashboard = {
  run: EvalRun;
  dimension_summary: DimensionSummary[];
  score_distribution: Record<string, number>;
};

// ===== A.5.1 comparison types =====
export type DiffPoint = {
  field: string;
  value_a: unknown;
  value_b: unknown;
  reason?: string | null;
};

export type DiffRunsResult = {
  diff_points: DiffPoint[];
  suggested_type: string | null;
  run_a_id: number;
  run_b_id: number;
};

export type MovementCase = {
  conversation_id_src: string;
  conversation_id: number;
  score_a: number | null;
  score_b: number | null;
};

export type DimensionMovement = {
  improved: MovementCase[];
  regressed: MovementCase[];
};

export type RunSummary = {
  id: number;
  name: string;
  status: string;
  weighted_score: number | null;
  pass_rate: number | null;
  dataset_id: number;
  bot_version_id: number;
  judge_model_id: number;
  judge_prompt_version_ids: Record<string, number>;
  dimensions_selected: string[];
  finished_at: string | null;
};

export type DimDelta = {
  dim_code: string;
  dim_name: string;
  avg_a: number | null;
  avg_b: number | null;
  delta: number | null;
  chi_square_pvalue: number | null;
  sample_size: number;
};

export type ComparisonPayload = {
  type: string;
  run_a_summary: RunSummary;
  run_b_summary: RunSummary;
  aligned_count: number;
  sample_size: number;
  session_movement: DimensionMovement;
  dimension_movements: Record<string, DimensionMovement>;
  dim_deltas: DimDelta[];
  kappa: number | null;
  confusion_matrix: number[][] | null;
  computed_at: string | null;
};

export type ComparisonOut = {
  id: number;
  name: string | null;
  type: string;
  run_a_id: number;
  run_b_id: number | null;
  created_at: string;
  computed_at: string | null;
  payload: ComparisonPayload;
};

// ===== A.5.2 annotation types =====
export type AnnotationOut = {
  id: number;
  conversation_id: number;
  dimension_code: string;
  annotator: string;
  score: number | null;
  is_applicable: boolean | null;
  comment: string | null;
  evidence_text: string | null;
  created_at: string;
  updated_at: string;
};

export type QueueTurn = {
  turn_index: number;
  user_query: string;
  rewritten_query: string | null;
};

export type QueueItem = {
  case_id: number;
  conversation_id: number;
  conversation_id_src: string;
  dimension_tag: string | null;
  quality_label: string | null;
  judge_score: number | null;
  judge_applicable: boolean | null;
  judge_explanation: string | null;
  judge_confidence: number | null;
  judge_raw: Record<string, unknown> | null;
  turns: QueueTurn[];
  existing_annotation: AnnotationOut | null;
};

export type QueueResponse = {
  items: QueueItem[];
  total: number;
  dimension_code: string;
  dimension_name: string;
};

export type AgreementDim = {
  dim_code: string;
  dim_name: string;
  accuracy: number | null;
  kappa: number | null;
  confusion_matrix: number[][];
  sample_size: number;
};

export type AgreementAnnotator = {
  annotator: string;
  dims: AgreementDim[];
  overall_accuracy: number | null;
  overall_kappa: number | null;
  total_sample_size: number;
};

export type AgreementResponse = {
  run_id: number;
  mode: string;
  per_annotator: AgreementAnnotator[];
  levels: string[];
};
