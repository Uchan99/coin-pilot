"use client";
import { useState, useEffect, useCallback } from "react";
import PlotlyChart from "@/components/plotly-chart";
import { getCandles, getBotBrain } from "@/lib/bot-api";

/*
 * Market Analysis 페이지 — Bot Brain + 캔들스틱 차트
 * Phase 3: /api/mobile/candles + /api/mobile/brain 실데이터 연동
 * 심볼/인터벌 변경 시 자동 재조회
 */

const SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP", "KRW-DOGE"];
const INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"];

const REGIME_COLORS = {
  BULL: { bg: "bg-tertiary/10", text: "text-tertiary", icon: "trending_up" },
  SIDEWAYS: { bg: "bg-yellow-500/10", text: "text-yellow-400", icon: "trending_flat" },
  BEAR: { bg: "bg-error/10", text: "text-error", icon: "trending_down" },
  UNKNOWN: { bg: "bg-outline-variant/10", text: "text-on-surface-variant", icon: "help" },
};

export default function MarketPage() {
  const [symbol, setSymbol] = useState("KRW-BTC");
  const [interval, setInterval] = useState("15m");
  const [candles, setCandles] = useState(null);
  const [brain, setBrain] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const [candleData, brainData] = await Promise.all([
      getCandles({ symbol, interval, limit: 200 }),
      getBotBrain(symbol),
    ]);
    setCandles(candleData);
    setBrain(brainData);
    setLoading(false);
  }, [symbol, interval]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const rc = REGIME_COLORS[brain?.regime] || REGIME_COLORS.UNKNOWN;
  const candleList = candles?.candles || [];
  const dates = candleList.map((c) => c.time);
  const opens = candleList.map((c) => c.open);
  const highs = candleList.map((c) => c.high);
  const lows = candleList.map((c) => c.low);
  const closes = candleList.map((c) => c.close);

  const lastClose = closes.length > 0 ? closes[closes.length - 1] : 0;
  const highMax = highs.length > 0 ? Math.max(...highs) : 0;
  const lowMin = lows.length > 0 ? Math.min(...lows.filter((v) => v > 0)) : 0;

  // 봇 브레인 freshness 계산
  let freshLabel = "N/A";
  if (brain?.timestamp) {
    const ageSec = Math.floor((Date.now() - new Date(brain.timestamp).getTime()) / 1000);
    freshLabel = ageSec <= 120 ? `${ageSec}s ago` : `${Math.floor(ageSec / 60)}m ago`;
  }

  // HWM 포맷
  const hwm = brain?.indicators?.hwm;
  const hwmDisplay = hwm && hwm > 0 ? `₩${Number(hwm).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}` : "N/A";
  const rsi = brain?.indicators?.rsi;
  const rsiDisplay = rsi != null ? Number(rsi).toFixed(1) : "N/A";

  return (
    <div className="space-y-6">
      {/* 컨트롤 바 */}
      <div className="flex items-center gap-4 flex-wrap">
        <select
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          className="bg-surface-container text-on-surface text-sm rounded-lg px-4 py-2 border border-outline-variant/20 focus:outline-none focus:border-primary/40"
        >
          {SYMBOLS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <div className="flex gap-1">
          {INTERVALS.map((iv) => (
            <button
              key={iv}
              onClick={() => setInterval(iv)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase transition-colors ${
                interval === iv
                  ? "bg-primary text-on-primary"
                  : "bg-surface-container text-on-surface-variant hover:bg-surface-high"
              }`}
            >
              {iv}
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2">
          {loading && <span className="text-xs text-primary animate-pulse">Loading...</span>}
          <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">
            Candles: {candleList.length}
          </span>
        </div>
      </div>

      {/* Bot Brain 카드 */}
      <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">psychology</span>
            <h3 className="font-bold">Bot Brain — {symbol}</h3>
          </div>
          <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${rc.bg} ${rc.text}`}>
            <span className="material-symbols-outlined text-sm">{rc.icon}</span>
            {brain?.regime || "UNKNOWN"}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Recommended Action</div>
            <div className="text-lg font-bold text-tertiary">{brain?.action || "UNKNOWN"}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">RSI (14)</div>
            <div className="text-lg font-bold">{rsiDisplay}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">HWM Price</div>
            <div className="text-lg font-bold">{hwmDisplay}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Last Update</div>
            <div className="text-lg font-bold">{freshLabel}</div>
          </div>
        </div>

        <div className="bg-surface-low rounded-lg p-4 border border-primary/10">
          <div className="flex items-start gap-2">
            <span className="material-symbols-outlined text-primary text-sm mt-0.5">smart_toy</span>
            <p className="text-xs text-on-surface-variant leading-relaxed">
              {brain?.reason || "봇 상태를 조회할 수 없습니다. 봇이 실행 중인지 확인하세요."}
            </p>
          </div>
        </div>
      </div>

      {/* 캔들스틱 차트 */}
      <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-4">
        <div className="flex items-center gap-2 mb-4 px-2">
          <h3 className="text-sm font-bold uppercase tracking-wider text-on-surface-variant">
            Live Chart
          </h3>
          {candleList.length > 0 && (
            <span className="text-[10px] text-primary uppercase font-bold">● Live Data</span>
          )}
        </div>
        {candleList.length > 0 ? (
          <PlotlyChart
            data={[
              {
                x: dates,
                open: opens,
                high: highs,
                low: lows,
                close: closes,
                type: "candlestick",
                increasing: { line: { color: "#4ae176" } },
                decreasing: { line: { color: "#ffb4ab" } },
              },
            ]}
            layout={{
              height: 500,
              xaxis: { rangeslider: { visible: false }, gridcolor: "#1f2a3d" },
              yaxis: {
                title: "Price (KRW)",
                gridcolor: "#1f2a3d",
                tickformat: ",d",
              },
              margin: { l: 80, r: 20, t: 10, b: 40 },
            }}
          />
        ) : (
          <div className="flex items-center justify-center h-[400px] text-on-surface-variant text-sm">
            {loading ? "차트 데이터 로딩 중..." : "캔들 데이터가 없습니다."}
          </div>
        )}
      </div>

      {/* 현재가 바 */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-surface-container rounded-xl p-4 border border-outline-variant/10">
          <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Current Price (KRW)</div>
          <div className="text-2xl font-bold">₩{lastClose.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}</div>
        </div>
        <div className="bg-surface-container rounded-xl p-4 border border-outline-variant/10">
          <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">24H High</div>
          <div className="text-2xl font-bold text-tertiary">₩{highMax.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}</div>
        </div>
        <div className="bg-surface-container rounded-xl p-4 border border-outline-variant/10">
          <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">24H Low</div>
          <div className="text-2xl font-bold text-error">₩{lowMin.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}</div>
        </div>
      </div>
    </div>
  );
}
