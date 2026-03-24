import { getRiskSnapshot } from "@/lib/bot-api";
import { formatKrw } from "@/lib/formatters";

/*
 * Risk Monitor 페이지 — Stitch 디자인
 * Server Component: 서버에서 getRiskSnapshot() 호출
 * Daily Loss 게이지(CSS), Buy Count, Fill Counts, 연패, Trading Status
 */

export default async function RiskPage() {
  const data = await getRiskSnapshot();

  const dailyLimit = 500_000;
  const tradeLimit = 10;
  const pnlPct = Math.min(Math.abs(data.dailyTotalPnlKrw) / dailyLimit, 1);
  const buyPct = Math.min(data.buyCount / tradeLimit, 1);
  const isLoss = data.dailyTotalPnlKrw < 0;

  return (
    <div className="space-y-6">
      {/* Daily Loss + Buy Count */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Daily Loss Gauge */}
        <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-6">
          <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">
            Daily Loss Gauge
          </div>
          <div className="text-xs text-on-surface-variant mb-4">
            일일 손실 한도: -{formatKrw(dailyLimit)} KRW
          </div>
          <div className="flex justify-center mb-4">
            <div className="relative w-48 h-24 overflow-hidden">
              {/* 반원 게이지 배경 */}
              <div className="absolute inset-0 rounded-t-full border-[12px] border-surface-high border-b-0" />
              {/* 반원 게이지 값 — CSS rotate로 시각화 */}
              <div
                className={`absolute inset-0 rounded-t-full border-[12px] border-b-0 ${
                  isLoss ? "border-error" : "border-tertiary"
                }`}
                style={{
                  clipPath: `polygon(0 100%, 0 0, ${pnlPct * 100}% 0, ${pnlPct * 100}% 100%)`,
                }}
              />
              {/* 중앙 값 */}
              <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-center">
                <div className={`text-2xl font-bold ${isLoss ? "text-error" : "text-tertiary"}`}>
                  {formatKrw(data.dailyTotalPnlKrw, true)}
                </div>
              </div>
            </div>
          </div>
          {data.dailyTotalPnlKrw <= -dailyLimit && (
            <div className="bg-error/10 text-error text-xs font-bold px-4 py-2 rounded-lg text-center">
              🚨 Daily Loss Limit Reached!
            </div>
          )}
        </div>

        {/* Daily Buy Count */}
        <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-6">
          <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">
            Daily Buy Count
          </div>
          <div className="text-xs text-on-surface-variant mb-4">
            일일 매수 한도: {tradeLimit}건
          </div>
          <div className="flex justify-center mb-4">
            <div className="relative w-32 h-32">
              <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                <circle cx="50" cy="50" r="42" fill="none" stroke="#1f2a3d" strokeWidth="8" />
                <circle
                  cx="50" cy="50" r="42" fill="none"
                  stroke="#adc6ff" strokeWidth="8"
                  strokeDasharray={`${buyPct * 264} 264`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                  <div className="text-3xl font-bold text-primary">{data.buyCount}</div>
                  <div className="text-[10px] text-on-surface-variant">/ {tradeLimit}</div>
                </div>
              </div>
            </div>
          </div>
          {data.buyCount >= tradeLimit && (
            <div className="bg-yellow-500/10 text-yellow-400 text-xs font-bold px-4 py-2 rounded-lg text-center">
              ⚠️ Max Buy Count Reached
            </div>
          )}
        </div>
      </div>

      {/* Fill Counts */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Buy Fills", value: data.buyCount, unit: "건", color: "text-primary" },
          { label: "Sell Fills", value: data.sellCount, unit: "건", color: "text-error" },
          { label: "Total Trades", value: data.tradeCount, unit: "건", color: "text-on-surface" },
        ].map(({ label, value, unit, color }) => (
          <div key={label} className="bg-surface-container rounded-xl border border-outline-variant/10 p-5">
            <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-2">{label}</div>
            <div className={`text-3xl font-bold ${color}`}>
              {value} <span className="text-sm font-normal text-on-surface-variant">{unit}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Consecutive Losses + Trading Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-6">
          <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-2">
            Consecutive Losses
          </div>
          <div className={`text-4xl font-bold ${data.consecutiveLosses >= 3 ? "text-error" : "text-on-surface"}`}>
            {data.consecutiveLosses}
          </div>
          <div className="text-xs text-on-surface-variant mt-1">3연패 시 쿨다운 발동</div>
          {data.consecutiveLosses >= 3 && (
            <div className="mt-3 bg-error/10 text-error text-xs font-bold px-4 py-2 rounded-lg">
              🧊 Cooldown Active
            </div>
          )}
        </div>

        <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-6">
          <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-2">
            Trading Status
          </div>
          <div className={`text-2xl font-bold flex items-center gap-3 ${data.isTradingHalted ? "text-error" : "text-tertiary"}`}>
            <span className={`w-3 h-3 rounded-full ${data.isTradingHalted ? "bg-error animate-pulse" : "bg-tertiary"}`} />
            {data.isTradingHalted ? "HALTED" : "RUNNING"}
          </div>
        </div>
      </div>

      {/* Risk Audit Log */}
      <div className="bg-surface-container rounded-xl border border-outline-variant/10 overflow-hidden">
        <div className="px-6 py-4 border-b border-outline-variant/10">
          <h3 className="font-bold flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-lg">shield</span>
            Risk Audit Log
          </h3>
        </div>
        <div className="px-6 py-8 text-center text-on-surface-variant text-sm">
          Risk Audit 로그는 API 연동 후 표시됩니다.
        </div>
      </div>
    </div>
  );
}
