const BOT_API_BASE_URL = (process.env.BOT_API_BASE_URL || "http://bot:8000").replace(/\/+$/, "");
  const API_SECRET = process.env.COINPILOT_API_SHARED_SECRET || "";
  const API_TIMEOUT_MS = 5000;
  const SHARED_SECRET_HEADER = "X-Api-Secret";

  function headers() {
    const h = { accept: "application/json" };
    if (API_SECRET) h[SHARED_SECRET_HEADER] = API_SECRET;
    return h;
  }

  function freshnessStatus(generatedAt) {
    if (!generatedAt) return { freshnessStatus: "failed", dataAgeSec: null, staleThresholdSec: 60, delayedThresholdSec: 20 };
    const ageSec = Math.max(0, Math.floor((Date.now() - new Date(generatedAt).getTime()) / 1000));
    if (Number.isNaN(ageSec)) return { freshnessStatus: "failed", dataAgeSec: null, staleThresholdSec: 60, delayedThresholdSec: 20 };
    if (ageSec <= 20) return { freshnessStatus: "fresh", dataAgeSec: ageSec, staleThresholdSec: 60, delayedThresholdSec: 20 };
    if (ageSec <= 60) return { freshnessStatus: "delayed", dataAgeSec: ageSec, staleThresholdSec: 60, delayedThresholdSec: 20 };
    return { freshnessStatus: "stale", dataAgeSec: ageSec, staleThresholdSec: 60, delayedThresholdSec: 20 };
  }

  async function fetchApiJson(path) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
    try {
      const res = await fetch(`${BOT_API_BASE_URL}${path}`, { headers: headers(), cache: "no-store", signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } finally {
      clearTimeout(timer);
    }
  }

  export async function getOverviewSnapshot() {
    try {
      const [positionsRes, pnlRes, riskRes] = await Promise.all([
        fetchApiJson("/api/mobile/positions"),
        fetchApiJson("/api/mobile/pnl"),
        fetchApiJson("/api/mobile/risk"),
      ]);
      const posData = positionsRes?.data || {};
      const pnlData = pnlRes?.data || {};
      const riskData = riskRes?.data || {};

      const positions = Array.isArray(posData?.holdings) ? posData.holdings : [];
      const holdings = positions.map((item) => ({
        symbol: item.symbol,
        quantity: Number(item.quantity) || 0,
        avg_price: Number(item.avg_price) || 0,
        current_price: Number(item.current_price) || 0,
        valuation_krw: Number(item.valuation_krw) || 0,
        unrealized_pnl_krw: Number(item.unrealized_pnl_krw) || 0,
        unrealized_pnl_pct: item.unrealized_pnl_pct != null ? Number(item.unrealized_pnl_pct) : null,
      }));
      return {
        metrics: {
          totalValuationKrw: Number(posData?.total_valuation_krw || 0),
          cashKrw: Number(posData?.cash_krw || 0),
          // 누적(전체 기간) 값 — Streamlit과 동일하게 SUM/COUNT 기반
          cumulativePnlKrw: Number(pnlData?.cumulative_pnl_krw || 0),
          cumulativeTradeCount: Number(pnlData?.cumulative_trade_count || 0),
          // 당일 값 (참고용)
          dailyTotalPnlKrw: Number(pnlData?.daily_total_pnl_krw || 0),
          tradeCount: Number(pnlData?.trade_count || 0),
          buyCount: Number(pnlData?.buy_count || 0),
        },
        riskLevel: riskData?.risk_level || "UNKNOWN",
        riskFlags: riskData?.flags || riskData?.risk_flags || [],
        holdings,
        ...freshnessStatus(positionsRes?.generated_at || pnlRes?.generated_at || riskRes?.generated_at),
      };
    } catch (error) {
      return {
        metrics: { totalValuationKrw: 0, cashKrw: 0, cumulativePnlKrw: 0, cumulativeTradeCount: 0, dailyTotalPnlKrw: 0, tradeCount: 0, buyCount: 0 },
        riskLevel: "UNKNOWN",
        riskFlags: [String(error?.message || "데이터 조회 실패")],
        holdings: [],
        ...freshnessStatus(null),
      };
    }
  }

  /*
   * Risk 상세 데이터 — Risk Monitor 페이지용
   * pnl + risk 엔드포인트를 조합해 게이지/카운트/감사 로그에 필요한 데이터를 반환
   */
  export async function getRiskSnapshot() {
    try {
      const [pnlRes, riskRes] = await Promise.all([
        fetchApiJson("/api/mobile/pnl"),
        fetchApiJson("/api/mobile/risk"),
      ]);
      const pnlData = pnlRes?.data || {};
      const riskData = riskRes?.data || {};
      return {
        dailyTotalPnlKrw: Number(pnlData?.daily_total_pnl_krw || 0),
        buyCount: Number(pnlData?.buy_count || 0),
        sellCount: Number(pnlData?.sell_count || 0),
        tradeCount: Number(pnlData?.trade_count || 0),
        consecutiveLosses: Number(riskData?.consecutive_losses || 0),
        isTradingHalted: riskData?.is_trading_halted || false,
        riskLevel: riskData?.risk_level || "UNKNOWN",
        riskFlags: riskData?.flags || riskData?.risk_flags || [],
        ...freshnessStatus(pnlRes?.generated_at || riskRes?.generated_at),
      };
    } catch (error) {
      return {
        dailyTotalPnlKrw: 0, buyCount: 0, sellCount: 0, tradeCount: 0,
        consecutiveLosses: 0, isTradingHalted: false,
        riskLevel: "UNKNOWN", riskFlags: [String(error?.message || "조회 실패")],
        ...freshnessStatus(null),
      };
    }
  }

  export async function getSystemSnapshot() {
    try {
      const [statusRes, decisionsRes] = await Promise.all([
        fetchApiJson("/api/mobile/status"),
        fetchApiJson("/api/mobile/ai-decisions?limit=10"),
      ]);
      const statusData = statusRes?.data || {};
      const decisionsData = decisionsRes?.data || {};
      return {
        overallStatus: statusData?.overall_status || "UNKNOWN",
        riskLevel: statusData?.risk_level || "UNKNOWN",
        riskFlags: statusData?.risk_flags || [],
        components: statusData?.components || {},
        decisions: decisionsData?.decisions || [],
        ...freshnessStatus(statusRes?.generated_at),
      };
    } catch (error) {
      return {
        overallStatus: "UNKNOWN",
        riskLevel: "UNKNOWN",
        riskFlags: [String(error?.message || "상태 조회 실패")],
        components: { bot: { status: "UNKNOWN", detail: "조회 실패" } },
        decisions: [],
        ...freshnessStatus(null),
      };
    }
  }

  /*
   * Phase 3 클라이언트용 API 함수
   * Client Component(브라우저)에서 호출 → Next.js API Route Handler(프록시) → 백엔드
   * 브라우저는 Docker 내부 주소(bot:8000)에 접근 불가하므로, /api/* 프록시 경로를 사용
   */

  /**
   * 클라이언트용 fetch — 브라우저에서 Next.js 프록시 route로 요청
   * Server Component에서는 fetchApiJson을, Client Component에서는 이 함수를 사용
   */
  async function fetchClientJson(proxyPath) {
    const res = await fetch(proxyPath, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  }

  /* 거래 내역 — History 탭 (Client Component) */
  export async function getTrades({ symbol, side, limit = 50, offset = 0 } = {}) {
    try {
      const params = new URLSearchParams();
      if (symbol) params.set("symbol", symbol);
      if (side) params.set("side", side);
      params.set("limit", String(limit));
      params.set("offset", String(offset));
      const res = await fetchClientJson(`/api/history/trades?${params}`);
      return res?.data || { trades: [], total: 0, limit, offset };
    } catch {
      return { trades: [], total: 0, limit, offset };
    }
  }

  /* 캔들 데이터 — Market 탭 (Client Component) */
  export async function getCandles({ symbol = "KRW-BTC", interval = "15m", limit = 200 } = {}) {
    try {
      const params = new URLSearchParams({ symbol, interval, limit: String(limit) });
      const res = await fetchClientJson(`/api/market/candles?${params}`);
      return res?.data || { symbol, interval, candles: [] };
    } catch {
      return { symbol, interval, candles: [] };
    }
  }

  /* 봇 브레인 상태 — Market 탭 (Client Component) */
  export async function getBotBrain(symbol = "KRW-BTC") {
    try {
      const res = await fetchClientJson(`/api/market/brain?symbol=${encodeURIComponent(symbol)}`);
      return res?.data || { available: false, symbol, regime: "UNKNOWN", action: "UNKNOWN", indicators: {}, reason: "" };
    } catch {
      return { available: false, symbol, regime: "UNKNOWN", action: "UNKNOWN", indicators: {}, reason: "조회 실패" };
    }
  }

  /* 매도 분석 — Exit Analysis 탭 (Client Component) */
  export async function getExitAnalysis({ days = 30, limit = 800 } = {}) {
    try {
      const params = new URLSearchParams({ days: String(days), limit: String(limit) });
      const res = await fetchClientJson(`/api/exit-analysis/data?${params}`);
      return res?.data || { kpi: {}, post_exit_avg: {}, heatmap: [], sells: [], filter: { days, limit } };
    } catch {
      return { kpi: {}, post_exit_avg: {}, heatmap: [], sells: [], filter: { days, limit } };
    }
  }

  /* AI 챗봇 — Chatbot 탭 (Client Component) */
  export async function askChatbot(query, sessionId = null) {
    try {
      const res = await fetch("/api/chatbot/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify({ query, session_id: sessionId }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      return json?.data?.answer || "응답을 받지 못했습니다.";
    } catch (error) {
      return `오류: ${error?.message || "AI 응답 실패"}`;
    }
  }

  /* 누적 PnL — Control Center용 (Server Component) */
  export async function getCumulativePnl() {
    try {
      const res = await fetchApiJson("/api/mobile/pnl");
      const data = res?.data || {};
      return {
        cumulativePnlKrw: Number(data?.cumulative_pnl_krw || 0),
        cumulativeTradeCount: Number(data?.cumulative_trade_count || 0),
        dailyTotalPnlKrw: Number(data?.daily_total_pnl_krw || 0),
      };
    } catch {
      return { cumulativePnlKrw: 0, cumulativeTradeCount: 0, dailyTotalPnlKrw: 0 };
    }
  }
