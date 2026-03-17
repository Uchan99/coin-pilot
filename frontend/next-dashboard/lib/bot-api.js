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

      const positions = Array.isArray(posData?.positions) ? posData.positions : (Array.isArray(posData) ? posData : []);
      const holdings = positions.map((item) => ({
        symbol: item.symbol,
        quantity: Number(item.quantity) || 0,
        avg_price: Number(item.avg_price ?? item.avgPrice) || 0,
        current_price: Number(item.current_price ?? item.currentPrice) || 0,
        valuation_krw: Number(item.valuation_krw ?? item.valuation) || 0,
        unrealized_pnl_krw: Number(item.unrealized_pnl_krw ?? item.pnl) || 0,
      }));
      return {
        metrics: {
          totalValuationKrw: holdings.reduce((a, h) => a + h.valuation_krw, 0),
          cashKrw: Number(pnlData?.cash_krw || 0),
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

  export async function getSystemSnapshot() {
    try {
      const statusRes = await fetchApiJson("/api/mobile/status");
      // API 응답은 {"ok", "generated_at", "data": {...}} 구조
      const d = statusRes?.data || {};
      return {
        overallStatus: d?.overall_status || "UNKNOWN",
        riskLevel: d?.risk_level || "UNKNOWN",
        riskFlags: d?.risk_flags || [d?.overall_status, d?.risk_level].filter(Boolean).map(String),
        components: d?.components || {},
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
