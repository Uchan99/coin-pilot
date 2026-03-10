import time
from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from src.agents.state import AgentState
from src.agents.structs import AnalystDecision
from src.agents.prompts import ANALYST_SYSTEM_PROMPT, get_analyst_prompt
from src.agents.factory import get_analyst_llm
from src.common.llm_usage import (
    UsageCaptureCallback,
    build_usage_request_id,
    estimate_cost_usd,
    log_llm_usage_event,
)

RULE_REVALIDATION_TERM_MAP = {
    # canonical: 감지 키워드 목록
    "rsi": ("rsi", "rsi(14)", "rsi(7)"),
    "ma20": ("ma20", "ma(20)", "moving average", "이동평균"),
    "volume": ("거래량", "volume ratio", "vol_ratio", "볼륨"),
    "bollinger": ("볼린저", "bb 하단", "bb_lower", "볼린저밴드"),
}


def detect_rule_revalidation_terms(reasoning: str) -> List[str]:
    """
    reasoning에 포함된 Rule Engine 재판단 흔적 키워드를 canonical term 목록으로 반환합니다.

    왜 필요한가:
    - 기존 bool 감지만으로는 어떤 항목이 경계 위반을 유발했는지 운영자가 알기 어렵습니다.
    - audit 모드에서는 '차단'보다 '관측'이 중요하므로, 탐지 근거(term) 기록이 필요합니다.
    """
    if not reasoning:
        return []
    normalized = reasoning.lower()
    matched: List[str] = []
    for canonical, aliases in RULE_REVALIDATION_TERM_MAP.items():
        if any(alias in normalized for alias in aliases):
            matched.append(canonical)
    return matched


def contains_rule_revalidation_reasoning(reasoning: str) -> bool:
    """
    Analyst가 Rule Engine 검증 항목(RSI/MA/거래량/BB)을 다시 판단했는지 탐지합니다.
    """
    return len(detect_rule_revalidation_terms(reasoning)) > 0


def build_rule_boundary_audit_note(
    original_reasoning: str,
    matched_terms: List[str],
    preview_len: int = 220,
) -> str:
    """
    Rule boundary 위반을 차단하지 않고 기록(audit)만 남길 때 사용할 요약 노트를 생성합니다.
    """
    terms = ",".join(matched_terms) if matched_terms else "unknown"
    raw = (original_reasoning or "").strip()
    preview = raw if len(raw) <= preview_len else f"{raw[:preview_len].rstrip()}...(후략)"
    if not preview:
        preview = "원본 reasoning이 비어 있어 preview를 남기지 못했습니다."
    return (
        f"[BoundaryAudit] Rule Engine 재판단 흔적 감지(terms={terms}). "
        f"정책상 차단하지 않고 감사 로그로만 기록합니다. preview={preview}"
    )


def build_analyst_rag_reference_block(rag_context: Optional[Dict[str, Any]]) -> str:
    """
    선택적 RAG 컨텍스트를 Analyst 프롬프트에 안전하게 삽입하기 위한 문자열 블록을 생성합니다.

    왜 별도 함수로 분리하는가:
    - RAG가 비활성인 기본 경로와 활성인 실험 경로를 같은 PromptTemplate에서 처리해야 합니다.
    - 전략 문서/사례 요약이 비어 있을 때도 프롬프트 형식이 깨지지 않도록 일관된 문자열을 반환해야 합니다.
    """
    if not isinstance(rag_context, dict):
        return ""

    raw_text = str(rag_context.get("text") or "").strip()
    source_summary = rag_context.get("source_summary") or []
    if not raw_text:
        return ""

    summary_text = ", ".join(str(item).strip() for item in source_summary if str(item).strip())
    prefix = "[추가 참고: 전략/과거사례 RAG]"
    if summary_text:
        prefix += f" ({summary_text})"
    # Analyst는 이미 Rule Engine을 통과한 후보를 기술적으로 검증하는 단계다.
    # 따라서 RSI/거래량/MA/BB 임계치 자체를 다시 심판하는 순간
    # RAG의 정적 규칙이 프롬프트 앞부분에서 과도하게 앵커링되어
    # valid 후보를 일괄 REJECT하는 drift가 생길 수 있다.
    boundary_guard = (
        "[RAG 사용 경계]\n"
        "- 아래 참고자료는 Rule Engine을 뒤집기 위한 근거가 아니라, 유사 사례와 캔들 구조 해석의 보조 자료다.\n"
        "- RSI, 거래량, MA, 볼린저밴드 임계치를 다시 판정하거나 규칙 자체를 더 엄격하게 재해석하지 말 것.\n"
        "- 직전 2~6개 캔들의 꼬리 구조, 몸통 강도, 반등/하락 지속성, 변동성 이상 징후만 기술적으로 검토할 것."
    )
    return f"\n\n{prefix}\n{boundary_guard}\n\n{raw_text}"


