import { getOverviewSnapshot } from "@/lib/bot-api";
import { formatKrw, formatPct, formatQty } from "@/lib/formatters";

/*
 * Overview 페이지 — Stitch 디자인 "Portfolio Overview"
 * Server Component: getOverviewSnapshot()으로 서버에서 데이터 조회 후 렌더링
 * KPI 4카드 + 보유 포지션 테이블
 * 수익률 추이 차트, 자산 비중 도넛은 Plotly 클라이언트 컴포넌트로 분리 (향후 구현)
 */

export default async function OverviewPage() {
  const data = await getOverviewSnapshot();
  const { metrics, holdings, riskLevel, freshnessStatus: freshness } = data;

  const kpiCards = [
    {
      label: "총 체결",
      value: `${metrics.cumulativeTradeCount.toLocaleString("ko-KR")} 건`,
      sub: `매수 ${metrics.buyCount}건 (당일 ${metrics.tradeCount}건)`,
      icon: "swap_horiz",
    },
    {
      label: "누적 손익",
      value: `${formatKrw(metrics.cumulativePnlKrw, true)} 원`,
      sub: metrics.cumulativePnlKrw >= 0 ? "수익 구간" : "손실 구간",
      icon: "trending_up",
      positive: metrics.cumulativePnlKrw >= 0,
    },
    {
      label: "총 평가액",
      value: `${formatKrw(metrics.totalValuationKrw)} 원`,
      sub: `리스크: ${riskLevel}`,
      icon: "account_balance_wallet",
    },
    {
      label: "현재 잔고",
      value: `${formatKrw(metrics.cashKrw)} 원`,
      sub: `총 자산 기준: ${formatKrw(metrics.totalValuationKrw)} 원`,
      icon: "payments",
    },
  ];

  return (
    <div className="space-y-8">
      {/* Freshness 배지 */}
      <div className="flex items-center gap-2">
        <span
          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${
            freshness === "fresh"
              ? "bg-tertiary/10 text-tertiary"
              : freshness === "delayed"
              ? "bg-yellow-500/10 text-yellow-400"
              : "bg-error/10 text-error"
          }`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${
            freshness === "fresh" ? "bg-tertiary" : freshness === "delayed" ? "bg-yellow-400" : "bg-error"
          }`} />
          {freshness === "fresh" ? "LIVE" : freshness === "delayed" ? "DELAYED" : "STALE"}
        </span>
      </div>

      {/* KPI 카드 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpiCards.map(({ label, value, sub, icon, positive }) => (
          <div
            key={label}
            className="bg-surface-container p-5 rounded-xl border border-outline-variant/10"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                {label}
              </span>
              <span className="material-symbols-outlined text-primary/40 text-lg">
                {icon}
              </span>
            </div>
            <div
              className={`text-2xl font-bold tracking-tight ${
                positive === true
                  ? "text-tertiary"
                  : positive === false
                  ? "text-error"
                  : "text-on-surface"
              }`}
            >
              {value}
            </div>
            <div className="text-xs text-on-surface-variant mt-1">{sub}</div>
          </div>
        ))}
      </div>

      {/* 보유 포지션 테이블 */}
      <div className="bg-surface-container rounded-xl border border-outline-variant/10 overflow-hidden">
        <div className="px-6 py-4 flex items-center justify-between border-b border-outline-variant/10">
          <div className="flex items-center gap-2">
            <h3 className="font-bold">보유 포지션</h3>
            <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-bold">
              {holdings.length}
            </span>
          </div>
        </div>

        {holdings.length === 0 ? (
          <div className="px-6 py-12 text-center text-on-surface-variant text-sm">
            현재 보유 중인 포지션이 없습니다.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
                  <th className="px-6 py-3">Symbol</th>
                  <th className="px-4 py-3">Quantity</th>
                  <th className="px-4 py-3">Avg Price (KRW)</th>
                  <th className="px-4 py-3">Invested</th>
                  <th className="px-4 py-3">Current Value</th>
                  <th className="px-4 py-3">PNL (KRW)</th>
                  <th className="px-4 py-3">PNL (%)</th>
                </tr>
              </thead>
              <tbody>
                {holdings.map((h) => {
                  const invested = h.quantity * h.avg_price;
                  const isProfit = h.unrealized_pnl_krw >= 0;
                  return (
                    <tr
                      key={h.symbol}
                      className="border-t border-outline-variant/5 hover:bg-surface-high/30 transition-colors"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-[10px] font-bold text-primary">
                            {h.symbol.replace("KRW-", "").slice(0, 3)}
                          </div>
                          <div>
                            <div className="font-semibold text-sm">{h.symbol.replace("KRW-", "")}</div>
                            <div className="text-[10px] text-on-surface-variant">{h.symbol}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-sm font-mono">
                        {formatQty(h.quantity)}
                      </td>
                      <td className="px-4 py-4 text-sm font-mono">
                        {formatKrw(h.avg_price)}
                      </td>
                      <td className="px-4 py-4 text-sm font-mono">
                        {formatKrw(invested)}
                      </td>
                      <td className="px-4 py-4 text-sm font-mono">
                        {formatKrw(h.valuation_krw)}
                      </td>
                      <td className={`px-4 py-4 text-sm font-mono font-semibold ${isProfit ? "text-tertiary" : "text-error"}`}>
                        {formatKrw(h.unrealized_pnl_krw, true)}
                      </td>
                      <td className={`px-4 py-4 text-sm font-mono font-semibold ${isProfit ? "text-tertiary" : "text-error"}`}>
                        {h.unrealized_pnl_pct != null ? formatPct(h.unrealized_pnl_pct) : "N/A"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
