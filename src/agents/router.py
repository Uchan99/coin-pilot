import asyncio
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Literal, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from src.agents.factory import get_chat_llm, get_premium_review_llm
from src.agents.rag_agent import run_rag_agent
from src.agents.sql_agent import run_sql_agent
from src.agents.tools.market_outlook_tool import run_market_outlook_tool
from src.agents.tools.portfolio_tool import run_portfolio_tool
from src.agents.tools.risk_diagnosis_tool import run_risk_diagnosis_tool
from src.agents.tools.sell_timing_tool import run_sell_timing_tool
from src.agents.tools.strategy_policy_tool import run_strategy_policy_tool
from src.agents.tools.strategy_review_tool import run_strategy_review_tool
from src.common.async_utils import run_async_safely

SAFETY_DISCLAIMER = "이 답변은 참고용 분석이며 투자 권유가 아닙니다. 최종 결정은 본인 판단과 리스크 한도 기준으로 진행하세요."
SCENARIO_NOTE = "시장 예측은 단정할 수 없으며, 가능한 시나리오를 기준으로 해석해야 합니다."


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# Phase 5: 비용/안전 가드레일 런타임 설정
CHAT_SESSION_COOLDOWN_SECONDS = _env_float("CHAT_SESSION_COOLDOWN_SECONDS", 1.5)
CHAT_CACHE_TTL_SECONDS = _env_int("CHAT_CACHE_TTL_SECONDS", 300)
CHAT_CACHE_MAX_ENTRIES = _env_int("CHAT_CACHE_MAX_ENTRIES", 256)
CHAT_MAX_INPUT_CHARS = _env_int("CHAT_MAX_INPUT_CHARS", 600)
CHAT_MAX_OUTPUT_CHARS = _env_int("CHAT_MAX_OUTPUT_CHARS", 2200)
CHAT_ENABLE_PREMIUM_REVIEW = _env_bool("CHAT_ENABLE_PREMIUM_REVIEW", True)
CHAT_PREMIUM_REVIEW_MIN_QUERY_LEN = _env_int("CHAT_PREMIUM_REVIEW_MIN_QUERY_LEN", 28)
CHAT_PREMIUM_REVIEW_TIMEOUT_SEC = _env_float("CHAT_PREMIUM_REVIEW_TIMEOUT_SEC", 12.0)

# 고난도 전략 리뷰 승격 판단용 힌트 단어
PREMIUM_REVIEW_HINTS = (
    "장단점",
    "개선",
    "원인",
    "왜",
    "근거",
    "리스크",
    "성과",
    "패턴",
    "회고",
    "손실",
    "최적화",
    "포지션",
    "시나리오",
)

SCENARIO_REQUIRED_INTENTS = {
    "market_outlook",
    "strategy_policy",
    "strategy_review",
    "risk_diagnosis",
    "sell_timing_advice",
    "action_recommendation",
}

_runtime_guard_lock = threading.Lock()
_session_last_request_ts: dict[str, float] = {}
_response_cache: OrderedDict[tuple[str, str], tuple[float, str]] = OrderedDict()


class AgentState(TypedDict):
    """LangGraph 상태 정의: 메시지 기록, 최종 응답, 사용자 의도"""

    messages: list[BaseMessage]
    response: str
    intent: str


class IntentDecision(BaseModel):
    """LLM 구조적 출력(Structured Output)을 위한 Pydantic 모델"""

    intent: Literal[
        "db_query",
        "doc_search",
        "portfolio_status",
        "market_outlook",
        "strategy_policy",
        "strategy_review",
        "risk_diagnosis",
        "sell_timing_advice",
        "action_recommendation",
        "general_chat",
    ] = Field(
        ...,
        description=(
            "User intent classification. "
            "Use db_query for SQL-like data lookup, doc_search for policy/architecture docs, "
            "portfolio_status for asset/position summary, market_outlook for market interpretation, "
            "strategy_policy for rule explanation, strategy_review for trade performance coaching, "
            "risk_diagnosis for risk status check, sell_timing_advice for position exit timing guidance, "
            "action_recommendation for buy/entry/hold decision guidance, and general_chat otherwise."
        ),
    )


