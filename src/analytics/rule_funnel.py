from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import func, select

from src.common.models import RuleFunnelEvent


STAGE_ORDER = [
    "rule_pass",
    "risk_reject",
    "ai_prefilter_reject",
    "ai_guardrail_block",
    "ai_confirm",
    "ai_reject",
]


class RuleFunnelAnalyzer:
    """
    레짐별 Rule/Risk/AI 퍼널 이벤트를 집계해 주간 운영 리포트에 제공한다.
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory

    @staticmethod
    def _empty_stage_bucket() -> Dict[str, Any]:
        return {"count": 0, "unique_symbols": 0}

    @staticmethod
    def _stage_count(summary: Dict[str, Any], regime: str, stage: str) -> int:
        return int(
            summary.get("by_regime", {})
            .get(regime, {})
            .get(stage, {})
            .get("count", 0)
        )

    @staticmethod
    def _safe_ratio(numerator: int, denominator: int) -> float | None:
        if denominator <= 0:
            return None
        return round(numerator / denominator, 4)

    async def summarize_period(self, days: int = 7) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        start_ts = now - timedelta(days=days)

        by_regime: Dict[str, Dict[str, Dict[str, Any]]] = {}
        totals_by_stage: Dict[str, Dict[str, Any]] = {
            stage: self._empty_stage_bucket() for stage in STAGE_ORDER
        }
        top_reasons: List[Dict[str, Any]] = []

        async with self.session_factory() as session:
            counts_stmt = (
                select(
                    func.coalesce(RuleFunnelEvent.regime, "UNKNOWN").label("regime"),
                    RuleFunnelEvent.stage,
                    func.count().label("count"),
                    func.count(func.distinct(RuleFunnelEvent.symbol)).label("unique_symbols"),
                )
                .where(
                    RuleFunnelEvent.created_at >= start_ts,
                    RuleFunnelEvent.created_at <= now,
                )
                .group_by("regime", RuleFunnelEvent.stage)
            )
            count_rows = (await session.execute(counts_stmt)).all()

            stage_totals_stmt = (
                select(
                    RuleFunnelEvent.stage,
                    func.count().label("count"),
                    func.count(func.distinct(RuleFunnelEvent.symbol)).label("unique_symbols"),
                )
                .where(
                    RuleFunnelEvent.created_at >= start_ts,
                    RuleFunnelEvent.created_at <= now,
                )
                .group_by(RuleFunnelEvent.stage)
            )
            stage_total_rows = (await session.execute(stage_totals_stmt)).all()

            reasons_stmt = (
                select(
                    func.coalesce(RuleFunnelEvent.regime, "UNKNOWN").label("regime"),
                    RuleFunnelEvent.stage,
                    func.coalesce(RuleFunnelEvent.reason_code, "unknown").label("reason_code"),
                    func.count().label("count"),
                )
                .where(
                    RuleFunnelEvent.created_at >= start_ts,
                    RuleFunnelEvent.created_at <= now,
                )
                .group_by("regime", RuleFunnelEvent.stage, "reason_code")
                .order_by(func.count().desc(), "regime", RuleFunnelEvent.stage, "reason_code")
                .limit(12)
            )
            reason_rows = (await session.execute(reasons_stmt)).all()

        for row in count_rows:
            regime = row.regime or "UNKNOWN"
            stage = row.stage
            if stage not in STAGE_ORDER:
                continue
            regime_bucket = by_regime.setdefault(
                regime,
                {name: self._empty_stage_bucket() for name in STAGE_ORDER},
            )
            regime_bucket[stage] = {
                "count": int(row.count or 0),
                "unique_symbols": int(row.unique_symbols or 0),
            }

        for row in stage_total_rows:
            stage = row.stage
            if stage not in STAGE_ORDER:
                continue
            totals_by_stage[stage] = {
                "count": int(row.count or 0),
                "unique_symbols": int(row.unique_symbols or 0),
            }

        for row in reason_rows:
            top_reasons.append(
                {
                    "regime": row.regime or "UNKNOWN",
                    "stage": row.stage,
                    "reason_code": row.reason_code or "unknown",
                    "count": int(row.count or 0),
                }
            )

        ratios_by_regime: Dict[str, Dict[str, float | None]] = {}
        for regime, regime_bucket in by_regime.items():
            rule_pass = int(regime_bucket["rule_pass"]["count"])
            ratios_by_regime[regime] = {
                "risk_reject_per_rule_pass": self._safe_ratio(
                    int(regime_bucket["risk_reject"]["count"]), rule_pass
                ),
                "ai_prefilter_reject_per_rule_pass": self._safe_ratio(
                    int(regime_bucket["ai_prefilter_reject"]["count"]), rule_pass
                ),
                "ai_guardrail_block_per_rule_pass": self._safe_ratio(
                    int(regime_bucket["ai_guardrail_block"]["count"]), rule_pass
                ),
                "ai_confirm_per_rule_pass": self._safe_ratio(
                    int(regime_bucket["ai_confirm"]["count"]), rule_pass
                ),
                "ai_reject_per_rule_pass": self._safe_ratio(
                    int(regime_bucket["ai_reject"]["count"]), rule_pass
                ),
            }

        return {
            "period_days": days,
            "period_start": start_ts.isoformat(),
            "period_end": now.isoformat(),
            "by_regime": by_regime,
            "totals_by_stage": totals_by_stage,
            "ratios_by_regime": ratios_by_regime,
            "top_reasons": top_reasons,
        }

    @staticmethod
    def generate_review_suggestions_from_summary(
        summary: Dict[str, Any],
        *,
        target_regime: str = "BULL",
        min_rule_pass: int = 5,
    ) -> List[str]:
        """
        퍼널 병목을 빠르게 해석하기 위한 순수 함수.
        자동 수정이 아니라 "자동 제안"만 생성한다.
        """
        target_regime = (target_regime or "BULL").upper()
        rule_pass = RuleFunnelAnalyzer._stage_count(summary, target_regime, "rule_pass")
        if rule_pass < min_rule_pass:
            return [
                (
                    f"{target_regime} 퍼널 데이터 부족: rule_pass {rule_pass}건 "
                    f"(최소 {min_rule_pass}건 필요)"
                )
            ]

        risk_reject = RuleFunnelAnalyzer._stage_count(summary, target_regime, "risk_reject")
        prefilter_reject = RuleFunnelAnalyzer._stage_count(summary, target_regime, "ai_prefilter_reject")
        guardrail_block = RuleFunnelAnalyzer._stage_count(summary, target_regime, "ai_guardrail_block")
        ai_confirm = RuleFunnelAnalyzer._stage_count(summary, target_regime, "ai_confirm")
        ai_reject = RuleFunnelAnalyzer._stage_count(summary, target_regime, "ai_reject")

        suggestions: List[str] = []

        if RuleFunnelAnalyzer._safe_ratio(risk_reject, rule_pass) and (risk_reject / rule_pass) >= 0.5:
            suggestions.append(
                f"{target_regime}에서 Risk reject 비중이 높음: {risk_reject}/{rule_pass}. "
                "노출 한도/현금/중복 진입 제약이 병목인지 점검 필요"
            )

        if RuleFunnelAnalyzer._safe_ratio(prefilter_reject, rule_pass) and (prefilter_reject / rule_pass) >= 0.4:
            suggestions.append(
                f"{target_regime}에서 AI prefilter reject 비중이 높음: {prefilter_reject}/{rule_pass}. "
                "컨텍스트 부족 또는 prefilter 임계값 과민 여부 점검 필요"
            )

        if RuleFunnelAnalyzer._safe_ratio(guardrail_block, rule_pass) and (guardrail_block / rule_pass) >= 0.3:
            suggestions.append(
                f"{target_regime}에서 AI guardrail block 비중이 높음: {guardrail_block}/{rule_pass}. "
                "쿨다운/호출 상한/글로벌 block 상태 확인 필요"
            )

        if ai_reject > ai_confirm:
            suggestions.append(
                f"{target_regime}에서 AI reject가 confirm보다 많음: reject={ai_reject}, confirm={ai_confirm}. "
                "Analyst/Guardian rejection reason 상위 코드를 우선 검토"
            )

        sideways_rule_pass = RuleFunnelAnalyzer._stage_count(summary, "SIDEWAYS", "rule_pass")
        sideways_confirm = RuleFunnelAnalyzer._stage_count(summary, "SIDEWAYS", "ai_confirm")
        bull_confirm_rate = RuleFunnelAnalyzer._safe_ratio(ai_confirm, rule_pass)
        sideways_confirm_rate = RuleFunnelAnalyzer._safe_ratio(sideways_confirm, sideways_rule_pass)
        if (
            bull_confirm_rate is not None
            and sideways_confirm_rate is not None
            and (sideways_confirm_rate - bull_confirm_rate) >= 0.15
        ):
            suggestions.append(
                f"{target_regime} confirm/rule_pass 비율({bull_confirm_rate:.2f})이 "
                f"SIDEWAYS({sideways_confirm_rate:.2f})보다 낮음. "
                "레짐별 조건/guardrail 차이를 함께 비교 필요"
            )

        if not suggestions:
            suggestions.append(
                f"{target_regime} 퍼널 기준 뚜렷한 단일 병목은 아직 보이지 않음. "
                "주간 추세 비교를 유지"
            )
        return suggestions
