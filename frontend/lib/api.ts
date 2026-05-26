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
  // M1.1: bootstrap 95% CI（n<30 时为 null）
  mean_ci_low: number | null;
  mean_ci_high: number | null;
};

export type CostBreakdownItem = {
  dim_code: string;
  calls: number;
  cost_cny: number;
  cost_usd: number;
};

export type CostSummary = {
  total_calls: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_cost_usd: number;
  total_cost_cny: number;
  cost_per_session_cny: number;
  breakdown_by_dim: CostBreakdownItem[];
};

export type EvalRunDashboard = {
  run: EvalRun;
  dimension_summary: DimensionSummary[];
  score_distribution: Record<string, number>;
  cost_summary: CostSummary | null;
};

// ===== C.3 SSE live progress =====
export type LiveProgressEvent = {
  event:
    | "run_started"
    | "case_completed"
    | "case_failed"
    | "run_finished"
    | "run_failed"
    | "run_cancelled";
  completed?: number;
  failed?: number;
  total?: number;
  eta_seconds?: number | null;
  conversation_id?: number;
  dim_scores?: Record<string, number | null>;
  error_message?: string;
  case_id?: number;
  status?: string;
  weighted_score?: number | null;
  pass_rate?: number | null;
  reason?: string;
  retry?: boolean;
  retry_count?: number;
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
  // M1.1: bootstrap CI of delta（任一组 n<30 时为 null）
  delta_ci_low: number | null;
  delta_ci_high: number | null;
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
  // M1.1: 替代错位 kappa——Cohen's d 衡量两 run 分布差距
  score_distribution_overlap: number | null;
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

// ===== B.2 dimension slice =====
export type DimensionPromptInfo = {
  id: number;
  version_tag: string;
  notes: string | null;
};

export type DimensionStats = {
  total_cases: number;
  applicable_count: number;
  trigger_rate: number | null;
  avg_score: number | null;
  min_score: number | null;
  max_score: number | null;
  pass_count: number;
  pass_rate: number | null;
  // M1.1: bootstrap 95% CI（n<30 时为 null）
  mean_ci_low: number | null;
  mean_ci_high: number | null;
};

export type DimensionHistBucket = {
  bucket: string;
  count: number;
};

export type DimensionTopBadcase = {
  case_id: number;
  conversation_id_src: string;
  dim_score: number | null;
  weighted_score: number | null;
  explanation: string | null;
};

export type DimensionIssueCluster = {
  key: string;
  count: number;
};

export type DimensionSliceResponse = {
  dim_code: string;
  dim_name: string;
  weight: number;
  prompt_version: DimensionPromptInfo | null;
  stats: DimensionStats;
  histogram: DimensionHistBucket[];
  top_badcases: DimensionTopBadcase[];
  issue_clusters: DimensionIssueCluster[];
};

// ===== B.1 badcase types =====
export type BadcaseTag = {
  id: number;
  tag: string;
  is_confirmed: boolean;
  added_to_regression: boolean;
  notes: string | null;
  created_at: string;
};

export type BadcaseListItem = {
  case_id: number;
  conversation_id: number;
  conversation_id_src: string;
  weighted_score: number | null;
  lowest_dim_code: string | null;
  dim_scores: Record<string, number | null>;
  tags: BadcaseTag[];
  preview_query: string;
};

export type BadcaseFacet = { tag: string; count: number };

export type BadcaseStats = {
  total_cases: number;
  below_threshold: number;
  tagged: number;
  confirmed: number;
};

export type BadcaseListResponse = {
  total: number;
  items: BadcaseListItem[];
  tag_facets: BadcaseFacet[];
  stats: BadcaseStats;
};

export type CaseFullTurn = {
  turn_index: number;
  user_query: string;
  rewritten_query: string | null;
  timestamp: string | null;
};

export type CaseFullTurnResult = {
  turn_index: number;
  dimension_code: string;
  score: number | null;
  applicable: boolean | null;
  judge_raw_response: Record<string, unknown> | null;
};

export type CaseConversationMeta = {
  dimension_tag: string | null;
  quality_label: string | null;
  issue_type: string | null;
};

export type CaseFullDetail = {
  case_id: number;
  conversation_id: number;
  conversation_id_src: string;
  weighted_score: number | null;
  lowest_dim_code: string | null;
  dim_scores: Record<string, number | null>;
  turns: CaseFullTurn[];
  dim_results_full: Record<string, unknown>;
  turn_results: CaseFullTurnResult[];
  tags: BadcaseTag[];
  conversation_meta: CaseConversationMeta;
};

// ===== C.2 regression set types =====
export type RegressionSetOut = {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  item_count: number;
};

export type RegressionSetItemOut = {
  id: number;
  conversation_id: number;
  conversation_id_src: string | null;
  dimension_tag: string | null;
  source_case_id: number | null;
  added_at: string;
};

export type RegressionSetDetail = {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  items: RegressionSetItemOut[];
};

export type RegressionSetAddItemsResult = {
  added: number;
  skipped: number;
  items: RegressionSetItemOut[];
};

export type RegressionSetFromBadcasesResult = {
  added: number;
  skipped: number;
  matched_cases: number;
};