def _infer_symbol(message: str) -> str:
    lower = message.lower()
    aliases = {
        "krw-btc": "KRW-BTC",
        "btc": "KRW-BTC",
        "비트코인": "KRW-BTC",
        "bitcoin": "KRW-BTC",
        "krw-eth": "KRW-ETH",
        "eth": "KRW-ETH",
        "이더리움": "KRW-ETH",
        "ethereum": "KRW-ETH",
        "krw-xrp": "KRW-XRP",
        "xrp": "KRW-XRP",
        "리플": "KRW-XRP",
        "krw-sol": "KRW-SOL",
        "sol": "KRW-SOL",
        "솔라나": "KRW-SOL",
        "krw-doge": "KRW-DOGE",
        "doge": "KRW-DOGE",
        "도지": "KRW-DOGE",
    }
    for key, symbol in aliases.items():
        if key in lower:
            return symbol
    return "KRW-BTC"


def _format_krw(value: float) -> str:
    return f"{value:,.0f}원"


def _is_action_decision_query(text: str) -> bool:
    """매수/진입 여부를 묻는 판단형 질문인지 판정합니다."""
    action_terms = ["매수", "진입", "살까", "사도", "들어가", "홀드", "관망", "보유", "포지션"]
    decision_terms = [
        "좋",
        "안하는게",
        "해야",
        "해도",
        "할까",
        "맞",
        "괜찮",
        "어때",
        "지금",
        "현재 기준",
    ]
    return any(term in text for term in action_terms) and any(
        cue in text for cue in decision_terms
    )


def _classify_intent_fast_path(message: str) -> str | None:
    """키워드 기반 고속 분류. 명확한 경우에만 즉시 분기합니다."""
    text = message.lower()

    sell_timing_keywords = [
        "언제 매도",
        "언제 팔",
        "매도 타이밍",
        "익절 타이밍",
        "청산 타이밍",
        "매도하는게",
        "팔아야",
        "정리할까",
        "매도하는 게",
    ]
    strategy_policy_keywords = [
        "매도 전략",
        "청산 전략",
        "청산 규칙",
        "매도 규칙",
        "전략 규칙",
        "익절 규칙",
        "손절 규칙",
        "exit 전략",
    ]
    strategy_review_keywords = ["전략 장단점", "전략 리뷰", "성과 분석", "리뷰", "코칭", "개선안"]
    action_keywords = ["진입", "매수해도", "사도", "행동", "어떻게 할까", "추천"]
    risk_keywords = ["리스크", "위험", "주의", "손실", "위험요소", "경고"]
    market_keywords = ["시장", "전망", "모멘텀", "레짐", "분위기", "해석", "추세"]
    portfolio_keywords = ["잔고", "자산", "포트폴리오", "보유", "포지션", "평가액"]
    doc_keywords = ["규칙", "아키텍처", "왜", "어떻게", "정책", "설명", "문서"]
    sql_keywords = ["sql", "쿼리", "수익률", "거래내역", "price", "pnl", "balance", "count"]

    # 매도 타이밍/전략 설명은 사용자 기대가 뚜렷하므로 우선순위를 가장 높게 둡니다.
    if any(k in text for k in sell_timing_keywords):
        return "sell_timing_advice"

    if any(k in text for k in strategy_policy_keywords):
        return "strategy_policy"

    if (
        "전략" in text
        and any(k in text for k in ["어떻게", "뭐야", "설명", "알려", "정의"])
        and not any(k in text for k in strategy_review_keywords)
    ):
        return "strategy_policy"

    if any(k in text for k in strategy_review_keywords):
        return "strategy_review"

    if _is_action_decision_query(text):
        return "action_recommendation"

    if any(k in text for k in action_keywords):
        return "action_recommendation"
    if any(k in text for k in risk_keywords):
        return "risk_diagnosis"
    if any(k in text for k in market_keywords):
        return "market_outlook"
    if any(k in text for k in portfolio_keywords):
        return "portfolio_status"
    if any(k in text for k in doc_keywords):
        return "doc_search"
    if any(k in text for k in sql_keywords):
        return "db_query"

    return None