def sanitize_market_context_for_analyst(
    market_context: List[Dict[str, Any]], limit: int = 24
) -> List[Dict[str, Any]]:
    """
    Analyst 입력용 컨텍스트를 OHLC 중심으로 축소합니다.
    거래량 기반 재검증 유도를 줄이기 위해 volume 필드는 전달하지 않습니다.
    """
    if not isinstance(market_context, list):
        return []

    sanitized: List[Dict[str, Any]] = []
    for candle in market_context[-max(1, int(limit)):]:
        if not isinstance(candle, dict):
            continue
        sanitized.append(
            {
                "timestamp": candle.get("timestamp"),
                "open": candle.get("open"),
                "high": candle.get("high"),
                "low": candle.get("low"),
                "close": candle.get("close"),
            }
        )
    return sanitized


def extract_candle_pattern_features(market_context: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    최근 1시간봉 OHLC에서 캔들 패턴 전용 요약 피처를 생성합니다.
    이 피처는 Rule Engine 조건(RSI/거래량 임계치)과 분리된 정보만 제공하기 위한 목적입니다.
    """
    default = {
        "pattern_direction": "FLAT",
        "net_change_pct_6h": 0.0,
        "bearish_streak_6h": 0,
        "bullish_streak_6h": 0,
        "last_body_to_range_ratio": 0.0,
        "last_upper_wick_ratio": 0.0,
        "last_lower_wick_ratio": 0.0,
        "range_expansion_ratio_6h": 1.0,
    }
    if not market_context:
        return default

    closes: List[float] = []
    opens: List[float] = []
    highs: List[float] = []
    lows: List[float] = []
    for candle in market_context[-6:]:
        try:
            opens.append(float(candle.get("open")))
            highs.append(float(candle.get("high")))
            lows.append(float(candle.get("low")))
            closes.append(float(candle.get("close")))
        except (TypeError, ValueError):
            continue

    if len(closes) < 2:
        return default

    first_close = closes[0]
    last_close = closes[-1]
    net_change_pct = ((last_close - first_close) / first_close * 100.0) if first_close > 0 else 0.0

    if net_change_pct > 0.2:
        direction = "UP"
    elif net_change_pct < -0.2:
        direction = "DOWN"
    else:
        direction = "FLAT"

    bearish_streak = 0
    bullish_streak = 0
    for idx in range(len(closes) - 1, -1, -1):
        if closes[idx] < opens[idx]:
            bearish_streak += 1
            if bullish_streak > 0:
                break
        elif closes[idx] > opens[idx]:
            bullish_streak += 1
            if bearish_streak > 0:
                break
        else:
            break

    last_open = opens[-1]
    last_high = highs[-1]
    last_low = lows[-1]
    last_close = closes[-1]
    last_range = max(last_high - last_low, 1e-9)
    last_body = abs(last_close - last_open)
    upper_wick = max(last_high - max(last_open, last_close), 0.0)
    lower_wick = max(min(last_open, last_close) - last_low, 0.0)

    prev_ranges = [max(h - l, 1e-9) for h, l in zip(highs[:-1], lows[:-1])]
    prev_range_avg = (sum(prev_ranges) / len(prev_ranges)) if prev_ranges else last_range
    range_expansion = last_range / max(prev_range_avg, 1e-9)

    return {
        "pattern_direction": direction,
        "net_change_pct_6h": round(net_change_pct, 4),
        "bearish_streak_6h": bearish_streak,
        "bullish_streak_6h": bullish_streak,
        "last_body_to_range_ratio": round(last_body / last_range, 4),
        "last_upper_wick_ratio": round(upper_wick / last_range, 4),
        "last_lower_wick_ratio": round(lower_wick / last_range, 4),
        "range_expansion_ratio_6h": round(range_expansion, 4),
    }


async def market_analyst_node(state: AgentState) -> Dict[str, Any]:
    """시장 분석가 노드: 지표 기반 진입 타당성 검토"""
    
    llm = get_analyst_llm(state.get("llm_route"))
    structured_llm = llm.with_structured_output(AnalystDecision)

    sanitized_context = sanitize_market_context_for_analyst(
        state.get("market_context", []), limit=24
    )
    pattern_features = extract_candle_pattern_features(sanitized_context)
    prompt_indicators = {**state.get("indicators", {}), **pattern_features}
    rag_reference_block = build_analyst_rag_reference_block(state.get("rag_context"))

    prompt = ChatPromptTemplate.from_messages([
        ("system", ANALYST_SYSTEM_PROMPT),
        ("human", "{analyst_prompt}\n\n"
                  "[참고: Analyst 입력(OHLC + 패턴요약)]\n"
                  "- 심볼: {symbol}\n"
                  "- 패턴 요약 피처: {pattern_features}\n"
                  "- 최근 1시간봉 캔들(OHLC, 최대 24개): {market_context_ohlc}"
                  "{rag_reference_block}")
    ])
    
    chain = prompt | structured_llm

    base_prompt = get_analyst_prompt(prompt_indicators)
    result: AnalystDecision | None = None
    validation_error: Exception | None = None
    boundary_terms: List[str] = []
    boundary_violation = False
    latency_ms = 0
    estimated_cost = None
    usage_capture = UsageCaptureCallback()
    started_at = time.perf_counter()
    llm_route = state.get("llm_route") or {}
    provider = str(llm_route.get("provider") or "unknown")
    model = str(llm_route.get("model") or "unknown")
    replay_mode = bool(state.get("replay_mode"))
    rag_enabled = bool((state.get("rag_context") or {}).get("text"))
    route_name = "ai_decision_analyst_replay" if replay_mode else "ai_decision_analyst"

    try:
        invoke_payload = {
            "symbol": state["symbol"],
            "pattern_features": pattern_features,
            "market_context_ohlc": sanitized_context,
            "analyst_prompt": base_prompt,
            "rag_reference_block": rag_reference_block,
        }
        try:
            candidate: AnalystDecision = await chain.ainvoke(
                invoke_payload,
                config={"callbacks": [usage_capture]},
            )
        except TypeError:
            candidate = await chain.ainvoke(invoke_payload)
        result = candidate
        # 정책 전환(18-15): boundary는 차단하지 않고 audit 기록으로 남긴다.
        boundary_terms = detect_rule_revalidation_terms((candidate.reasoning or "").strip())
        boundary_violation = len(boundary_terms) > 0
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        estimated_cost = estimate_cost_usd(provider=provider, model=model, usage=usage_capture.usage)

        await log_llm_usage_event(
            route=route_name,
            feature="ai_decision",
            provider=provider,
            model=model,
            status="success",
            usage=usage_capture.usage,
            request_id=build_usage_request_id(route_name, provider, model),
            latency_ms=latency_ms,
            meta={
                "symbol": state.get("symbol"),
                "strategy_name": state.get("strategy_name"),
                "replay_mode": replay_mode,
                "rag_enabled": rag_enabled,
                "rag_source_summary": (state.get("rag_context") or {}).get("source_summary", []),
            },
        )
    except Exception as e:
        validation_error = e
        await log_llm_usage_event(
            route=route_name,
            feature="ai_decision",
            provider=provider,
            model=model,
            status="error",
            usage=usage_capture.usage,
            request_id=build_usage_request_id(route_name, provider, model),
            error_type=type(e).__name__,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            meta={
                "symbol": state.get("symbol"),
                "strategy_name": state.get("strategy_name"),
                "replay_mode": replay_mode,
                "rag_enabled": rag_enabled,
            },
        )

    if result is None:
        # Structured output 파싱 실패(예: reasoning 누락) 시 보수적 거절
        return {
            "analyst_decision": {
                "decision": "REJECT",
                "confidence": 0,
                "reasoning": f"분석가 출력 검증 실패: {str(validation_error)}",
                "boundary_violation": False,
                "boundary_terms": [],
            }
        }
    
    # 분석 결과 업데이트
    # V1.2 정책: confidence < 60 이면 강제 REJECT
    final_decision = result.decision
    final_reasoning = (result.reasoning or "").strip()
    if not final_reasoning:
        final_reasoning = (
            f"모델 출력에 분석 사유(reasoning)가 비어 있습니다 "
            f"(decision={result.decision}, confidence={result.confidence})."
        )
    
    if result.decision == "CONFIRM" and result.confidence < 60:
        final_decision = "REJECT"
        final_reasoning = f"[신뢰도 부족: {result.confidence}] {final_reasoning}"

    if boundary_violation:
        # 강제 REJECT는 하지 않되, 운영 관측을 위해 감사 노트를 reasoning에 부착한다.
        audit_note = build_rule_boundary_audit_note(final_reasoning, boundary_terms)
        final_reasoning = f"{final_reasoning}\n\n{audit_note}"
    
    return {
        "analyst_decision": {
            "decision": final_decision,
            "confidence": result.confidence,
            "reasoning": final_reasoning,
            "boundary_violation": boundary_violation,
            "boundary_terms": boundary_terms,
            "latency_ms": latency_ms,
            "estimated_cost_usd": float(estimated_cost) if estimated_cost is not None else None,
            "usage": {
                "input_tokens": usage_capture.usage.input_tokens,
                "output_tokens": usage_capture.usage.output_tokens,
                "total_tokens": usage_capture.usage.total_tokens,
            },
            "rag_enabled": rag_enabled,
            "rag_source_summary": (state.get("rag_context") or {}).get("source_summary", []),
        }
    }
