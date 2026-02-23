from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from src.agents.state import AgentState
from src.agents.structs import AnalystDecision
from src.agents.prompts import ANALYST_SYSTEM_PROMPT, get_analyst_prompt
from src.agents.factory import get_analyst_llm

RULE_REVALIDATION_TERMS = (
    "rsi",
    "ma20",
    "ma(20)",
    "moving average",
    "거래량",
    "volume ratio",
    "vol_ratio",
    "볼린저",
    "bb 하단",
    "bb_lower",
)


def contains_rule_revalidation_reasoning(reasoning: str) -> bool:
    """
    Analyst가 Rule Engine 검증 항목(RSI/MA/거래량/BB)을 다시 판단했는지 탐지합니다.
    """
    if not reasoning:
        return False
    normalized = reasoning.lower()
    return any(term in normalized for term in RULE_REVALIDATION_TERMS)


def build_rule_boundary_reject_reasoning(original_reasoning: str, max_len: int = 1400) -> str:
    """
    Rule boundary 위반으로 강제 REJECT 되더라도 운영자가 맥락을 볼 수 있게 상세 근거를 보존합니다.

    왜 필요한가:
    - 기존에는 고정 문구만 남아 디버깅/운영 판단이 어려웠습니다.
    - 차단 정책(REJECT)은 유지하면서, 사람이 읽는 설명 품질만 복구하는 것이 목적입니다.

    불변조건:
    - 항상 Rule boundary 위반 사실은 첫 문장에 명시합니다.
    - 원문 reasoning이 비어 있으면 대체 문구를 반환합니다.
    - 과도하게 긴 본문은 상한으로 잘라 Discord payload 길이 폭주를 방지합니다.
    """
    raw = (original_reasoning or "").strip()
    if not raw:
        return (
            "분석가 응답이 재시도 후에도 룰 경계를 위반해 보수적으로 REJECT 처리했습니다. "
            "다만 원본 상세 분석 근거가 비어 있어 추가 맥락을 제공할 수 없습니다."
        )

    trimmed = raw if len(raw) <= max_len else f"{raw[:max_len].rstrip()}...(후략)"
    return (
        "분석가 응답이 재시도 후에도 룰 경계를 위반해 보수적으로 REJECT 처리했습니다.\n\n"
        "[원본 분석 근거]\n"
        f"{trimmed}"
    )


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
    
    llm = get_analyst_llm()
    structured_llm = llm.with_structured_output(AnalystDecision)

    sanitized_context = sanitize_market_context_for_analyst(
        state.get("market_context", []), limit=24
    )
    pattern_features = extract_candle_pattern_features(sanitized_context)
    prompt_indicators = {**state.get("indicators", {}), **pattern_features}

    prompt = ChatPromptTemplate.from_messages([
        ("system", ANALYST_SYSTEM_PROMPT),
        ("human", "{analyst_prompt}\n\n"
                  "[참고: Analyst 입력(OHLC + 패턴요약)]\n"
                  "- 심볼: {symbol}\n"
                  "- 패턴 요약 피처: {pattern_features}\n"
                  "- 최근 1시간봉 캔들(OHLC, 최대 24개): {market_context_ohlc}")
    ])
    
    chain = prompt | structured_llm

    base_prompt = get_analyst_prompt(prompt_indicators)
    corrective_note = (
        "\n\n[재검토 지시]\n"
        "- 직전 응답에 Rule Engine 검증 항목(RSI/MA/거래량/볼린저) 재판단 흔적이 있었습니다.\n"
        "- 해당 항목은 다시 판단하지 말고, 캔들 패턴/추세 지속성/급격한 변동성 이상만 근거로 다시 작성하세요."
    )

    result: AnalystDecision | None = None
    validation_error: Exception | None = None
    for attempt in range(2):
        analyst_prompt = base_prompt if attempt == 0 else f"{base_prompt}{corrective_note}"
        try:
            candidate: AnalystDecision = await chain.ainvoke({
                "symbol": state["symbol"],
                "pattern_features": pattern_features,
                "market_context_ohlc": sanitized_context,
                "analyst_prompt": analyst_prompt,
            })
        except Exception as e:
            validation_error = e
            break

        # Rule Engine 검증 항목을 reasoning에서 다시 판단하면 1회 재시도 후 강제 REJECT 처리합니다.
        if contains_rule_revalidation_reasoning((candidate.reasoning or "").strip()):
            if attempt == 0:
                continue
            return {
                "analyst_decision": {
                    "decision": "REJECT",
                    "confidence": 0,
                    "reasoning": build_rule_boundary_reject_reasoning(candidate.reasoning),
                }
            }

        result = candidate
        break

    if result is None:
        # Structured output 파싱 실패(예: reasoning 누락) 시 보수적 거절
        return {
            "analyst_decision": {
                "decision": "REJECT",
                "confidence": 0,
                "reasoning": f"분석가 출력 검증 실패: {str(validation_error)}"
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
    
    return {
        "analyst_decision": {
            "decision": final_decision,
            "confidence": result.confidence,
            "reasoning": final_reasoning
        }
    }