def _normalize_session_id(session_id: str | None) -> str:
    """세션 식별자가 비어있으면 공통 기본값으로 정규화합니다."""
    if not session_id:
        return "default"
    normalized = session_id.strip()
    return normalized if normalized else "default"


def _is_input_too_long(message: str) -> bool:
    return len(message) > max(1, CHAT_MAX_INPUT_CHARS)


def _clip_output_text(text: str) -> str:
    """출력 길이 예산을 넘으면 뒤를 잘라 응답 폭주를 방지합니다."""
    max_chars = max(200, CHAT_MAX_OUTPUT_CHARS)
    if len(text) <= max_chars:
        return text
    clipped = text[: max_chars - 40].rstrip()
    return f"{clipped}\n[응답 길이 제한으로 일부 내용이 생략되었습니다.]"


def _cleanup_cache_locked(now_ts: float) -> None:
    ttl = max(1, CHAT_CACHE_TTL_SECONDS)
    max_entries = max(1, CHAT_CACHE_MAX_ENTRIES)

    while _response_cache:
        oldest_key, (created_ts, _) = next(iter(_response_cache.items()))
        if now_ts - created_ts <= ttl:
            break
        _response_cache.pop(oldest_key, None)

    while len(_response_cache) > max_entries:
        _response_cache.popitem(last=False)


def _get_cached_response(session_id: str, message: str) -> str | None:
    now_ts = time.time()
    key = (session_id, message)
    with _runtime_guard_lock:
        _cleanup_cache_locked(now_ts)
        payload = _response_cache.get(key)
        if payload is None:
            return None
        created_ts, response = payload
        if now_ts - created_ts > max(1, CHAT_CACHE_TTL_SECONDS):
            _response_cache.pop(key, None)
            return None
        _response_cache.move_to_end(key)
        return response


def _set_cached_response(session_id: str, message: str, response: str) -> None:
    now_ts = time.time()
    key = (session_id, message)
    with _runtime_guard_lock:
        _cleanup_cache_locked(now_ts)
        _response_cache[key] = (now_ts, response)
        _response_cache.move_to_end(key)
        _cleanup_cache_locked(now_ts)


def _is_cooldown_blocked(session_id: str) -> tuple[bool, str]:
    """세션별 최소 요청 간격을 강제해 과도한 LLM 호출을 줄입니다."""
    now_ts = time.time()
    cooldown_sec = max(0.0, CHAT_SESSION_COOLDOWN_SECONDS)
    with _runtime_guard_lock:
        last_ts = _session_last_request_ts.get(session_id, 0.0)
        if cooldown_sec > 0 and (now_ts - last_ts) < cooldown_sec:
            remain = max(0.0, cooldown_sec - (now_ts - last_ts))
            return True, f"요청 간격이 너무 짧습니다. {remain:.1f}초 후 다시 시도해주세요."
        _session_last_request_ts[session_id] = now_ts
    return False, ""


def _ensure_safety_footer(response: str, intent: str) -> str:
    text = response.strip() if response else "응답을 생성하지 못했습니다."

    # 본문에 이미 포함된 안전 문구는 제거한 뒤, footer에 1회만 재삽입합니다.
    # 이렇게 하면 길이 제한이 걸려도 안전 문구가 잘리지 않고 항상 보존됩니다.
    text = text.replace(SAFETY_DISCLAIMER, "").replace(SCENARIO_NOTE, "").strip()
    footer_lines: list[str] = []

    if intent in SCENARIO_REQUIRED_INTENTS:
        footer_lines.append(SCENARIO_NOTE)
    footer_lines.append(SAFETY_DISCLAIMER)

    if not text:
        return "\n".join(footer_lines)

    footer = "\n".join(footer_lines)
    max_chars = max(200, CHAT_MAX_OUTPUT_CHARS)

    # 안전 고지문은 항상 보존해야 하므로 본문만 우선 축약합니다.
    if len(text) + 1 + len(footer) <= max_chars:
        return f"{text}\n{footer}"

    trunc_note = "[응답 길이 제한으로 일부 내용이 생략되었습니다.]"
    available = max(40, max_chars - len(footer) - len(trunc_note) - 2)
    body = text[:available].rstrip()
    return f"{body}\n{trunc_note}\n{footer}"


