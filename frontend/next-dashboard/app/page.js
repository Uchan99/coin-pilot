import Link from "next/link";

/*
 * Control Center (랜딩 페이지)
 * Stitch 디자인 기반 — Hero 섹션 + 6개 Quick Nav 카드 + Quick Start Guide + PnL 요약
 * 프로젝트 호환: USD→KRW, Launch Terminal/View API Docs 제거
 */

const NAV_CARDS = [
  { href: "/overview", icon: "analytics", title: "Overview", desc: "전체 포트폴리오 및 시장 현황 요약", color: "primary" },
  { href: "/market", icon: "show_chart", title: "Market", desc: "실시간 시세 및 AI 트렌드 분석", color: "tertiary" },
  { href: "/risk", icon: "security", title: "Risk Monitor", desc: "실시간 리스크 노출도 및 손실 추적", color: "error" },
  { href: "/history", icon: "receipt_long", title: "Trade History", desc: "과거 체결 내역 및 손익 상세 분석", color: "secondary" },
  { href: "/system", icon: "health_and_safety", title: "System Health", desc: "서버 상태 및 API 연결 모니터링", color: "primary" },
  { href: "/exit-analysis", icon: "query_stats", title: "Exit Analysis", desc: "매도 타이밍 및 전략 사후 평가", color: "primary-container" },
];

const COLOR_MAP = {
  primary: { iconBg: "bg-primary/10", iconText: "text-primary", hoverText: "group-hover:text-primary" },
  tertiary: { iconBg: "bg-tertiary/10", iconText: "text-tertiary", hoverText: "group-hover:text-tertiary" },
  error: { iconBg: "bg-error/10", iconText: "text-error", hoverText: "group-hover:text-error" },
  secondary: { iconBg: "bg-secondary/10", iconText: "text-secondary", hoverText: "group-hover:text-secondary" },
  "primary-container": { iconBg: "bg-primary-container/10", iconText: "text-primary-container", hoverText: "group-hover:text-primary-container" },
};

export default function ControlCenterPage() {
  return (
    <div className="space-y-8">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-xl p-12 bg-gradient-to-br from-surface-high to-surface-low border border-outline-variant/10">
        <div className="relative z-10 space-y-4 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-primary/10 rounded-full border border-primary/20">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-primary">System Operational</span>
          </div>
          <h1 className="text-5xl font-extrabold tracking-tighter text-on-surface">
            Welcome to CoinPilot <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-primary-container">Control Center</span>
          </h1>
          <p className="text-on-surface-variant text-lg font-medium">
            AI-Powered Crypto Trading System. 포트폴리오를 모니터링하고, 분석하고, 정밀하게 운영하세요.
          </p>
        </div>
      </section>

      {/* 메인 그리드 */}
      <div className="grid grid-cols-12 gap-8">
        {/* Quick Nav 카드 */}
        <div className="col-span-12 lg:col-span-8 grid grid-cols-1 md:grid-cols-2 gap-4">
          {NAV_CARDS.map(({ href, icon, title, desc, color }) => {
            const c = COLOR_MAP[color] || COLOR_MAP.primary;
            return (
              <Link key={href} href={href} className="group relative bg-surface-container p-6 rounded-xl border border-transparent card-hover-glow transition-all duration-300">
                <div className="flex justify-between items-start mb-4">
                  <div className={`p-3 rounded-lg ${c.iconBg} ${c.iconText}`}>
                    <span className="material-symbols-outlined">{icon}</span>
                  </div>
                  <span className={`material-symbols-outlined text-on-surface-variant ${c.hoverText} transition-colors`}>arrow_forward</span>
                </div>
                <h3 className="text-lg font-bold mb-1">{title}</h3>
                <p className="text-xs text-on-surface-variant">{desc}</p>
              </Link>
            );
          })}
        </div>

        {/* 우측 */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
          <div className="bg-surface-low border border-outline-variant/[0.15] p-6 rounded-xl flex-1">
            <div className="flex items-center gap-2 mb-6">
              <span className="material-symbols-outlined text-primary">lightbulb</span>
              <h3 className="font-bold tracking-tight">Quick Start Guide</h3>
            </div>
            <div className="space-y-6">
              {[
                { n: 1, t: "Upbit API 연동", d: "업비트 API를 연동하여 실시간 자산 조회를 시작하세요." },
                { n: 2, t: "리스크 매개변수 구성", d: "최대 손실폭(Drawdown)과 일일 매매 한도를 설정합니다." },
                { n: 3, t: "AI 봇 활성화", d: "레짐 기반 전략 모델로 자동 매매를 시작합니다." },
              ].map(({ n, t, d }) => (
                <div key={n} className="flex gap-4">
                  <div className="flex-none w-6 h-6 rounded-full bg-primary/20 text-primary flex items-center justify-center text-xs font-bold">{n}</div>
                  <div>
                    <h4 className="text-sm font-semibold mb-1">{t}</h4>
                    <p className="text-xs text-on-surface-variant leading-relaxed">{d}</p>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-8 p-4 bg-surface-high rounded-lg border border-primary/10">
              <p className="text-xs text-primary font-medium italic">&ldquo;시장 변동성이 높을 때는 포지션 규모를 줄이는 것이 가장 효과적인 방어 전략입니다.&rdquo;</p>
              <p className="text-[10px] text-on-surface-variant mt-2 text-right">— CoinPilot AI Advice</p>
            </div>
          </div>

          <div className="bg-gradient-to-br from-surface-low to-surface-container p-6 rounded-xl border border-outline-variant/[0.15]">
            <div className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">Total Combined PNL</div>
            <div className="text-3xl font-bold text-tertiary">데이터 로딩 중...</div>
            <div className="mt-4 h-12 flex items-end gap-1">
              {[20, 30, 25, 40, 50].map((h, i) => (
                <div key={i} className="flex-1 bg-tertiary/20 rounded-t-sm" style={{ height: `${h}%` }} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
