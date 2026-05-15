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