def _should_escalate_premium_review(query: str) -> bool:
    """
    고난도 전략 리뷰(원인 분석/개선안/근거 요청)만 상위 모델로 승격합니다.
    단순 \"전략 리뷰 해줘\" 같은 짧은 질의는 기본 모델/규칙 응답을 유지합니다.
    """
    if not CHAT_ENABLE_PREMIUM_REVIEW:
        return False

    text = query.strip().lower()
    if len(text) < max(1, CHAT_PREMIUM_REVIEW_MIN_QUERY_LEN):
        return False

    hint_count = sum(1 for keyword in PREMIUM_REVIEW_HINTS if keyword in text)
    return hint_count >= 2


async def _generate_premium_review_commentary(query: str, data: dict[str, Any]) -> str | None:
    """
    상위 모델 코멘트 생성은 실패 가능성을 전제로 하며,
    실패 시 기존 규칙 기반 리뷰를 그대로 반환하도록 설계합니다.
    """
    summary = data.get("summary", {})
    strengths = data.get("strengths", [])
    weaknesses = data.get("weaknesses", [])
    improvements = data.get("improvements", [])

    prompt = (
        "당신은 코인 자동매매 성과 리뷰 코치입니다.\n"
        "아래 데이터와 사용자 질문을 기반으로, 한국어로 짧고 실행 가능한 심화 코멘트를 작성하세요.\n"
        "형식:\n"
        "1) 핵심 진단(2문장)\n"
        "2) 실패 패턴 가설(최대 2개)\n"
        "3) 다음 1주 액션(최대 3개)\n"
        "주의: 단정적 예측 금지, 수치 근거를 활용, 투자 권유 문구는 쓰지 말 것.\n\n"
        f"[사용자 질문]\n{query}\n\n"
        f"[요약]\n{summary}\n\n"
        f"[강점]\n{strengths}\n\n"
        f"[약점]\n{weaknesses}\n\n"
        f"[개선안]\n{improvements}\n"
    )

    try:
        llm = get_premium_review_llm(temperature=0.1)
        response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=CHAT_PREMIUM_REVIEW_TIMEOUT_SEC)
    except Exception:
        return None

    content = getattr(response, "content", "")
    if isinstance(content, list):
        content = "\n".join(str(item) for item in content)
    text = str(content).strip() if content else str(response).strip()
    return text if text else None


def get_classifier_llm():
    """의도 분류를 위한 LLM 인스턴스를 생성하고 구조화 출력 모드로 설정합니다."""
    llm = get_chat_llm(temperature=0)
    return llm.with_structured_output(IntentDecision)


async def classifier_node(state: AgentState):
    """
    사용자 쿼리의 의도(Intent)를 분류하는 노드입니다.
    Fast Path(키워드)와 Slow Path(LLM)를 하이브리드로 사용합니다.
    """
    last_message = str(state["messages"][-1].content)

    fast_intent = _classify_intent_fast_path(last_message)
    if fast_intent:
        return {"intent": fast_intent}

    try:
        llm = get_classifier_llm()
        decision: IntentDecision = await llm.ainvoke(last_message)
        return {"intent": decision.intent}
    except Exception as exc:
        print(f"Router Error: {exc}")
        return {"intent": "general_chat"}


async def sql_node(state: AgentState):
    query = str(state["messages"][-1].content)
    response = await run_sql_agent(query)
    return {"response": response}


async def rag_node(state: AgentState):
    query = str(state["messages"][-1].content)
    response = await run_rag_agent(query)
    return {"response": response}


