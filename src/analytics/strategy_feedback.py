from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from src.analytics.exit_performance import ExitPerformanceAnalyzer
from src.analytics.rule_funnel import RuleFunnelAnalyzer
from src.common.models import AgentDecision, LlmProviderCostSnapshot, LlmUsageEvent
from src.config.strategy import load_strategy_config


@dataclass
class _SellSequenceMetrics:
    total_sells: int
    avg_realized_pnl_pct: Optional[float]
    profit_factor: Optional[float]
    max_drawdown_pct: Optional[float]


class StrategyFeedbackAnalyzer:
    """
    전략 피드백 자동화의 1차 분석기.

    설계 의도:
    - 기존 Exit/Rule Funnel 분석기를 재사용해 "주간 전략 피드백"용 단일 payload를 만든다.
    - 승인형 운영 원칙을 지키기 위해 후보 생성(candidate)과 승인 가능 여부(gate)를 분리한다.
    - 아직 자동 적용기는 없으므로, 본 분석기의 출력은 "추천/보류/폐기 판단 + 근거"에만 사용한다.
    """

    def __init__(self, session_factory, *, strategy_config_path: str = "config/strategy_v3.yaml"):
        self.session_factory = session_factory
        self.strategy_config_path = strategy_config_path
        self.strategy_config = load_strategy_config(strategy_config_path)

    @staticmethod
    def _safe_pct_delta(current: Optional[float], previous: Optional[float]) -> Optional[float]:
        if current is None or previous is None:
            return None
        if abs(previous) < 1e-9:
            return None
        return round(((current - previous) / abs(previous)) * 100.0, 4)

    @staticmethod
    def _safe_ratio(numerator: int, denominator: int) -> Optional[float]:
        if denominator <= 0:
            return None
        return round((numerator / denominator) * 100.0, 4)

    @staticmethod
    def _weighted_avg_pnl_pct(summary: Dict[str, Any]) -> Optional[float]:
        by_reason = summary.get("by_exit_reason", {})
        total_count = 0
        weighted_sum = 0.0
        for bucket in by_reason.values():
            count = int(bucket.get("count", 0) or 0)
            avg_pnl_pct = bucket.get("avg_pnl_pct")
            if count <= 0 or avg_pnl_pct is None:
                continue
            total_count += count
            weighted_sum += float(avg_pnl_pct) * count
        if total_count <= 0:
            return None
        return round(weighted_sum / total_count, 4)

    @staticmethod
    def _stage_count(summary: Dict[str, Any], regime: str, stage: str) -> int:
        return int(
            summary.get("by_regime", {})
            .get(regime, {})
            .get(stage, {})
            .get("count", 0)
        )

    @staticmethod
    def determine_approval_tier(total_sells: int) -> str:
        if total_sells >= 20:
            return "strong_approval"
        if total_sells >= 12:
            return "reviewable"
        return "hold"

    @staticmethod
    def determine_gate_result(
        approval_tier: str,
        hold_reasons: List[str],
        discard_reasons: List[str],
        candidate_changes: List[Dict[str, Any]],
    ) -> str:
        if discard_reasons:
            return "discard"
        if hold_reasons or not candidate_changes:
            return "hold"
        if approval_tier in {"reviewable", "strong_approval"}:
            return "recommend"
        return "hold"

    def _strategy_config_hash(self) -> str:
        config_path = Path(self.strategy_config_path)
        if not config_path.exists():
            return "missing"
        return sha256(config_path.read_bytes()).hexdigest()

    def _regime_exit_value(self, regime: str, key: str) -> Optional[float]:
        regime_bucket = self.strategy_config.REGIMES.get(regime, {})
        exit_bucket = regime_bucket.get("exit", {})
        raw_value = exit_bucket.get(key)
        if raw_value is None:
            return None
        try:
            return float(raw_value)
        except Exception:
            return None

    def _dominant_regime(self, summary: Dict[str, Any]) -> str:
        by_regime = summary.get("by_regime", {})
        ranked = sorted(
            by_regime.items(),
            key=lambda kv: int(kv[1].get("count", 0) or 0),
            reverse=True,
        )
        if not ranked:
            return "SIDEWAYS"
        return ranked[0][0]

    def _build_candidate_changes(
        self,
        exit_summary: Dict[str, Any],
        funnel_summary: Dict[str, Any],
        approval_tier: str,
    ) -> List[Dict[str, Any]]:
        """
        후보 생성은 가능하면 숫자 기준을 직접 사용하고, 표본 부족 시에도 "후보만 생성"할 수 있게 한다.

        주의:
        - 리스크 절대 한도는 여기서 건드리지 않는다.
        - Rule Funnel 병목이 `max_per_order` 같은 운영 한도에 몰리면 전략 파라미터 후보를 억지로 만들지 않는다.
        """
        candidates: List[Dict[str, Any]] = []
        dominant_regime = self._dominant_regime(exit_summary)
        by_reason = exit_summary.get("by_exit_reason", {})
        top_reasons = funnel_summary.get("top_reasons", [])

        max_per_order_bottleneck = any(
            reason.get("reason_code") == "max_per_order"
            for reason in top_reasons
        )
        if max_per_order_bottleneck:
            return candidates

        trailing = by_reason.get("TRAILING_STOP", {})
        if trailing.get("avg_post_24h_pct") is not None and float(trailing["avg_post_24h_pct"]) > 3.0:
            current_value = self._regime_exit_value(dominant_regime, "trailing_stop_pct")
            if current_value is not None:
                candidates.append(
                    {
                        "candidate_id": f"{dominant_regime.lower()}_trailing_stop_pct_up",
                        "target_param": f"regimes.{dominant_regime}.exit.trailing_stop_pct",
                        "current_value": current_value,
                        "proposed_value": round(current_value + 0.005, 4),
                        "expected_effect": "TRAILING_STOP 이후 추가 상승 구간의 조기 청산 완화",
                        "rationale": (
                            f"TRAILING_STOP avg_post_24h_pct={float(trailing['avg_post_24h_pct']):.2f}% "
                            "로 추가 상승 여지가 관측됨"
                        ),
                        "approval_tier": approval_tier,
                    }
                )

        take_profit = by_reason.get("TAKE_PROFIT", {})
        if take_profit.get("avg_post_4h_pct") is not None and float(take_profit["avg_post_4h_pct"]) > 2.0:
            current_value = self._regime_exit_value(dominant_regime, "take_profit_pct")
            if current_value is not None:
                candidates.append(
                    {
                        "candidate_id": f"{dominant_regime.lower()}_take_profit_pct_up",
                        "target_param": f"regimes.{dominant_regime}.exit.take_profit_pct",
                        "current_value": current_value,
                        "proposed_value": round(current_value + 0.005, 4),
                        "expected_effect": "익절 이후 추가 상승을 일부 더 흡수",
                        "rationale": (
                            f"TAKE_PROFIT avg_post_4h_pct={float(take_profit['avg_post_4h_pct']):.2f}% "
                            "로 조기 익절 가능성이 관측됨"
                        ),
                        "approval_tier": approval_tier,
                    }
                )

        stop_loss = by_reason.get("STOP_LOSS", {})
        if stop_loss.get("avg_post_4h_pct") is not None and float(stop_loss["avg_post_4h_pct"]) > 1.0:
            current_value = self._regime_exit_value(dominant_regime, "stop_loss_pct")
            if current_value is not None:
                candidates.append(
                    {
                        "candidate_id": f"{dominant_regime.lower()}_stop_loss_pct_relax",
                        "target_param": f"regimes.{dominant_regime}.exit.stop_loss_pct",
                        "current_value": current_value,
                        "proposed_value": round(current_value + 0.005, 4),
                        "expected_effect": "STOP_LOSS 직후 과도한 반등 구간의 불필요한 청산 완화",
                        "rationale": (
                            f"STOP_LOSS avg_post_4h_pct={float(stop_loss['avg_post_4h_pct']):.2f}% "
                            "로 직후 반등이 반복 관측됨"
                        ),
                        "approval_tier": approval_tier,
                    }
                )

        return candidates

    async def _collect_sell_sequence_metrics(self, days: int) -> _SellSequenceMetrics:
        """
        realized SELL 시퀀스만으로 평균 손익/Profit Factor/MDD proxy를 계산한다.

        왜 proxy인가:
        - 현재 운영 DB에는 포트폴리오 equity curve가 저장돼 있지 않다.
        - 따라서 SELL 순서 기반 누적 손익률의 최대 낙폭을 "승인 게이트용 보조 MDD"로 사용한다.
        """
        exit_analyzer = ExitPerformanceAnalyzer(self.session_factory)
        now = datetime.now(timezone.utc)
        start_ts = now - timedelta(days=days)

        async with self.session_factory() as session:
            sells = await exit_analyzer._fetch_sell_orders(session, start_ts, now)
            symbols = sorted({s.symbol for s in sells})
            buy_lots = await exit_analyzer._build_buy_lots(session, symbols=symbols, end_ts=now)

        pnl_values: List[float] = []
        cumulative = 0.0
        peak = 0.0
        max_drawdown = 0.0
        gross_profit = 0.0
        gross_loss_abs = 0.0

        for order in sells:
            price = exit_analyzer._to_decimal(order.price)
            qty = exit_analyzer._to_decimal(order.quantity)
            if price is None or qty is None or qty <= 0:
                continue

            signal_info = order.signal_info if isinstance(order.signal_info, dict) else {}
            entry_avg = None
            if signal_info:
                entry_avg = exit_analyzer._to_decimal(signal_info.get("entry_avg_price"))
            if entry_avg is None:
                entry_avg, _ = exit_analyzer._consume_entry(buy_lots, order.symbol, qty)
            if entry_avg is None or entry_avg <= 0:
                continue

            pnl_pct = float((price - entry_avg) / entry_avg * Decimal("100"))
            pnl_values.append(pnl_pct)
            cumulative += pnl_pct
            peak = max(peak, cumulative)
            max_drawdown = max(max_drawdown, peak - cumulative)
            if pnl_pct >= 0:
                gross_profit += pnl_pct
            else:
                gross_loss_abs += abs(pnl_pct)

        avg_pnl_pct = round(sum(pnl_values) / len(pnl_values), 4) if pnl_values else None
        profit_factor = round(gross_profit / gross_loss_abs, 4) if gross_loss_abs > 0 else None
        max_drawdown_pct = round(max_drawdown, 4) if pnl_values else None
        return _SellSequenceMetrics(
            total_sells=len(pnl_values),
            avg_realized_pnl_pct=avg_pnl_pct,
            profit_factor=profit_factor,
            max_drawdown_pct=max_drawdown_pct,
        )

    async def _collect_ai_decision_metrics(self, days: int) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        current_start = now - timedelta(days=days)
        previous_start = current_start - timedelta(days=days)

        async with self.session_factory() as session:
            current_stmt = select(AgentDecision.decision, AgentDecision.reasoning).where(
                AgentDecision.created_at >= current_start,
                AgentDecision.created_at <= now,
            )
            previous_stmt = select(AgentDecision.decision).where(
                AgentDecision.created_at >= previous_start,
                AgentDecision.created_at < current_start,
            )
            current_rows = (await session.execute(current_stmt)).all()
            previous_rows = (await session.execute(previous_stmt)).all()

        total = len(current_rows)
        reject_count = 0
        parse_fail_count = 0
        timeout_count = 0
        for decision, reasoning in current_rows:
            if str(decision).upper() == "REJECT":
                reject_count += 1
            reason_text = str(reasoning or "")
            if reason_text.startswith("분석가 출력 검증 실패:"):
                parse_fail_count += 1
            if "timed out" in reason_text.lower():
                timeout_count += 1

        previous_total = len(previous_rows)
        previous_reject_count = sum(1 for (decision,) in previous_rows if str(decision).upper() == "REJECT")
        current_reject_rate = self._safe_ratio(reject_count, total)
        previous_reject_rate = self._safe_ratio(previous_reject_count, previous_total)

        return {
            "total": total,
            "reject_count": reject_count,
            "parse_fail_count": parse_fail_count,
            "timeout_count": timeout_count,
            "reject_rate_pct": current_reject_rate,
            "reject_rate_delta_pct": None
            if current_reject_rate is None or previous_reject_rate is None
            else round(current_reject_rate - previous_reject_rate, 4),
        }

    async def _collect_llm_cost_metrics(self, days: int) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        current_start = now - timedelta(days=days)
        previous_start = current_start - timedelta(days=days)

        async with self.session_factory() as session:
            current_cost_stmt = select(func.coalesce(func.sum(LlmUsageEvent.estimated_cost_usd), 0)).where(
                LlmUsageEvent.created_at >= current_start,
                LlmUsageEvent.created_at <= now,
            )
            previous_cost_stmt = select(func.coalesce(func.sum(LlmUsageEvent.estimated_cost_usd), 0)).where(
                LlmUsageEvent.created_at >= previous_start,
                LlmUsageEvent.created_at < current_start,
            )
            snapshot_stmt = select(func.count()).select_from(LlmProviderCostSnapshot).where(
                LlmProviderCostSnapshot.created_at >= current_start,
                LlmProviderCostSnapshot.created_at <= now,
            )

            current_cost = float((await session.execute(current_cost_stmt)).scalar() or 0)
            previous_cost = float((await session.execute(previous_cost_stmt)).scalar() or 0)
            snapshot_count = int((await session.execute(snapshot_stmt)).scalar() or 0)

        return {
            "cost_usd": round(current_cost, 6),
            "cost_delta_pct": self._safe_pct_delta(current_cost, previous_cost),
            "provider_snapshot_count": snapshot_count,
        }

    def _build_hold_reasons(
        self,
        approval_tier: str,
        ai_metrics: Dict[str, Any],
        cost_metrics: Dict[str, Any],
        funnel_summary: Dict[str, Any],
        sell_samples: int,
    ) -> List[str]:
        reasons: List[str] = []
        if sell_samples < 12:
            reasons.append(f"SELL 표본 부족: {sell_samples}건 (검토 최소 12건 필요)")
        if ai_metrics.get("total", 0) < 20:
            reasons.append(
                f"AI decision 표본 부족: {ai_metrics.get('total', 0)}건 (최소 20건 필요)"
            )
        if cost_metrics.get("provider_snapshot_count", 0) <= 0:
            reasons.append("provider cost snapshot 누락: 비용 reconciliation 보류")
        bull_rule_pass = self._stage_count(funnel_summary, "BULL", "rule_pass")
        if bull_rule_pass < 5:
            reasons.append(f"BULL rule_pass 부족: {bull_rule_pass}건 (최소 5건 필요)")
        return reasons

    def _build_discard_reasons(
        self,
        sell_metrics: _SellSequenceMetrics,
        ai_metrics: Dict[str, Any],
        cost_metrics: Dict[str, Any],
    ) -> List[str]:
        reasons: List[str] = []
        if sell_metrics.avg_realized_pnl_pct is not None and sell_metrics.avg_realized_pnl_pct <= 0:
            reasons.append("평균 실현 손익률이 0 이하")
        if sell_metrics.profit_factor is not None and sell_metrics.profit_factor < 1.0:
            reasons.append("Profit Factor가 1.0 미만")
        if ai_metrics.get("reject_rate_delta_pct") is not None and ai_metrics["reject_rate_delta_pct"] > 10.0:
            reasons.append("AI reject rate 악화가 +10%p 초과")
        if cost_metrics.get("cost_delta_pct") is not None and cost_metrics["cost_delta_pct"] > 20.0:
            reasons.append("LLM 비용 증가율이 +20% 초과")
        return reasons

    async def build_feedback_payload(
        self,
        *,
        report_days: int = 7,
        approval_days: int = 14,
        fallback_days: int = 30,
    ) -> Dict[str, Any]:
        exit_analyzer = ExitPerformanceAnalyzer(self.session_factory)
        weekly_exit_summary = await exit_analyzer.summarize_period(days=report_days)

        approval_window_days = approval_days
        approval_exit_summary = await exit_analyzer.summarize_period(days=approval_days)
        if approval_exit_summary.get("total_sells", 0) < 12 and fallback_days > approval_days:
            approval_window_days = fallback_days
            approval_exit_summary = await exit_analyzer.summarize_period(days=fallback_days)

        funnel_analyzer = RuleFunnelAnalyzer(self.session_factory)
        approval_funnel_summary = await funnel_analyzer.summarize_period(days=approval_window_days)
        funnel_suggestions = RuleFunnelAnalyzer.generate_review_suggestions_from_summary(
            approval_funnel_summary,
            target_regime="BULL",
            min_rule_pass=5,
        )

        sell_metrics = await self._collect_sell_sequence_metrics(approval_window_days)
        ai_metrics = await self._collect_ai_decision_metrics(approval_window_days)
        cost_metrics = await self._collect_llm_cost_metrics(approval_window_days)

        approval_tier = self.determine_approval_tier(int(approval_exit_summary.get("total_sells", 0) or 0))
        hold_reasons = self._build_hold_reasons(
            approval_tier,
            ai_metrics,
            cost_metrics,
            approval_funnel_summary,
            int(approval_exit_summary.get("total_sells", 0) or 0),
        )
        candidate_changes = self._build_candidate_changes(
            approval_exit_summary,
            approval_funnel_summary,
            approval_tier,
        )
        discard_reasons = self._build_discard_reasons(sell_metrics, ai_metrics, cost_metrics)
        gate_result = self.determine_gate_result(
            approval_tier,
            hold_reasons,
            discard_reasons,
            candidate_changes,
        )

        return {
            "window": {
                "report_days": report_days,
                "approval_days": approval_window_days,
                "period_start": approval_exit_summary.get("period_start"),
                "period_end": approval_exit_summary.get("period_end"),
            },
            "readiness": {
                "sell_samples": int(approval_exit_summary.get("total_sells", 0) or 0),
                "ai_decisions": int(ai_metrics.get("total", 0) or 0),
                "bull_rule_pass": self._stage_count(approval_funnel_summary, "BULL", "rule_pass"),
                "approval_tier": approval_tier,
                "eligible_for_change": approval_tier in {"reviewable", "strong_approval"} and not discard_reasons,
                "hold_reasons": hold_reasons,
                "discard_reasons": discard_reasons,
            },
            "scoreboard": {
                "avg_realized_pnl_pct": sell_metrics.avg_realized_pnl_pct,
                "profit_factor": sell_metrics.profit_factor,
                "max_drawdown_pct": sell_metrics.max_drawdown_pct,
                "ai_reject_rate_pct": ai_metrics.get("reject_rate_pct"),
                "ai_reject_rate_delta_pct": ai_metrics.get("reject_rate_delta_pct"),
                "llm_cost_usd": cost_metrics.get("cost_usd"),
                "llm_cost_delta_pct": cost_metrics.get("cost_delta_pct"),
            },
            "weekly_exit_summary": weekly_exit_summary,
            "rule_funnel": approval_funnel_summary,
            "bottlenecks": funnel_suggestions,
            "candidate_changes": candidate_changes,
            "gate_result": gate_result,
            "evidence": [
                f"config_hash={self._strategy_config_hash()}",
                f"approval_window_days={approval_window_days}",
                f"sell_samples={approval_exit_summary.get('total_sells', 0)}",
                f"ai_decisions={ai_metrics.get('total', 0)}",
                f"provider_snapshot_count={cost_metrics.get('provider_snapshot_count', 0)}",
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
