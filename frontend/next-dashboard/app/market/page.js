"use client";
import { useState } from "react";
import PlotlyChart from "@/components/plotly-chart";

/*
 * Market Analysis 페이지 — Bot Brain + 캔들스틱 차트
 * 현재 Phase 2 MVP: Mock 데이터로 UI 프레임 구현
 * 실제 OHLCV/Bot Status 데이터는 API route 추가 후 연동 예정
 */

const SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP", "KRW-DOGE"];
const INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"];

// 데모 캔들스틱 데이터 생성
function generateDemoCandles(count = 50) {
  const now = Date.now();
  const dates = [];
  const open = [];
  const high = [];
  const low = [];
  const close = [];
  let price = 98_000_000;

  for (let i = count; i >= 0; i--) {
    dates.push(new Date(now - i * 15 * 60 * 1000).toISOString());
    const o = price + (Math.random() - 0.5) * 500_000;
    const c = o + (Math.random() - 0.5) * 800_000;
    const h = Math.max(o, c) + Math.random() * 300_000;
    const l = Math.min(o, c) - Math.random() * 300_000;
    open.push(o);
    high.push(h);
    low.push(l);
    close.push(c);
    price = c;
  }
  return { dates, open, high, low, close };
}

export default function MarketPage() {
  const [symbol, setSymbol] = useState("KRW-BTC");
  const [interval, setInterval] = useState("15m");
  const candles = generateDemoCandles(50);

  // Bot Brain 목 데이터
  const botBrain = {
    regime: "BULL",
    action: "HOLD/BUY",
    rsi: 64.2,
    hwm: "₩98,420,000",
    lastUpdate: "42s ago",
    reasoning:
      "현재 KRW-BTC 시장은 긍정적 매수세가 유입되며 상승 Regime을 유지하고 있습니다. RSI 지표는 64.2로 과매수 구간에 근접해 있으나, 거래량 기준 상승 추세를 보이고 있습니다.",
  };

  const regimeColors = {
    BULL: { bg: "bg-tertiary/10", text: "text-tertiary", icon: "trending_up" },
    SIDEWAYS: { bg: "bg-yellow-500/10", text: "text-yellow-400", icon: "trending_flat" },
    BEAR: { bg: "bg-error/10", text: "text-error", icon: "trending_down" },
    UNKNOWN: { bg: "bg-outline-variant/10", text: "text-on-surface-variant", icon: "help" },
  };
  const rc = regimeColors[botBrain.regime] || regimeColors.UNKNOWN;

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

        <div className="ml-auto text-[10px] text-on-surface-variant uppercase tracking-wider">
          Candles: 50
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
            {botBrain.regime}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Recommended Action</div>
            <div className="text-lg font-bold text-tertiary">{botBrain.action}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">RSI (14)</div>
            <div className="text-lg font-bold">{botBrain.rsi}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">HWM Price</div>
            <div className="text-lg font-bold">{botBrain.hwm}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Last Update</div>
            <div className="text-lg font-bold">{botBrain.lastUpdate}</div>
          </div>
        </div>

        <div className="bg-surface-low rounded-lg p-4 border border-primary/10">
          <div className="flex items-start gap-2">
            <span className="material-symbols-outlined text-primary text-sm mt-0.5">smart_toy</span>
            <p className="text-xs text-on-surface-variant leading-relaxed">{botBrain.reasoning}</p>
          </div>
        </div>
      </div>

      {/* 캔들스틱 차트 */}
      <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-4">
        <div className="flex items-center gap-2 mb-4 px-2">
          <h3 className="text-sm font-bold uppercase tracking-wider text-on-surface-variant">
            Live Chart
          </h3>
          <span className="text-[10px] text-primary uppercase font-bold">● Real-time Data</span>
        </div>
        <PlotlyChart
          data={[
            {
              x: candles.dates,
              open: candles.open,
              high: candles.high,
              low: candles.low,
              close: candles.close,
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
      </div>

      {/* 현재가 바 */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-surface-container rounded-xl p-4 border border-outline-variant/10">
          <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Current Price (KRW)</div>
          <div className="text-2xl font-bold">₩{(candles.close[candles.close.length - 1] || 0).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}</div>
        </div>
        <div className="bg-surface-container rounded-xl p-4 border border-outline-variant/10">
          <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">24H High</div>
          <div className="text-2xl font-bold text-tertiary">₩{Math.max(...candles.high).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}</div>
        </div>
        <div className="bg-surface-container rounded-xl p-4 border border-outline-variant/10">
          <div className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">24H Low</div>
          <div className="text-2xl font-bold text-error">₩{Math.min(...candles.low).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}</div>
        </div>
      </div>
    </div>
  );
}