async def portfolio_node(state: AgentState):
    _ = state
    data = await asyncio.to_thread(run_portfolio_tool)

    lines = [
        f"총 평가액: {_format_krw(data['total_valuation_krw'])}",
        f"현금 잔고: {_format_krw(data['cash_krw'])}",
        f"보유 자산 평가액: {_format_krw(data['holdings_value_krw'])}",
    ]

    if data["holdings"]:
        lines.append("보유 포지션 요약:")
        for row in data["holdings"][:5]:
            pnl_pct = row["unrealized_pnl_pct"]
            pnl_text = "N/A" if pnl_pct is None else f"{pnl_pct:+.2f}%"
            lines.append(
                f"- {row['symbol']}: 평가 {_format_krw(row['valuation_krw'])}, 미실현 {pnl_text}"
            )
    else:
        lines.append("현재 보유 포지션이 없습니다.")

    risk = data["risk_snapshot"]
    lines.append(
        f"당일 리스크 상태: BUY {risk['buy_count']}회 / 총 {risk['trade_count']}회, 연속손실 {risk['consecutive_losses']}회"
    )

    return {"response": "\n".join(lines)}


async def market_outlook_node(state: AgentState):
    query = str(state["messages"][-1].content)
    symbol = _infer_symbol(query)
    data = await asyncio.to_thread(run_market_outlook_tool, symbol)

    if data["status"] != "OK":
        return {"response": f"{data['message']}\n{SAFETY_DISCLAIMER}"}

    lines = [
        f"{symbol} 시장 브리핑:",
        f"- 현재가: {_format_krw(data['current_price'])}",
        f"- 레짐: {data['regime']} (MA50-MA200 이격도 {data['regime_diff_pct']:+.2f}%)",
        f"- 단기 추세: {data['trend_signal']}",
    ]

    if data.get("rsi14") is not None:
        lines.append(f"- RSI(14): {data['rsi14']:.1f}")
    if data.get("momentum_1h_pct") is not None:
        lines.append(f"- 1시간 모멘텀: {data['momentum_1h_pct']:+.2f}%")
    if data.get("volatility_pct") is not None:
        lines.append(f"- 단기 변동성(추정): {data['volatility_pct']:.2f}%")

    if data.get("news_risk_score") is None:
        lines.append("- 뉴스 리스크 점수: 아직 수집/집계 데이터가 부족합니다.")
    else:
        lines.append(
            f"- 뉴스 리스크: {data['news_risk_level']} ({data['news_risk_score']:.1f})"
        )
        if data.get("news_summary"):
            lines.append(f"- 뉴스 요약: {data['news_summary']}")
    lines.append(SAFETY_DISCLAIMER)
    return {"response": "\n".join(lines)}


async def strategy_policy_node(state: AgentState):
    _ = state
    data = await asyncio.to_thread(run_strategy_policy_tool)

    lines = [
        f"현재 전략: {data['strategy_name']}",
        "레짐별 매도(청산) 규칙:",
    ]

    for regime in ["BULL", "SIDEWAYS", "BEAR"]:
        if regime not in data["regime_exit_policy"]:
            continue
        cfg = data["regime_exit_policy"][regime]
        lines.append(
            f"- {regime}: 익절 +{cfg['take_profit_pct']:.1f}%, 손절 -{cfg['stop_loss_pct']:.1f}%, "
            f"트레일링 {cfg['trailing_stop_activation_pct']:.1f}% 활성/{cfg['trailing_stop_pct']:.1f}% 하락, "
            f"RSI>{cfg['rsi_overbought']} (최소수익 {cfg['rsi_exit_min_profit_pct']:.1f}%), "
            f"최대보유 {cfg['time_limit_hours']}h"
        )

    rl = data["risk_limits"]
    lines.append("하드 리스크 한도:")
    lines.append(
        f"- 일손실 -{rl['max_daily_loss_pct']:.1f}%, 일일 신규진입 {rl['max_daily_buy_count']}회, "
        f"{rl['cooldown_after_losses']}연패 시 {rl['cooldown_hours']}h 쿨다운"
    )
    lines.append(SAFETY_DISCLAIMER)
    return {"response": "\n".join(lines)}


