from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from src.common.models import TradingHistory
from src.analytics.rule_funnel import RuleFunnelAnalyzer


@dataclass
class _SellSample:
    symbol: str
    regime: str
    exit_reason: str
    pnl_pct: float
    hold_hours: Optional[float]
    post_1h: Optional[float]
    post_4h: Optional[float]
    post_12h: Optional[float]
    post_24h: Optional[float]


class ExitPerformanceAnalyzer:
    """
    SELL 체결 이력을 기반으로 exit 성과를 집계하고 파라미터 튜닝 제안을 생성한다.
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

    @staticmethod
    def _to_decimal(v: Any) -> Optional[Decimal]:
        if v is None:
            return None
        try:
            return Decimal(str(v))
        except Exception:
            return None

    @staticmethod
    def _safe_float(v: Any) -> Optional[float]:
        if v is None:
            return None
        try:
            return float(v)
        except Exception:
            return None

    @staticmethod
    def _coalesced_ts(order: TradingHistory) -> datetime:
        return order.executed_at or order.created_at

    @staticmethod
    def _extract_post_change(post_exit_prices: Any, window: str) -> Optional[float]:
        if not isinstance(post_exit_prices, dict):
            return None
        point = post_exit_prices.get(window)
        if not isinstance(point, dict):
            return None
        return ExitPerformanceAnalyzer._safe_float(point.get("change_pct"))

    @staticmethod
    def _avg(values: List[float]) -> Optional[float]:
        if not values:
            return None
        return round(sum(values) / len(values), 4)

    @staticmethod
    def _min(values: List[float]) -> Optional[float]:
        return round(min(values), 4) if values else None

    @staticmethod
    def _max(values: List[float]) -> Optional[float]:
        return round(max(values), 4) if values else None

    @staticmethod
    def _median(values: List[float]) -> Optional[float]:
        return round(float(median(values)), 4) if values else None

    @staticmethod
    def _format_pct(v: Optional[float]) -> str:
        if v is None:
            return "N/A"
        return f"{v:.2f}%"

    @staticmethod
    def _build_rule_funnel_text(summary: Dict[str, Any]) -> str:
        by_regime = summary.get("by_regime", {})
        if not by_regime:
            return "- 데이터 없음"

        lines: List[str] = []
        for regime in ("BULL", "SIDEWAYS", "BEAR", "UNKNOWN"):
            regime_bucket = by_regime.get(regime)
            if not regime_bucket:
                continue
            lines.append(
                (
                    f"- {regime}: "
                    f"rule_pass={regime_bucket.get('rule_pass', {}).get('count', 0)}, "
                    f"risk_reject={regime_bucket.get('risk_reject', {}).get('count', 0)}, "
                    f"prefilter={regime_bucket.get('ai_prefilter_reject', {}).get('count', 0)}, "
                    f"guardrail={regime_bucket.get('ai_guardrail_block', {}).get('count', 0)}, "
                    f"ai_confirm={regime_bucket.get('ai_confirm', {}).get('count', 0)}, "
                    f"ai_reject={regime_bucket.get('ai_reject', {}).get('count', 0)}"
                )
            )
        return "\n".join(lines) if lines else "- 데이터 없음"

    @staticmethod
    def generate_tuning_suggestions_from_summary(
        summary: Dict[str, Any],
        min_samples: int = 20,
    ) -> List[str]:
        """
        테스트 가능한 순수 함수 형태의 튜닝 제안 로직.
        """
        total_sells = int(summary.get("total_sells", 0))
        if total_sells < min_samples:
            return [
                (
                    f"데이터 부족으로 제안 보류: SELL {total_sells}건 "
                    f"(최소 {min_samples}건 필요)"
                )
            ]

        suggestions: List[str] = []
        by_reason = summary.get("by_exit_reason", {})

        trailing = by_reason.get("TRAILING_STOP", {})
        if trailing.get("avg_post_24h_pct") is not None and trailing["avg_post_24h_pct"] > 3.0:
            suggestions.append(
                "TRAILING_STOP 이후 24h 평균 상승폭이 큼: trailing_stop_pct를 +0.5%p 완화 검토"
            )

        stop_loss = by_reason.get("STOP_LOSS", {})
        if stop_loss.get("avg_post_4h_pct") is not None and stop_loss["avg_post_4h_pct"] > 1.0:
            suggestions.append(
                "STOP_LOSS 이후 4h 반등이 관측됨: stop_loss_pct 완화 검토"
            )

        take_profit = by_reason.get("TAKE_PROFIT", {})
        if take_profit.get("avg_post_4h_pct") is not None and take_profit["avg_post_4h_pct"] > 2.0:
            suggestions.append(
                "TAKE_PROFIT 이후 4h 추가 상승이 큼: take_profit_pct 상향 검토"
            )

        time_limit = by_reason.get("TIME_LIMIT", {})
        if time_limit.get("avg_post_24h_pct") is not None and time_limit["avg_post_24h_pct"] < -2.0:
            suggestions.append(
                "TIME_LIMIT 이후 24h 추가 하락 경향: 현행 TIME_LIMIT 유지가 타당"
            )

        for regime, regime_stats in summary.get("by_regime", {}).items():
            early_rate = regime_stats.get("early_exit_rate")
            if early_rate is not None and early_rate > 0.40:
                suggestions.append(
                    f"{regime} 레짐 조기 청산율 {early_rate * 100:.1f}%: 해당 레짐 exit 파라미터 전반 재검토 권장"
                )

        if not suggestions:
            suggestions.append(
                "현재 데이터 기준 즉시 조정 필요 신호 없음: 현행 파라미터 유지하며 추가 데이터 수집 권장"
            )
        return suggestions

    async def _fetch_sell_orders(
        self,
        session: AsyncSession,
        start_ts: datetime,
        end_ts: datetime,
    ) -> List[TradingHistory]:
        stmt = (
            select(TradingHistory)
            .where(
                and_(
                    TradingHistory.side == "SELL",
                    TradingHistory.status == "FILLED",
                    or_(
                        and_(
                            TradingHistory.executed_at.is_not(None),
                            TradingHistory.executed_at >= start_ts,
                            TradingHistory.executed_at < end_ts,
                        ),
                        and_(
                            TradingHistory.executed_at.is_(None),
                            TradingHistory.created_at >= start_ts,
                            TradingHistory.created_at < end_ts,
                        ),
                    ),
                )
            )
            .order_by(func.coalesce(TradingHistory.executed_at, TradingHistory.created_at))
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def _build_buy_lots(
        self,
        session: AsyncSession,
        symbols: List[str],
        end_ts: datetime,
    ) -> Dict[str, List[Dict[str, Any]]]:
        if not symbols:
            return {}

        stmt = (
            select(TradingHistory)
            .where(
                and_(
                    TradingHistory.side == "BUY",
                    TradingHistory.status == "FILLED",
                    TradingHistory.symbol.in_(symbols),
                    or_(
                        and_(TradingHistory.executed_at.is_not(None), TradingHistory.executed_at < end_ts),
                        and_(TradingHistory.executed_at.is_(None), TradingHistory.created_at < end_ts),
                    ),
                )
            )
            .order_by(func.coalesce(TradingHistory.executed_at, TradingHistory.created_at))
        )
        result = await session.execute(stmt)
        orders = result.scalars().all()

        lots: Dict[str, List[Dict[str, Any]]] = {}
        for order in orders:
            symbol = order.symbol
            price = self._to_decimal(order.price)
            qty = self._to_decimal(order.quantity)
            if price is None or qty is None or qty <= 0:
                continue
            if symbol not in lots:
                lots[symbol] = []
            lots[symbol].append(
                {
                    "qty": qty,
                    "price": price,
                    "ts": self._coalesced_ts(order),
                }
            )
        return lots

    def _consume_entry(self, buy_lots: Dict[str, List[Dict[str, Any]]], symbol: str, sell_qty: Decimal) -> Tuple[Optional[Decimal], Optional[datetime]]:
        lots = buy_lots.get(symbol, [])
        if not lots or sell_qty <= 0:
            return None, None

        remaining = sell_qty
        consumed = Decimal("0")
        total_cost = Decimal("0")
        first_ts: Optional[datetime] = None

        while remaining > 0 and lots:
            lot = lots[0]
            lot_qty = lot["qty"]
            if lot_qty <= 0:
                lots.pop(0)
                continue

            use_qty = lot_qty if lot_qty <= remaining else remaining
            if first_ts is None:
                first_ts = lot["ts"]
            total_cost += lot["price"] * use_qty
            consumed += use_qty
            remaining -= use_qty

            lot["qty"] = lot_qty - use_qty
            if lot["qty"] <= 0:
                lots.pop(0)

        if consumed <= 0:
            return None, None
        return total_cost / consumed, first_ts

    async def summarize_period(self, days: int = 7) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        start_ts = now - timedelta(days=days)

        async with self.session_factory() as session:
            sells = await self._fetch_sell_orders(session, start_ts, now)
            symbols = sorted({s.symbol for s in sells})
            buy_lots = await self._build_buy_lots(session, symbols=symbols, end_ts=now)

        samples: List[_SellSample] = []

        for order in sells:
            sell_ts = self._coalesced_ts(order)
            symbol = order.symbol
            regime = order.regime or "UNKNOWN"
            exit_reason = order.exit_reason or "UNKNOWN"
            price = self._to_decimal(order.price)
            qty = self._to_decimal(order.quantity)
            if price is None or qty is None or qty <= 0:
                continue

            entry_avg = None
            entry_ts = None
            signal_info = order.signal_info if isinstance(order.signal_info, dict) else {}
            if signal_info:
                entry_avg = self._to_decimal(signal_info.get("entry_avg_price"))
            if entry_avg is None:
                entry_avg, entry_ts = self._consume_entry(buy_lots, symbol, qty)

            if entry_avg is None or entry_avg <= 0:
                continue

            pnl_pct = float((price - entry_avg) / entry_avg * Decimal("100"))
            hold_hours = None
            if entry_ts is not None:
                delta = sell_ts - entry_ts
                hold_hours = round(delta.total_seconds() / 3600.0, 4)

            samples.append(
                _SellSample(
                    symbol=symbol,
                    regime=regime,
                    exit_reason=exit_reason,
                    pnl_pct=round(pnl_pct, 6),
                    hold_hours=hold_hours,
                    post_1h=self._extract_post_change(order.post_exit_prices, "1h"),
                    post_4h=self._extract_post_change(order.post_exit_prices, "4h"),
                    post_12h=self._extract_post_change(order.post_exit_prices, "12h"),
                    post_24h=self._extract_post_change(order.post_exit_prices, "24h"),
                )
            )

        by_reason: Dict[str, Dict[str, Any]] = {}
        by_regime: Dict[str, Dict[str, Any]] = {}
        by_regime_reason: Dict[str, Dict[str, Dict[str, Any]]] = {}

        def _ensure_bucket(bucket_map: Dict[str, Dict[str, Any]], key: str) -> Dict[str, Any]:
            if key not in bucket_map:
                bucket_map[key] = {
                    "count": 0,
                    "pnl": [],
                    "hold_hours": [],
                    "post_1h": [],
                    "post_4h": [],
                    "post_12h": [],
                    "post_24h": [],
                    "early_exit_24h_plus2": 0,
                    "time_limit_24h_minus3": 0,
                    "post24_count": 0,
                    "early_exit_target_count": 0,
                    "time_limit_target_count": 0,
                }
            return bucket_map[key]

        for s in samples:
            reason_bucket = _ensure_bucket(by_reason, s.exit_reason)
            regime_bucket = _ensure_bucket(by_regime, s.regime)
            regime_reason_map = by_regime_reason.setdefault(s.regime, {})
            regime_reason_bucket = _ensure_bucket(regime_reason_map, s.exit_reason)

            for bucket in (reason_bucket, regime_bucket, regime_reason_bucket):
                bucket["count"] += 1
                bucket["pnl"].append(s.pnl_pct)
                if s.hold_hours is not None:
                    bucket["hold_hours"].append(s.hold_hours)
                if s.post_1h is not None:
                    bucket["post_1h"].append(s.post_1h)
                if s.post_4h is not None:
                    bucket["post_4h"].append(s.post_4h)
                if s.post_12h is not None:
                    bucket["post_12h"].append(s.post_12h)
                if s.post_24h is not None:
                    bucket["post_24h"].append(s.post_24h)
                    bucket["post24_count"] += 1

                if s.exit_reason in {"TRAILING_STOP", "TAKE_PROFIT"}:
                    bucket["early_exit_target_count"] += 1
                    if s.post_24h is not None and s.post_24h > 2.0:
                        bucket["early_exit_24h_plus2"] += 1

                if s.exit_reason == "TIME_LIMIT":
                    bucket["time_limit_target_count"] += 1
                    if s.post_24h is not None and s.post_24h < -3.0:
                        bucket["time_limit_24h_minus3"] += 1

        def _finalize(bucket: Dict[str, Any]) -> Dict[str, Any]:
            early_target = bucket["early_exit_target_count"]
            tl_target = bucket["time_limit_target_count"]
            return {
                "count": bucket["count"],
                "avg_pnl_pct": self._avg(bucket["pnl"]),
                "avg_hold_hours": self._avg(bucket["hold_hours"]),
                "avg_post_1h_pct": self._avg(bucket["post_1h"]),
                "avg_post_4h_pct": self._avg(bucket["post_4h"]),
                "avg_post_12h_pct": self._avg(bucket["post_12h"]),
                "avg_post_24h_pct": self._avg(bucket["post_24h"]),
                "median_post_24h_pct": self._median(bucket["post_24h"]),
                "min_post_24h_pct": self._min(bucket["post_24h"]),
                "max_post_24h_pct": self._max(bucket["post_24h"]),
                "post_24h_samples": bucket["post24_count"],
                "early_exit_rate": (
                    round(bucket["early_exit_24h_plus2"] / early_target, 4) if early_target > 0 else None
                ),
                "over_hold_rate": (
                    round(bucket["time_limit_24h_minus3"] / tl_target, 4) if tl_target > 0 else None
                ),
            }

        summary = {
            "period_days": days,
            "period_start": start_ts.isoformat(),
            "period_end": now.isoformat(),
            "total_sells": len(samples),
            "by_exit_reason": {k: _finalize(v) for k, v in by_reason.items()},
            "by_regime": {k: _finalize(v) for k, v in by_regime.items()},
            "by_regime_exit_reason": {
                regime: {reason: _finalize(bucket) for reason, bucket in reason_map.items()}
                for regime, reason_map in by_regime_reason.items()
            },
        }
        return summary

    async def build_weekly_report_payload(self, days: int = 7, min_samples: int = 20) -> Dict[str, Any]:
        summary = await self.summarize_period(days=days)
        suggestions = self.generate_tuning_suggestions_from_summary(summary, min_samples=min_samples)
        funnel_analyzer = RuleFunnelAnalyzer(self.session_factory)
        funnel_summary = await funnel_analyzer.summarize_period(days=days)
        funnel_suggestions = RuleFunnelAnalyzer.generate_review_suggestions_from_summary(
            funnel_summary,
            target_regime="BULL",
            min_rule_pass=5,
        )
        llm_summary = await self._generate_llm_summary(
            summary,
            suggestions,
            funnel_summary=funnel_summary,
            funnel_suggestions=funnel_suggestions,
        )

        payload = {
            "title": f"📊 CoinPilot Weekly Exit Report ({days}d)",
            "period_days": days,
            "period_start": summary["period_start"],
            "period_end": summary["period_end"],
            "total_sells": summary["total_sells"],
            "by_exit_reason": summary["by_exit_reason"],
            "by_regime": summary["by_regime"],
            "suggestions": suggestions,
            "rule_funnel": funnel_summary,
            "rule_funnel_suggestions": funnel_suggestions,
            "summary": llm_summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return payload

    async def _generate_llm_summary(
        self,
        summary: Dict[str, Any],
        suggestions: List[str],
        *,
        funnel_summary: Dict[str, Any] | None = None,
        funnel_suggestions: List[str] | None = None,
    ) -> str:
        by_reason = summary.get("by_exit_reason", {})
        lines: List[str] = []
        for reason, v in sorted(by_reason.items(), key=lambda kv: kv[1].get("count", 0), reverse=True):
            lines.append(
                f"- {reason}: count={v.get('count', 0)}, avg_pnl={self._format_pct(v.get('avg_pnl_pct'))}, "
                f"avg_post_24h={self._format_pct(v.get('avg_post_24h_pct'))}, early_exit_rate={v.get('early_exit_rate')}"
            )
        reason_text = "\n".join(lines) if lines else "- 데이터 없음"
        suggestion_text = "\n".join(f"- {s}" for s in suggestions)
        funnel_text = self._build_rule_funnel_text(funnel_summary or {})
        funnel_suggestion_text = "\n".join(f"- {s}" for s in (funnel_suggestions or [])) or "- 데이터 없음"

        prompt = PromptTemplate(
            input_variables=[
                "period_days",
                "total_sells",
                "reason_text",
                "suggestion_text",
                "funnel_text",
                "funnel_suggestion_text",
            ],
            template="""
