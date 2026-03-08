from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.common.models import RuleFunnelEvent


def _normalize_regime(regime: Optional[str]) -> str:
    value = (regime or "UNKNOWN").strip().upper()
    return value or "UNKNOWN"


def derive_rule_funnel_reason_code(stage: str, reason: Optional[str]) -> str:
    """
    사람이 읽는 상세 reason은 그대로 보존하고,
    리포트/주간 비교에는 집계 가능한 짧은 reason_code를 함께 저장한다.

    문자열 패턴은 운영 중 문구가 조금씩 달라져도 큰 버킷이 유지되도록
    prefix/핵심 키워드 기준으로만 분류한다.
    """
    text = (reason or "").strip()
    lower = text.lower()

    if stage == "rule_pass":
        return "entry_signal_detected"

    if stage == "risk_reject":
        if "노출 한도" in text or "exposure" in lower:
            return "exposure_cap"
        if "가용 현금 부족" in text or "insufficient balance" in lower:
            return "cash_cap"
        if "주문 가능 금액이 0 이하" in text:
            return "zero_order_amount"
        if "동시 보유 포지션" in text:
            return "max_positions"
        if "중복 진입 금지" in text or "이미 포지션 보유" in text:
            return "duplicate_position"
        if "일일 최대 신규 진입" in text:
            return "daily_buy_limit"
        if "쿨다운" in text:
            return "risk_cooldown"
        return "risk_other"

    if stage == "ai_prefilter_reject":
        if "AI 컨텍스트 부족" in text:
            return "insufficient_context"
        if "falling knife pre-filter" in lower:
            return "falling_knife"
        if "volume recovery pre-filter" in lower:
            return "weak_volume_recovery"
        return "prefilter_other"

    if stage == "ai_guardrail_block":
        if "global ai block active" in lower:
            return "global_block"
        if "symbol ai cooldown active" in lower:
            return "symbol_cooldown"
        if "hourly ai budget exhausted" in lower:
            return "hourly_budget"
        if "daily ai budget exhausted" in lower:
            return "daily_budget"
        return "guardrail_other"

    if stage == "ai_confirm":
        return "approved"

    if stage == "ai_reject":
        if "분석가 출력 검증 실패" in text:
            return "analyst_validation_error"
        if "timed out" in lower:
            return "timeout"
        if "[risk warning]" in lower:
            return "guardian_warning"
        if "boundary" in lower:
            return "boundary_violation"
        return "ai_reject_other"

    return "unknown"


def record_rule_funnel_event(
    session: AsyncSession,
    *,
    symbol: str,
    regime: Optional[str],
    stage: str,
    result: str,
    reason: Optional[str],
    strategy_name: Optional[str] = None,
) -> None:
    """
    퍼널 이벤트 기록은 soft side-effect여야 하므로 호출부에서 주문 흐름을 바꾸지 않는다.
    세션에 add만 수행하고 실제 commit은 기존 트랜잭션 경계에 맡긴다.
    """
    try:
        session.add(
            RuleFunnelEvent(
                symbol=symbol,
                strategy_name=strategy_name,
                regime=_normalize_regime(regime),
                stage=stage,
                result=result,
                reason_code=derive_rule_funnel_reason_code(stage, reason),
                reason=reason,
            )
        )
    except Exception as exc:
        # 퍼널 계측 실패가 주문/판정 흐름을 멈추면 관측 기능이 본 기능을 역전한다.
        # 따라서 여기서는 soft-fail로 남기고 호출부 흐름은 계속 진행한다.
        print(f"[!] Failed to record rule funnel event: {exc}")