async def strategy_review_node(state: AgentState):
    query = str(state["messages"][-1].content)
    data = await asyncio.to_thread(run_strategy_review_tool)

    if data["status"] != "OK":
        return {"response": f"{data['message']}\n{SAFETY_DISCLAIMER}"}

    summary = data["summary"]
    lines = [
        "최근 전략 리뷰 결과:",
        f"- 분석 기간: 최근 {summary['days']}일",
        f"- 실현 손익: {_format_krw(summary['total_realized_pnl_krw'])}",
        f"- 승률: {summary['win_rate'] * 100:.1f}% ({summary['win_count']}승/{summary['sell_count']}건)",
        f"- 평균 손익률: {summary['avg_pnl_pct']:+.2f}%",
        f"- 최대 연속 손실: {summary['max_loss_streak']}회",
        "",
        "장점:",
    ]

    strengths = data.get("strengths") or ["아직 뚜렷한 강점 신호가 부족합니다."]
    for item in strengths[:3]:
        lines.append(f"- {item}")

    lines.append("")
    lines.append("약점:")
    weaknesses = data.get("weaknesses") or ["주요 약점은 관측되지 않았습니다."]
    for item in weaknesses[:3]:
        lines.append(f"- {item}")

    lines.append("")
    lines.append("즉시 개선 3가지:")
    for item in data.get("improvements", [])[:3]:
        lines.append(f"- {item}")

    lines.append("")
    lines.append(SAFETY_DISCLAIMER)

    # 고난도 전략 리뷰 요청(원인/개선/근거 포함)인 경우에만 상위 모델 코멘트를 추가합니다.
    if _should_escalate_premium_review(query):
        premium_commentary = await _generate_premium_review_commentary(query, data)
        if premium_commentary:
            lines.append("")
            lines.append("심화 리뷰 코멘트:")
            lines.append(premium_commentary)

    return {"response": "\n".join(lines)}


async def risk_diagnosis_node(state: AgentState):
    _ = state
    data = await asyncio.to_thread(run_risk_diagnosis_tool)

    snapshot = data["snapshot"]
    lines = [
        f"현재 리스크 레벨: {data['risk_level']}",
        f"- 당일 손익: {_format_krw(snapshot['total_pnl'])}",
        f"- BUY/총 체결: {snapshot['buy_count']} / {snapshot['trade_count']}",
        f"- 연속 손실: {snapshot['consecutive_losses']}회",
        f"- 포지션 집중도: {snapshot['position_concentration'] * 100:.1f}%",
        f"- 최근 24h 리스크 이벤트: {snapshot['audit_events_24h']}건",
        "주요 경고/진단:",
    ]

    for flag in data.get("flags", []):
        lines.append(f"- {flag}")

    lines.append(SAFETY_DISCLAIMER)
    return {"response": "\n".join(lines)}


async def sell_timing_node(state: AgentState):
    _ = state
    data = await asyncio.to_thread(run_sell_timing_tool)

    if data.get("status") != "OK":
        return {"response": f"{data.get('message', '매도 타이밍 분석에 필요한 데이터가 부족합니다.')}\n{SAFETY_DISCLAIMER}"}

    lines = ["보유 종목 매도 타이밍 코칭:"]
    summary = data.get("summary", {})
    lines.append(
        f"- 대상 {summary.get('total_positions', len(data['positions']))}개 포지션 중 즉시 점검 {summary.get('sell_consider_count', 0)}건"
    )

    for item in data["positions"]:
        lines.append(
            f"- {item['symbol']}: {item['recommendation']} (수익률 {item['pnl_pct']:+.2f}%, 레짐 {item['current_regime']})"
        )
        th = item.get("thresholds", {})
        if th:
            lines.append(
                f"  · 기준: 익절 +{th.get('take_profit_pct', 0):.1f}% / 손절 -{th.get('stop_loss_pct', 0):.1f}% / "
                f"트레일링 기준가 {th.get('trailing_stop_price', 0):,.0f}"
            )
        if item.get("signals"):
            for signal in item["signals"][:2]:
                lines.append(f"  · 신호: {signal}")

    lines.append("- 참고: 자동 매도 실행은 하지 않으며, 시나리오 기반 제안만 제공합니다.")
    lines.append(SAFETY_DISCLAIMER)
    return {"response": "\n".join(lines)}


