"use client";
import { usePathname } from "next/navigation";

/*
 * 상단 고정 내비게이션 바 — 현재 페이지 제목 표시
 * pathname으로 현재 위치를 파악해 제목을 동적으로 변경한다.
 */

const PAGE_TITLES = {
  "/": "Control Center",
  "/overview": "Overview",
  "/market": "Market Analysis",
  "/risk": "Risk Monitor",
  "/history": "Trade History",
  "/system": "System Health",
  "/chatbot": "AI Chatbot",
  "/exit-analysis": "Exit Analysis",
};

export default function Topbar() {
  const pathname = usePathname();
  const title = PAGE_TITLES[pathname] || "CoinPilot";

  return (
    <header className="sticky top-0 z-40 w-full h-16 bg-surface/80 backdrop-blur-xl border-b border-outline-variant/[0.15] flex justify-between items-center px-8">
      <div className="flex items-center gap-4">
        <h2 className="text-primary text-xs font-medium uppercase tracking-widest">
          {title}
        </h2>
      </div>
      <div className="flex items-center gap-6">
        <div className="flex gap-4 items-center">
          <button className="text-on-surface-variant hover:text-on-surface transition-opacity cursor-pointer">
            <span className="material-symbols-outlined">notifications</span>
          </button>
          <button className="text-on-surface-variant hover:text-on-surface transition-opacity cursor-pointer">
            <span className="material-symbols-outlined">settings</span>
          </button>
        </div>
        <div className="h-8 w-8 rounded-full bg-primary-container/20 border border-primary/20 flex items-center justify-center">
          <span className="material-symbols-outlined text-primary text-sm">
            person
          </span>
        </div>
      </div>
    </header>
  );
}
