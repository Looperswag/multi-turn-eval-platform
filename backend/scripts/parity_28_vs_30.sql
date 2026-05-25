-- Parity check: run 28 (sequential baseline) vs run 30 (concurrency=5 verification).
-- Read-only. Run via:
--   docker compose exec -T postgres psql -U eval -d eval_platform -f /app/scripts/parity_28_vs_30.sql

\echo === [1] EvalRun row state for 28 and 30 ===
SELECT id, status, total, completed, failed, weighted_score, pass_rate,
       EXTRACT(EPOCH FROM (finished_at - started_at))::int AS duration_sec
FROM eval_run
WHERE id IN (28, 30)
ORDER BY id;

\echo === [2] EvalCaseResult row counts per run (should both be 198) ===
SELECT eval_run_id, COUNT(*) AS case_count
FROM eval_case_result
WHERE eval_run_id IN (28, 30)
GROUP BY eval_run_id
ORDER BY eval_run_id;

\echo === [3] EvalTurnResult row counts per (run, dim) ===
SELECT cr.eval_run_id, tr.dimension_code, COUNT(*) AS turn_count
FROM eval_turn_result tr
JOIN eval_case_result cr ON cr.id = tr.eval_case_result_id
WHERE cr.eval_run_id IN (28, 30)
GROUP BY cr.eval_run_id, tr.dimension_code
ORDER BY tr.dimension_code, cr.eval_run_id;

\echo === [4] Per-dim avg score, run 28 vs run 30 ===
SELECT tr.dimension_code,
       cr.eval_run_id,
       COUNT(*)                                                       AS n_turns,
       COUNT(*) FILTER (WHERE tr.applicable IS FALSE)                 AS n_not_applicable,
       ROUND(AVG(tr.score) FILTER (WHERE tr.applicable IS NOT FALSE)::numeric, 4) AS avg_score,
       ROUND(AVG(CASE WHEN tr.score >= 0.6 THEN 1.0 ELSE 0 END)::numeric, 4)      AS pass_rate
FROM eval_turn_result tr
JOIN eval_case_result cr ON cr.id = tr.eval_case_result_id
WHERE cr.eval_run_id IN (28, 30)
GROUP BY tr.dimension_code, cr.eval_run_id
ORDER BY tr.dimension_code, cr.eval_run_id;

\echo === [5] Race-condition smell: duplicate (case_id, turn_index, dim) tuples in run 30 ===
SELECT cr.eval_run_id, tr.eval_case_result_id, tr.turn_index, tr.dimension_code, COUNT(*) AS dup_count
FROM eval_turn_result tr
JOIN eval_case_result cr ON cr.id = tr.eval_case_result_id
WHERE cr.eval_run_id = 30
GROUP BY cr.eval_run_id, tr.eval_case_result_id, tr.turn_index, tr.dimension_code
HAVING COUNT(*) > 1
LIMIT 20;

\echo === [6] Per-session weighted_score deltas: run 30 vs run 28 (top 20 by abs diff) ===
WITH r28 AS (
    SELECT conversation_id, weighted_score AS score_28
    FROM eval_case_result WHERE eval_run_id = 28
),
r30 AS (
    SELECT conversation_id, weighted_score AS score_30
    FROM eval_case_result WHERE eval_run_id = 30
)
SELECT r28.conversation_id,
       ROUND(r28.score_28::numeric, 4)            AS score_28,
       ROUND(r30.score_30::numeric, 4)            AS score_30,
       ROUND((r30.score_30 - r28.score_28)::numeric, 4) AS delta
FROM r28
FULL OUTER JOIN r30 USING (conversation_id)
ORDER BY ABS(COALESCE(r30.score_30, 0) - COALESCE(r28.score_28, 0)) DESC
LIMIT 20;

\echo === [7] Aggregate delta: mean / median / 95p of abs(delta) ===
WITH joined AS (
    SELECT r28.weighted_score AS s28, r30.weighted_score AS s30
    FROM eval_case_result r28
    JOIN eval_case_result r30 USING (conversation_id)
    WHERE r28.eval_run_id = 28 AND r30.eval_run_id = 30
)
SELECT COUNT(*) AS n,
       ROUND(AVG(ABS(s30 - s28))::numeric, 4)                             AS mean_abs_delta,
       ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ABS(s30-s28))::numeric, 4) AS median_abs_delta,
       ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY ABS(s30-s28))::numeric, 4) AS p95_abs_delta,
       ROUND(MAX(ABS(s30 - s28))::numeric, 4)                             AS max_abs_delta
FROM joined;

\echo === [8] Conversations covered by 28 but missing in 30 (and vice versa) ===
SELECT 'in_28_only' AS bucket, COUNT(*)
FROM (SELECT conversation_id FROM eval_case_result WHERE eval_run_id = 28
      EXCEPT SELECT conversation_id FROM eval_case_result WHERE eval_run_id = 30) x
UNION ALL
SELECT 'in_30_only', COUNT(*)
FROM (SELECT conversation_id FROM eval_case_result WHERE eval_run_id = 30
      EXCEPT SELECT conversation_id FROM eval_case_result WHERE eval_run_id = 28) y;
