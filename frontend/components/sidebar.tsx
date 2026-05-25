"use client";

/* Hallmark · component: sidebar · theme: EvalKit Studio (custom)
 * Editorial restraint: italic wordmark, no fill on active state, hairline group sep.
 * Mobile (< lg): top bar + framer-motion drawer.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import clsx from "clsx";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

type NavItem = { href: string; label: string; section: string };

const NAV: NavItem[] = [
  { section: "数据", href: "/datasets", label: "评测集" },
  { section: "数据", href: "/bot-versions", label: "Bot 版本" },
  { section: "数据", href: "/regression-sets", label: "回归集" },
  { section: "配置", href: "/judge-config/prompts", label: "Prompt 版本" },
  { section: "配置", href: "/judge-config/models", label: "Judge 模型" },
  { section: "评测", href: "/eval-runs", label: "评测任务" },
  { section: "评测", href: "/eval-runs/new", label: "新建评测" },
  { section: "对比", href: "/comparisons", label: "对比列表" },
  { section: "对比", href: "/comparisons/new", label: "新建对比" },
  { section: "标注", href: "/annotations", label: "标注工作台" },
  { section: "标注", href: "/annotations/agreement", label: "一致率看板" },
];

function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-sm">
      <svg width={compact ? 20 : 22} height={compact ? 20 : 22} viewBox="0 0 22 22" fill="none" aria-hidden>
        <rect x="2" y="2" width="18" height="18" rx="3" fill="var(--color-accent)" />
        <path d="M6 11l4 4 6-8" stroke="var(--color-paper-2)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div className="flex flex-col leading-none">
        <span className="italic-display text-[19px] font-medium text-ink tracking-tight">EvalKit</span>
        <span className="mt-0.5 font-mono text-[10px] tracking-[0.14em] uppercase text-ink-3">多轮 · 六维</span>
      </div>
    </div>
  );
}

function NavList({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  const sections = Array.from(new Set(NAV.map((n) => n.section)));
  return (
    <nav aria-label="Primary" className="flex flex-col gap-xl">
      {sections.map((section) => (
        <div key={section} className="flex flex-col gap-xs">
          <div className="italic-display text-xs text-ink-3 px-2xs">{section}</div>
          <ul className="m-0 flex list-none flex-col gap-2xs p-0">
            {NAV.filter((n) => n.section === section).map((item) => {
              const active =
                pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={clsx(
                      "group relative block py-2xs pl-md pr-xs text-sm no-underline transition-colors duration-fast ease-out",
                      "border-l-2",
                      active
                        ? "border-l-accent font-medium text-ink"
                        : "border-l-transparent text-ink-2 hover:text-ink hover:border-l-rule-strong",
                    )}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function DesktopSidebar({ pathname }: { pathname: string }) {
  return (
    <aside className="sticky top-0 hidden h-screen flex-col gap-2xl border-r border-rule bg-paper-2 px-lg py-xl lg:flex">
      <Wordmark />
      <div className="hairline-t -mx-lg" aria-hidden />
      <div className="flex-1 overflow-y-auto">
        <NavList pathname={pathname} />
      </div>
    </aside>
  );
}

function MobileBar({
  pathname,
  open,
  onToggle,
}: {
  pathname: string;
  open: boolean;
  onToggle: () => void;
}) {
  const reduce = useReducedMotion();
  const transition = reduce
    ? { duration: 0.08, ease: "linear" as const }
    : { type: "spring" as const, stiffness: 360, damping: 32 };

  return (
    <>
      <div className="sticky top-0 z-40 flex items-center justify-between border-b border-rule bg-paper-2 px-md py-sm lg:hidden">
        <Wordmark compact />
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-controls="evalkit-mobile-nav"
          className="rounded-sm border border-rule px-sm py-2xs text-xs text-ink-2 transition-colors duration-fast ease-out hover:border-rule-strong hover:text-ink"
        >
          {open ? "关闭" : "导航"}
        </button>
      </div>

      <AnimatePresence>
        {open ? (
          <>
            <motion.div
              key="scrim"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: reduce ? 0.08 : 0.2 }}
              className="fixed inset-0 z-40 bg-ink/30 lg:hidden"
              onClick={onToggle}
              aria-hidden
            />
            <motion.aside
              key="drawer"
              id="evalkit-mobile-nav"
              role="dialog"
              aria-modal="true"
              initial={reduce ? { opacity: 0 } : { x: "-100%" }}
              animate={reduce ? { opacity: 1 } : { x: 0 }}
              exit={reduce ? { opacity: 0 } : { x: "-100%" }}
              transition={transition}
              className="fixed inset-y-0 left-0 z-50 flex w-[280px] max-w-[85vw] flex-col gap-xl bg-paper-2 px-lg py-xl shadow-[var(--color-rule)] lg:hidden"
            >
              <Wordmark />
              <div className="hairline-t -mx-lg" aria-hidden />
              <div className="flex-1 overflow-y-auto">
                <NavList pathname={pathname} onNavigate={onToggle} />
              </div>
            </motion.aside>
          </>
        ) : null}
      </AnimatePresence>
    </>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // close drawer on route change
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <>
      <DesktopSidebar pathname={pathname} />
      <MobileBar pathname={pathname} open={open} onToggle={() => setOpen((v) => !v)} />
    </>
  );
}
