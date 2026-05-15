"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

type NavItem = { href: string; label: string; section: string };

const NAV: NavItem[] = [
  { section: "数据", href: "/datasets", label: "评测集" },
  { section: "数据", href: "/bot-versions", label: "Bot 版本" },
  { section: "配置", href: "/judge-config/prompts", label: "Prompt 版本" },
  { section: "配置", href: "/judge-config/models", label: "Judge 模型" },
  { section: "评测", href: "/eval-runs", label: "评测任务" },
  { section: "评测", href: "/eval-runs/new", label: "新建评测" },
  { section: "对比", href: "/comparisons/new", label: "新建对比" },
  { section: "标注", href: "/annotations", label: "标注工作台" },
];

export function Sidebar() {
  const pathname = usePathname();
  const sections = Array.from(new Set(NAV.map((n) => n.section)));
  return (
    <aside className="sticky top-0 h-screen bg-card border-r border-[var(--rule)] px-5 py-6 flex flex-col">
      <div className="pb-6 mb-5 border-b border-dashed border-[var(--rule)]">
        <div className="flex items-center gap-2.5 mb-1">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <rect x="2" y="2" width="18" height="18" rx="4" fill="#4A7C59" />
            <path d="M6 11l4 4 6-8" stroke="#FCFAF5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="font-display text-[19px] font-medium text-ink tracking-tight">EvalKit</span>
        </div>
        <div className="font-mono-feat text-[11px] text-ink-3 tracking-wider pl-8">多轮 · 六维</div>
      </div>

      {sections.map((section) => (
        <div key={section} className="mb-5">
          <div className="uppercase-label text-ink-3 mb-2.5 px-1">{section}</div>
          <ul className="flex flex-col gap-1 list-none p-0 m-0">
            {NAV.filter((n) => n.section === section).map((item) => {
              const active =
                pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={clsx(
                      "block px-3 py-1.5 rounded text-[13px] transition-colors no-underline",
                      active
                        ? "bg-[var(--moss-bg)] text-moss font-medium"
                        : "text-ink-2 hover:bg-[var(--rule)] hover:text-ink",
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
    </aside>
  );
}
