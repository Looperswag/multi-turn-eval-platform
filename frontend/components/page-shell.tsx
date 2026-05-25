/* Hallmark · component: page-shell · theme: EvalKit Studio (custom)
 * Standard page chrome: eyebrow → display heading → optional lede → meta strip → content.
 * All consumer pages render <PageShell> rather than ad-hoc <h1>s.
 */

import clsx from "clsx";
import type { ReactNode } from "react";
import { Eyebrow } from "./eyebrow";

type PageShellProps = {
  eyebrow?: { numerator?: string; label?: string };
  title: ReactNode;
  lede?: ReactNode;          // single-line italic Fraunces lede
  meta?: ReactNode;          // right-aligned mono strip (counts, badges, timestamps)
  actions?: ReactNode;       // primary actions (export, drilldown)
  display?: boolean;         // true → text-display-s (Stat-Led headings); false → text-h1 (default)
  className?: string;
  children: ReactNode;
};

export function PageShell({
  eyebrow,
  title,
  lede,
  meta,
  actions,
  display = false,
  className,
  children,
}: PageShellProps) {
  return (
    <div className={clsx("flex min-w-0 flex-col gap-2xl pb-4xl", className)}>
      <header className="flex flex-col gap-sm">
        {eyebrow ? <Eyebrow numerator={eyebrow.numerator} label={eyebrow.label} /> : null}
        <div className="flex flex-wrap items-end justify-between gap-lg">
          <h1
            className={clsx(
              "m-0 font-display text-ink",
              display ? "text-display-s" : "text-h1",
            )}
          >
            {title}
          </h1>
          {meta ? (
            <div className="text-xs font-mono tabular-nums text-ink-3 tracking-wider">{meta}</div>
          ) : null}
        </div>
        {lede ? (
          <p className="m-0 max-w-[68ch] text-lede text-ink-2 italic-display">{lede}</p>
        ) : null}
        {actions ? <div className="flex flex-wrap items-center gap-md pt-xs">{actions}</div> : null}
      </header>
      {children}
    </div>
  );
}