async def action_recommendation_node(state: AgentState):
    query = str(state["messages"][-1].content)
    symbol = _infer_symbol(query)

    market_data, risk_data = await asyncio.gather(
        asyncio.to_thread(run_market_outlook_tool, symbol),
        asyncio.to_thread(run_risk_diagnosis_tool),
    )

    if market_data.get("status") != "OK":
        return {
            "response": (
                "시장 데이터가 부족해 행동 제안을 생성할 수 없습니다. "
                "데이터가 충분해진 뒤 다시 요청해주세요.\n"
                + SAFETY_DISCLAIMER
            )
        }

    risk_level = risk_data.get("risk_level", "WARNING")
    momentum = market_data.get("momentum_1h_pct")
    rsi = market_data.get("rsi14")
    news_risk_level = market_data.get("news_risk_level")
    news_risk_score = market_data.get("news_risk_score")

    recommendation = "관망"
    reason = "데이터 기준으로 보수적 접근이 유리합니다."

    if (
        risk_level == "SAFE"
        and momentum is not None
        and momentum > 0
        and rsi is not None
        and rsi < 65
        and news_risk_level != "HIGH"
    ):
        recommendation = "분할 진입 고려"
        reason = "리스크 상태가 안정적이고 단기 모멘텀이 양수입니다."
    elif risk_level == "HIGH_RISK":
        recommendation = "신규 진입 보류"
        reason = "리스크 가드레일이 경고 구간으로, 방어가 우선입니다."
    elif news_risk_level == "HIGH":
        recommendation = "신규 진입 보류"
        reason = f"뉴스 리스크가 HIGH({news_risk_score:.1f})로 집계되어 이벤트 변동성 위험이 큽니다."

    if recommendation in {"관망", "신규 진입 보류"}:
        conclusion = "결론: 현재는 신규 매수를 보류(관망)하는 쪽이 더 안전합니다."
    elif recommendation == "분할 진입 고려":
        conclusion = "결론: 현재는 소규모 분할 진입을 고려할 수 있습니다."
    else:
        conclusion = f"결론: {recommendation}"

    lines = [
        conclusion,
        f"{symbol} 실행 제안(자동매매 아님): {recommendation}",
        f"- 근거: {reason}",
        f"- 레짐: {market_data.get('regime')} / RSI(14): {rsi if rsi is not None else 'N/A'}",
        f"- 1시간 모멘텀: {momentum:+.2f}%" if momentum is not None else "- 1시간 모멘텀: N/A",
        f"- 리스크 레벨: {risk_level}",
        (
            f"- 뉴스 리스크: {news_risk_level} ({news_risk_score:.1f})"
            if news_risk_score is not None
            else "- 뉴스 리스크: 데이터 부족"
        ),
        "- 제안 방식: 시나리오 기반(진입/보류)이며 자동 주문은 수행하지 않습니다.",
        SAFETY_DISCLAIMER,
    ]

    return {"response": "\n".join(lines)}


async def general_node(state: AgentState):
    _ = state
    return {
        "response": (
            "안녕하세요. CoinPilot AI 트레이딩 비서입니다.\n"
            "아래 유형의 질문을 지원합니다:\n"
            "- 포트폴리오 현황 (잔고/포지션/평가액)\n"
            "- 시장 해석 (레짐/모멘텀/변동성)\n"
            "- 전략 규칙 설명 (매도/청산 정책)\n"
            "- 전략 리뷰 (장점/약점/개선안)\n"
            "- 보유 종목 매도 타이밍 코칭"
        )
    }


