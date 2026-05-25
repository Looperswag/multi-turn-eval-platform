/* Hallmark · component: eyebrow · theme: EvalKit Studio (custom)
 * Only for ordinal contexts (wizard step, chapter number, run number).
 * Default OFF — do NOT decorate every section with eyebrows.
 */

import clsx from "clsx";

type EyebrowProps = {
  numerator?: string; // e.g. "1/4"  "Run #142"  "01"
  label?: string;     // e.g. "Wizard"  "Comparison"
  className?: string;
};

export function Eyebrow({ numerator, label, className }: EyebrowProps) {
  if (!numerator && !label) return null;
  return (
    <div
      className={clsx(
        "flex items-center gap-sm text-caption uppercase tracking-[0.08em] text-ink-3",
        className,
      )}
    >
      {numerator ? <span className="font-mono tabular-nums">{numerator}</span> : null}
      {numerator && label ? <span aria-hidden className="text-ink-4">·</span> : null}
      {label ? <span className="italic-display normal-case tracking-normal">{label}</span> : null}
    </div>
  );
}
