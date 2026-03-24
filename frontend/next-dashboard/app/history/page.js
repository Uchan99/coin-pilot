"use client";
import { useState } from "react";
import PlotlyChart from "@/components/plotly-chart";

/*
 * Trade History 페이지 — Stitch 디자인
 * 현재 Phase 2 MVP: Mock 데이터로 UI 프레임 구현
 * 실제 trading_history 데이터는 전용 API route 추가 후 연동 예정
 */

const MOCK_TRADES = [
  { timestamp: "2026-03-24 14:22:05", symbol: "KRW-BTC", side: "BUY", avgEntry: "97,429,500", executed: "97,421,100", qty: "0.250", realizedPnl: null, pnlPct: null, total: "24,355,275", regime: "Sideways" },
  { timestamp: "2026-03-24 10:08:41", symbol: "KRW-ETH", side: "SELL", avgEntry: "2,885,120", executed: "2,878,450", qty: "4.326", realizedPnl: "-28,860", pnlPct: "-0.23", total: "12,452,134", regime: "Sideways" },
  { timestamp: "2026-03-23 22:15:32", symbol: "KRW-SOL", side: "BUY", avgEntry: "58,420", executed: "59,950", qty: "158.00", realizedPnl: null, pnlPct: null, total: "9,472,100", regime: "Bull" },
  { timestamp: "2026-03-23 18:44:12", symbol: "KRW-XRP", side: "SELL", avgEntry: "880", executed: "862.15", qty: "12,000", realizedPnl: "-213,800", pnlPct: "-2.02", total: "10,345,800", regime: "Bear" },
];

export default function HistoryPage() {
  const [sideFilter, setSideFilter] = useState("ALL");
  const [viewMode, setViewMode] = useState("기본");

  const filtered = MOCK_TRADES.filter(
    (t) => sideFilter === "ALL" || t.side === sideFilter
  );

  const buyCount = MOCK_TRADES.filter((t) => t.side === "BUY").length;
  const sellCount = MOCK_TRADES.filter((t) => t.side === "SELL").length;

  return (
    <div className="space-y-6">
      {/* 필터 바 */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-lg">search</span>
          <input
            type="text"
            placeholder="Symbol search (e.g. BTC)"
            className="bg-surface-container text-on-surface text-sm rounded-lg pl-10 pr-4 py-2 border border-outline-variant/20 focus:outline-none focus:border-primary/40 w-64 placeholder:text-on-surface-variant/50"
          />
        </div>

        <select
          value={sideFilter}
          onChange={(e) => setSideFilter(e.target.value)}
          className="bg-surface-container text-on-surface text-sm rounded-lg px-4 py-2 border border-outline-variant/20"
        >
          <option value="ALL">Side: All</option>
          <option value="BUY">매수 (BUY)</option>
          <option value="SELL">매도 (SELL)</option>
        </select>

        <div className="flex gap-1">
          {["기본", "상세"].map((m) => (
            <button
              key={m}
              onClick={() => setViewMode(m)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                viewMode === m
                  ? "bg-primary text-on-primary"
                  : "bg-surface-container text-on-surface-variant hover:bg-surface-high"
              }`}
            >
              {m}
            </button>
          ))}
        </div>

        <div className="ml-auto text-[10px] text-on-surface-variant">
          Showing {filtered.length} of {MOCK_TRADES.length} trades
        </div>
      </div>

      {/* 거래 테이블 */}
      <div className="bg-surface-container rounded-xl border border-outline-variant/10 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
                <th className="px-6 py-3">Timestamp</th>
                <th className="px-4 py-3">Symbol</th>
                <th className="px-4 py-3">Side</th>
                <th className="px-4 py-3">Avg Entry</th>
                <th className="px-4 py-3">Executed</th>
                <th className="px-4 py-3">Qty</th>
                <th className="px-4 py-3">Realized PnL (KRW)</th>
                <th className="px-4 py-3">PnL (%)</th>
                <th className="px-4 py-3">Total</th>
                {viewMode === "상세" && <th className="px-4 py-3">Regime</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.map((t, i) => (
                <tr key={i} className="border-t border-outline-variant/5 hover:bg-surface-high/30 transition-colors">
                  <td className="px-6 py-4 text-xs text-on-surface-variant font-mono">{t.timestamp}</td>
                  <td className="px-4 py-4 text-sm font-semibold">{t.symbol.replace("KRW-", "")}</td>
                  <td className="px-4 py-4">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                      t.side === "BUY" ? "bg-primary/10 text-primary" : "bg-error/10 text-error"
                    }`}>
                      {t.side === "BUY" ? "매수" : "매도"}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-sm font-mono">{t.avgEntry}</td>
                  <td className="px-4 py-4 text-sm font-mono">{t.executed}</td>
                  <td className="px-4 py-4 text-sm font-mono">{t.qty}</td>
                  <td className={`px-4 py-4 text-sm font-mono font-semibold ${
                    t.realizedPnl === null ? "text-on-surface-variant" : Number(t.realizedPnl.replace(/,/g, "")) >= 0 ? "text-tertiary" : "text-error"
                  }`}>
                    {t.realizedPnl || "N/A"}
                  </td>
                  <td className={`px-4 py-4 text-sm font-mono ${
                    t.pnlPct === null ? "text-on-surface-variant" : Number(t.pnlPct) >= 0 ? "text-tertiary" : "text-error"
                  }`}>
                    {t.pnlPct ? `${t.pnlPct}%` : "N/A"}
                  </td>
                  <td className="px-4 py-4 text-sm font-mono">{t.total}</td>
                  {viewMode === "상세" && (
                    <td className="px-4 py-4 text-xs text-on-surface-variant">{t.regime}</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 하단 차트 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Buy/Sell 도넛 */}
        <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-6">
          <h4 className="text-sm font-bold text-on-surface-variant uppercase tracking-wider mb-4">
            Buy/Sell Volume Ratio
          </h4>
          <PlotlyChart
            data={[{
              values: [buyCount, sellCount],
              labels: ["BUY", "SELL"],
              type: "pie",
              hole: 0.5,
              marker: { colors: ["#adc6ff", "#ffb4ab"] },
              textinfo: "label+percent",
              textfont: { color: "#d7e3fc", size: 12 },
            }]}
            layout={{ height: 280, showlegend: false, margin: { l: 20, r: 20, t: 10, b: 10 } }}
          />
        </div>

        {/* Execution Status */}
        <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-6">
          <h4 className="text-sm font-bold text-on-surface-variant uppercase tracking-wider mb-4">
            Execution Status
          </h4>
          <PlotlyChart
            data={[{
              x: ["Filled", "Partial", "Cancelled", "Rejected"],
              y: [MOCK_TRADES.length, 0, 0, 0],
              type: "bar",
              marker: { color: "#adc6ff" },
            }]}
            layout={{
              height: 280,
              margin: { l: 40, r: 20, t: 10, b: 40 },
              yaxis: { title: "Count", gridcolor: "#1f2a3d" },
              xaxis: { gridcolor: "#1f2a3d" },
            }}
          />
        </div>
      </div>
    </div>
  );
}
