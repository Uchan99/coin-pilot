"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

/*
 * 사이드바 네비게이션 — Stitch "Deep Sea" 디자인 기반
 * pathname 비교로 현재 페이지를 하이라이트하고,
 * 하단에 auto-refresh 상태와 DB 연결 상태를 표시한다.
 */

const NAV_ITEMS = [
  { href: "/", icon: "dashboard", label: "Control Center" },
  { href: "/overview", icon: "analytics", label: "Overview" },
  { href: "/market", icon: "show_chart", label: "Market" },
  { href: "/risk", icon: "security", label: "Risk Monitor" },
  { href: "/history", icon: "receipt_long", label: "Trade History" },
  { href: "/system", icon: "health_and_safety", label: "System Health" },
  { href: "/chatbot", icon: "smart_toy", label: "AI Chatbot" },
  { href: "/exit-analysis", icon: "query_stats", label: "Exit Analysis" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-full w-[240px] bg-surface-low border-r border-outline-variant/[0.15] flex flex-col py-6 px-4 gap-2 shadow-2xl z-50">
      {/* 로고 */}
      <div className="mb-8 px-2">
        <h1 className="text-xl font-bold tracking-tighter text-on-surface">
          CoinPilot v3.0
        </h1>
        <p className="text-[10px] font-medium uppercase tracking-widest text-primary/70">
          AI-Powered Crypto Trading
        </p>
      </div>

      {/* 내비게이션 */}
      <nav className="flex-1 flex flex-col gap-1">
        {NAV_ITEMS.map(({ href, icon, label }) => {
          const isActive = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                isActive
                  ? "text-primary font-semibold bg-surface-high nav-active-shadow"
                  : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container"
              }`}
            >
              <span className="material-symbols-outlined text-xl">
                {icon}
              </span>
              <span className="text-sm font-medium tracking-tight">
                {label}
              </span>
            </Link>
          );
        })}
      </nav>

      {/* 하단 상태 */}
      <div className="mt-auto border-t border-outline-variant/10 pt-4 flex flex-col gap-3">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-primary/60 font-bold bg-primary/5 p-2 rounded-lg">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-tertiary opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-tertiary" />
          </span>
          Auto-refresh: 30s
        </div>
        <div className="flex items-center gap-3 px-3 py-2 text-on-surface-variant">
          <span className="material-symbols-outlined text-tertiary text-sm">
            cloud_done
          </span>
          <span className="text-xs font-medium tracking-tight uppercase">
            DB Connected
          </span>
        </div>
      </div>
    </aside>
  );
}
