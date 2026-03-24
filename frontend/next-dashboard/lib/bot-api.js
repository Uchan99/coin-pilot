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
      // API 응답은 {"ok", "generated_at", "data": {...}} 구조 — data 내부에서 추출
      const posData = positionsRes?.data || {};
      const pnlData = pnlRes?.data || {};
      const riskData = riskRes?.data || {};

      // positions 엔드포인트: data.holdings 배열, data.cash_krw, data.total_valuation_krw
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
          // 총 평가액과 현금은 positions 응답에서, PnL/거래 수는 pnl 응답에서 가져옴
          totalValuationKrw: Number(posData?.total_valuation_krw || 0),
          cashKrw: Number(posData?.cash_krw || 0),
          dailyTotalPnlKrw: Number(pnlData?.daily_total_pnl_krw || 0),
          tradeCount: Number(pnlData?.trade_count || 0),
          buyCount: Number(pnlData?.buy_count || 0),
        },
        riskLevel: riskData?.risk_level || "UNKNOWN",
        riskFlags: riskData?.flags || riskData?.risk_flags || [],
        holdings,
        // generated_at는 최상위에 있음
        ...freshnessStatus(positionsRes?.generated_at || pnlRes?.generated_at || riskRes?.generated_at),
      };
    } catch (error) {
      return {
        metrics: { totalValuationKrw: 0, cashKrw: 0, dailyTotalPnlKrw: 0, tradeCount: 0, buyCount: 0 },
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
      const statusRes = await fetchApiJson("/api/mobile/status");
      // API 응답은 {"ok", "generated_at", "data": {...}} 구조
      const statusData = statusRes?.data || {};
      return {
        overallStatus: statusData?.overall_status || "UNKNOWN",
        riskLevel: statusData?.risk_level || "UNKNOWN",
        riskFlags: statusData?.risk_flags || [statusData?.overall_status, statusData?.risk_level].filter(Boolean).map(String),
        components: statusData?.components || {},
        // generated_at는 최상위에 있음
        ...freshnessStatus(statusRes?.generated_at),
      };
    } catch (error) {
      return {
        overallStatus: "UNKNOWN",
        riskLevel: "UNKNOWN",
        riskFlags: [String(error?.message || "상태 조회 실패")],
        components: { bot: { status: "UNKNOWN", detail: "조회 실패" } },
        ...freshnessStatus(null),
      };
    }
  }
