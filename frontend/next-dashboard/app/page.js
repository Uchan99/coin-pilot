import { MetricCard } from "@/components/metric-card";
import { SectionFrame } from "@/components/section-frame";
import { getOverviewSnapshot } from "@/lib/bot-api";

function formatKrw(value) {
  return new Intl.NumberFormat("ko-KR", {
    style: "currency",
    currency: "KRW",
    maximumFractionDigits: 0
  }).format(value || 0);
}

function formatSignedKrw(value) {
  const formatted = formatKrw(Math.abs(value || 0));
  if (!value) {
    return formatted;
  }
  return value > 0 ? `+${formatted}` : `-${formatted}`;
}

export default async function OverviewPage() {
  const overview = await getOverviewSnapshot();
  const holdings = overview.holdings || [];

  return (
    <main className="content-grid">
      <SectionFrame
        eyebrow="Primary"
        title="Overview"
        description="총 평가액, 잔고, 당일 리스크 상태를 읽기 전용으로 재구성한 초기 MVP입니다."
        freshnessStatus={overview.freshnessStatus}
        dataAgeSec={overview.dataAgeSec}
        staleThresholdSec={overview.staleThresholdSec}
      >
        {overview.error ? <p className="callout error">{overview.error}</p> : null}
        <div className="metrics-grid">
          <MetricCard
            label="Total Valuation"
            value={formatKrw(overview.metrics?.totalValuationKrw)}
            tone="hero"
          />
          <MetricCard label="Cash" value={formatKrw(overview.metrics?.cashKrw)} />
          <MetricCard
            label="Daily PnL"
            value={formatSignedKrw(overview.metrics?.dailyTotalPnlKrw)}
            tone={Number(overview.metrics?.dailyTotalPnlKrw) >= 0 ? "good" : "warn"}
          />
          <MetricCard label="Trades" value={overview.metrics?.tradeCount || 0} />
          <MetricCard label="BUY Count" value={overview.metrics?.buyCount || 0} />
          <MetricCard
            label="Risk Level"
            value={overview.riskLevel || "UNKNOWN"}
            tone={overview.riskLevel === "HIGH_RISK" ? "warn" : "neutral"}
          />
        </div>
      </SectionFrame>

      <SectionFrame
        eyebrow="Primary / Secondary"
        title="Holdings"
        description="기존 Streamlit Overview의 활성 포지션 테이블을 Next.js 표 형태로 옮긴 버전입니다."
        freshnessStatus={overview.freshnessStatus}
        dataAgeSec={overview.dataAgeSec}
        staleThresholdSec={overview.staleThresholdSec}
      >
        {holdings.length === 0 ? (
          <p className="callout">현재 활성 포지션이 없습니다.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Qty</th>
                  <th>Avg Price</th>
                  <th>Current Price</th>
                  <th>Valuation</th>
                  <th>PnL</th>
                </tr>
              </thead>
              <tbody>
                {holdings.map((holding) => (
                  <tr key={holding.symbol}>
                    <td>{holding.symbol}</td>
                    <td>{holding.quantity?.toFixed?.(6) ?? holding.quantity}</td>
                    <td>{formatKrw(holding.avg_price)}</td>
                    <td>{holding.current_price ? formatKrw(holding.current_price) : "-"}</td>
                    <td>{formatKrw(holding.valuation_krw)}</td>
                    <td className={Number(holding.unrealized_pnl_krw) >= 0 ? "tone-good" : "tone-warn"}>
                      {formatSignedKrw(holding.unrealized_pnl_krw)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionFrame>

      <SectionFrame
        eyebrow="Diagnostic"
        title="Risk Flags"
        description="22번 spec에 맞춰 monitoring-only 정보는 Primary가 아니라 설명형 블록으로 유지합니다."
        freshnessStatus={overview.freshnessStatus}
        dataAgeSec={overview.dataAgeSec}
        staleThresholdSec={overview.staleThresholdSec}
      >
        <ul className="flag-list">
          {(overview.riskFlags || []).map((flag) => (
            <li key={flag}>{flag}</li>
          ))}
        </ul>
      </SectionFrame>
    </main>
  );
}
