/* Hallmark · chart color helper
 * Recharts can't dereference CSS vars itself — it needs string-resolved colors.
 * These mirror tokens.css (OKLCH, perceptually equivalent to the hex anchors).
 * Modern browsers accept oklch() in SVG `stroke` and `fill` attributes.
 */

export const chartColors = {
  ink:        "oklch(15.7% 0.005 60)",
  ink2:       "oklch(40.5% 0.008 60)",
  ink3:       "oklch(63.4% 0.010 70)",
  ink4:       "oklch(77.1% 0.012 75)",
  paper:      "oklch(95.0% 0.013 80)",
  paper2:     "oklch(98.1% 0.008 80)",
  paper3:     "oklch(100% 0 0)",
  accent:     "oklch(49.0% 0.070 145)",
  accentSoft: "oklch(93.0% 0.018 145)",
  warn:       "oklch(60.0% 0.180 35)",
  warnSoft:   "oklch(94.0% 0.025 35)",
  info:       "oklch(45.0% 0.100 245)",
  infoSoft:   "oklch(93.0% 0.020 245)",
  note:       "oklch(60.0% 0.100 75)",
  noteSoft:   "oklch(93.0% 0.040 85)",
  rule:       "oklch(15.7% 0.005 60 / 0.10)",
  ruleStrong: "oklch(15.7% 0.005 60 / 0.20)",
} as const;

/** Pass/warn/fail color by score on a 0–1 scale. */
export function scoreColor(score: number): string {
  if (score < 0.6) return chartColors.warn;
  if (score < 0.8) return chartColors.note;
  return chartColors.accent;
}

/** Standard tooltip surface for chart tooltips — matches editorial card. */
export const tooltipStyle: React.CSSProperties = {
  background: chartColors.paper2,
  border: `1px solid ${chartColors.rule}`,
  borderRadius: 2,
  fontSize: 11,
  fontFamily: "var(--font-mono)",
  color: chartColors.ink,
  padding: "6px 10px",
  boxShadow: "none",
};
