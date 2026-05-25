/* Hallmark · component: section-head · theme: EvalKit Studio (custom)
 * Editorial section heading — VERTICAL stack only.
 * Banned: 2-column hanging-header pattern (Hallmark slop-test gate 66).
 */

import clsx from "clsx";
import type { ReactNode } from "react";

type SectionHeadProps = {
  eyebrow?: string;
  title: ReactNode;
  caption?: ReactNode;
  meta?: ReactNode;          // optional right-aligned strip (counts, links, exports)
  asLevel?: 1 | 2;           // 1 = page h1, 2 = section h2 (default 2)
  hairline?: boolean;        // default true
  className?: string;
};

export function SectionHead({
  eyebrow,
  title,
  caption,
  meta,
  asLevel = 2,
  hairline = true,
  className,
}: SectionHeadProps) {
  const Tag = asLevel === 1 ? "h1" : "h2";
  return (
    <header
      className={clsx(
        "flex flex-col gap-xs",
        hairline && "border-t border-rule pt-md",
        className,
      )}
    >
      {eyebrow ? (
        <span className="text-caption uppercase tracking-[0.08em] text-ink-3">{eyebrow}</span>
      ) : null}
      <div className="flex flex-wrap items-end justify-between gap-md">
        <Tag
          className={clsx(
            "font-display text-ink m-0",
            asLevel === 1 ? "text-h1" : "text-h2",
          )}
        >
          {title}
        </Tag>
        {meta ? <div className="text-xs text-ink-3 font-mono tabular-nums">{meta}</div> : null}
      </div>
      {caption ? (
        <p className="m-0 max-w-[68ch] text-lede text-ink-2 italic-display">{caption}</p>
      ) : null}
    </header>
  );
}
