"use client";
import { useState, useEffect, useCallback } from "react";
import PlotlyChart from "@/components/plotly-chart";
import { getTrades } from "@/lib/bot-api";
import { formatKrw } from "@/lib/formatters";

/*
 * Trade History 페이지 — Stitch 디자인
 * Phase 3: /api/mobile/trades 실데이터 연동 + 페이징/필터
 */

export default function HistoryPage() {
  const [sideFilter, setSideFilter] = useState("ALL");
  const [symbolSearch, setSymbolSearch] = useState("");
  const [viewMode, setViewMode] = useState("기본");
  const [trades, setTrades] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const PAGE_SIZE = 50;

  const fetchData = useCallback(async () => {
    setLoading(true);
    const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE };
    if (sideFilter !== "ALL") params.side = sideFilter;
    if (symbolSearch.trim()) params.symbol = `KRW-${symbolSearch.trim().toUpperCase()}`;
    const data = await getTrades(params);
    setTrades(data.trades || []);
    setTotal(data.total || 0);
    setLoading(false);
  }, [sideFilter, symbolSearch, page]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // 페이지 변경 시 맨 위로 스크롤 리셋
  useEffect(() => { setPage(0); }, [sideFilter, symbolSearch]);

  const buyCount = trades.filter((t) => t.side === "BUY").length;
  const sellCount = trades.filter((t) => t.side === "SELL").length;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-6">
      {/* 필터 바 */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-lg">search</span>
          <input
            type="text"
            value={symbolSearch}
            onChange={(e) => setSymbolSearch(e.target.value)}
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

        <div className="ml-auto flex items-center gap-3">
          {loading && <span className="text-xs text-primary animate-pulse">Loading...</span>}
          <span className="text-[10px] text-on-surface-variant">
            {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total} trades
          </span>
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
                <th className="px-4 py-3">Price</th>
                <th className="px-4 py-3">Qty</th>
                <th className="px-4 py-3">Realized PnL</th>
                <th className="px-4 py-3">PnL (%)</th>
                {viewMode === "상세" && <th className="px-4 py-3">Regime</th>}
                {viewMode === "상세" && <th className="px-4 py-3">Exit Reason</th>}
              </tr>
            </thead>
            <tbody>
              {trades.length === 0 ? (
                <tr>
                  <td colSpan={viewMode === "상세" ? 9 : 7} className="px-6 py-12 text-center text-on-surface-variant text-sm">
                    {loading ? "로딩 중..." : "거래 내역이 없습니다."}
                  </td>
                </tr>
              ) : (
                trades.map((t, i) => (
                  <tr key={i} className="border-t border-outline-variant/5 hover:bg-surface-high/30 transition-colors">
                    <td className="px-6 py-4 text-xs text-on-surface-variant font-mono">{t.filled_at_kst || "-"}</td>
                    <td className="px-4 py-4 text-sm font-semibold">{(t.symbol || "").replace("KRW-", "")}</td>
                    <td className="px-4 py-4">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                        t.side === "BUY" ? "bg-primary/10 text-primary" : "bg-error/10 text-error"
                      }`}>
                        {t.side === "BUY" ? "매수" : "매도"}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-sm font-mono">{t.price != null ? formatKrw(t.price) : "N/A"}</td>
                    <td className="px-4 py-4 text-sm font-mono">{t.quantity != null ? Number(t.quantity).toFixed(8).replace(/0+$/, "").replace(/\.$/, "") : "N/A"}</td>
                    <td className={`px-4 py-4 text-sm font-mono font-semibold ${
                      t.realized_pnl_krw == null ? "text-on-surface-variant" : t.realized_pnl_krw >= 0 ? "text-tertiary" : "text-error"
                    }`}>
                      {t.realized_pnl_krw != null ? formatKrw(t.realized_pnl_krw, true) : "N/A"}
                    </td>
                    <td className={`px-4 py-4 text-sm font-mono ${
                      t.realized_pnl_pct == null ? "text-on-surface-variant" : t.realized_pnl_pct >= 0 ? "text-tertiary" : "text-error"
                    }`}>
                      {t.realized_pnl_pct != null ? `${t.realized_pnl_pct >= 0 ? "+" : ""}${t.realized_pnl_pct.toFixed(2)}%` : "N/A"}
                    </td>
                    {viewMode === "상세" && <td className="px-4 py-4 text-xs text-on-surface-variant">{t.regime || "-"}</td>}
                    {viewMode === "상세" && <td className="px-4 py-4 text-xs text-on-surface-variant">{t.exit_reason || "-"}</td>}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* 페이징 */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 py-4 border-t border-outline-variant/10">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-3 py-1.5 rounded-lg text-xs font-bold bg-surface-high text-on-surface-variant disabled:opacity-30"
            >
              Prev
            </button>
            <span className="text-xs text-on-surface-variant">{page + 1} / {totalPages}</span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="px-3 py-1.5 rounded-lg text-xs font-bold bg-surface-high text-on-surface-variant disabled:opacity-30"
            >
              Next
            </button>
          </div>
        )}
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

        {/* Total 통계 */}
        <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-6">
          <h4 className="text-sm font-bold text-on-surface-variant uppercase tracking-wider mb-4">
            Trade Statistics
          </h4>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-surface-low rounded-lg p-4">
              <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Total Trades</div>
              <div className="text-2xl font-bold">{total}</div>
            </div>
            <div className="bg-surface-low rounded-lg p-4">
              <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Current Page</div>
              <div className="text-2xl font-bold">{trades.length}건</div>
            </div>
            <div className="bg-surface-low rounded-lg p-4">
              <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Buy (this page)</div>
              <div className="text-2xl font-bold text-primary">{buyCount}</div>
            </div>
            <div className="bg-surface-low rounded-lg p-4">
              <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Sell (this page)</div>
              <div className="text-2xl font-bold text-error">{sellCount}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