당신은 CoinPilot 운영 분석가입니다.
다음 데이터를 기반으로 4줄 이내의 주간 운영 요약을 작성하세요.

[기본]
- 분석 기간: 최근 {period_days}일
- SELL 샘플 수: {total_sells}

[Exit Reason 요약]
{reason_text}

[Exit 기반 자동 제안]
{suggestion_text}

[Rule Funnel 요약]
{funnel_text}

[Rule Funnel 자동 제안]
{funnel_suggestion_text}

규칙:
1) 숫자 근거를 최소 1개 포함
2) 데이터 부족이면 과도한 추정 금지
3) 실행 가능한 조치 1개만 명시
""",
        )

        chain = prompt | self.llm
        try:
            response = await chain.ainvoke(
                {
                    "period_days": summary.get("period_days", 7),
                    "total_sells": summary.get("total_sells", 0),
                    "reason_text": reason_text,
                    "suggestion_text": suggestion_text,
                    "funnel_text": funnel_text,
                    "funnel_suggestion_text": funnel_suggestion_text,
                }
            )
            return response.content
        except Exception as e:
            return (
                f"LLM 요약 생성 실패 ({e}). "
                f"기본 요약: sells={summary.get('total_sells', 0)}, "
                f"suggestions={len(suggestions)}, "
                f"funnel_suggestions={len(funnel_suggestions or [])}"
            )