def create_chat_graph():
    """LangGraph 워크플로우 그래프를 구성합니다."""
    workflow = StateGraph(AgentState)

    workflow.add_node("classifier", classifier_node)
    workflow.add_node("sql_agent", sql_node)
    workflow.add_node("rag_agent", rag_node)
    workflow.add_node("portfolio_tool", portfolio_node)
    workflow.add_node("market_outlook", market_outlook_node)
    workflow.add_node("strategy_policy", strategy_policy_node)
    workflow.add_node("strategy_review", strategy_review_node)
    workflow.add_node("risk_diagnosis", risk_diagnosis_node)
    workflow.add_node("sell_timing_advice", sell_timing_node)
    workflow.add_node("action_recommendation", action_recommendation_node)
    workflow.add_node("general_chat", general_node)

    workflow.set_entry_point("classifier")

    def route_decision(state: AgentState):
        return state["intent"]

    workflow.add_conditional_edges(
        "classifier",
        route_decision,
        {
            "db_query": "sql_agent",
            "doc_search": "rag_agent",
            "portfolio_status": "portfolio_tool",
            "market_outlook": "market_outlook",
            "strategy_policy": "strategy_policy",
            "strategy_review": "strategy_review",
            "risk_diagnosis": "risk_diagnosis",
            "sell_timing_advice": "sell_timing_advice",
            "action_recommendation": "action_recommendation",
            "general_chat": "general_chat",
        },
    )

    workflow.add_edge("sql_agent", END)
    workflow.add_edge("rag_agent", END)
    workflow.add_edge("portfolio_tool", END)
    workflow.add_edge("market_outlook", END)
    workflow.add_edge("strategy_policy", END)
    workflow.add_edge("strategy_review", END)
    workflow.add_edge("risk_diagnosis", END)
    workflow.add_edge("sell_timing_advice", END)
    workflow.add_edge("action_recommendation", END)
    workflow.add_edge("general_chat", END)

    return workflow.compile()


_chat_graph = None
_graph_lock = threading.Lock()


def get_or_create_chat_graph():
    """그래프 compile은 프로세스당 1회만 수행하도록 캐시합니다."""
    global _chat_graph
    if _chat_graph is None:
        with _graph_lock:
            if _chat_graph is None:
                _chat_graph = create_chat_graph()
    return _chat_graph


async def process_chat(message: str, session_id: str | None = None) -> str:
    """UI에서 호출하는 메인 비동기 진입 함수입니다."""
    normalized_message = message.strip()
    normalized_session = _normalize_session_id(session_id)

    if not normalized_message:
        return _ensure_safety_footer("질문을 입력해주세요.", "general_chat")

    if _is_input_too_long(normalized_message):
        return _ensure_safety_footer(
            f"질문이 너무 깁니다. {CHAT_MAX_INPUT_CHARS}자 이하로 요약해서 다시 요청해주세요.",
            "general_chat",
        )

    cached = _get_cached_response(normalized_session, normalized_message)
    if cached is not None:
        return cached

    blocked, reason = _is_cooldown_blocked(normalized_session)
    if blocked:
        return _ensure_safety_footer(reason, "general_chat")

    app = get_or_create_chat_graph()
    inputs = {"messages": [HumanMessage(content=normalized_message)]}

    try:
        result = await asyncio.wait_for(app.ainvoke(inputs), timeout=40.0)
        raw_response = str(result.get("response", "응답을 생성하지 못했습니다."))
        intent = str(result.get("intent", "general_chat"))
        final_response = _ensure_safety_footer(raw_response, intent)
        _set_cached_response(normalized_session, normalized_message, final_response)
        return final_response
    except asyncio.TimeoutError:
        return _ensure_safety_footer(
            "요청 처리 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
            "general_chat",
        )
    except Exception as exc:
        return _ensure_safety_footer(f"챗봇 처리 중 오류가 발생했습니다: {str(exc)}", "general_chat")


def process_chat_sync(message: str, session_id: str | None = None) -> str:
    """동기 환경(Streamlit)에서 안전하게 사용할 수 있는 래퍼입니다."""
    return run_async_safely(process_chat, message, session_id)
