import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import select

from src.common.db import get_db_session
from src.common.models import AgentDecision, RuleFunnelEvent, TradingHistory


def _config_path() -> Path:
    """
    AI Decision 전용 전략 레퍼런스 설정 파일 경로를 반환한다.

    왜 markdown 원문 대신 별도 JSON을 두는가:
    - bot 컨테이너는 `docs/` 전체를 포함하지 않으므로, Charter 원문을 런타임에 직접 읽는 구조는
      운영 환경과 로컬 환경이 달라질 수 있다.
    - Phase 1에서는 "전략 문서 전체 검색"보다 "검증된 핵심 운영 규칙만 짧게 주입"하는 편이
      토큰/지연/드리프트 측면에서 더 안전하다.
    """
    return Path(__file__).resolve().parents[2] / "config" / "ai_decision_rag_strategy_refs.json"


@lru_cache(maxsize=1)
def _load_strategy_reference_config() -> Dict[str, Any]:
    path = _config_path()
    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    if not isinstance(payload, dict):
        raise ValueError("ai_decision_rag_strategy_refs.json must be a JSON object")
    return payload


def build_strategy_reference_lines(regime: str) -> List[str]:
    """
    현재 레짐에 맞는 전략 문서 기반 핵심 레퍼런스를 짧은 bullet 목록으로 만든다.

    설계 의도:
    - Analyst는 장문의 문서를 그대로 읽기보다, 운영에 이미 굳어진 핵심 규칙 요약을
      짧게 참조하는 편이 안정적이다.
    - 규칙의 "설명"이 아니라 "현재 판단에 도움이 되는 운영 제약"만 선택적으로 넣는다.
    """
    config = _load_strategy_reference_config()
    normalized_regime = (regime or "UNKNOWN").strip().upper()

    lines: List[str] = []
    for section_name in ("global",):
        section = config.get(section_name, [])
        if isinstance(section, list):
            lines.extend(str(item).strip() for item in section if str(item).strip())

    regime_section = (config.get("regime") or {}).get(normalized_regime, [])
    if isinstance(regime_section, list):
        lines.extend(str(item).strip() for item in regime_section if str(item).strip())

    # 전략 요약은 "많을수록 좋은" 정보가 아니다.
    # Phase 1 replay 결과에서 strategy:9가 과도한 보수 앵커링을 유발했기 때문에,
    # 28-01부터는 핵심 운영 경계 + 레짐별 기술 해석만 남기고 최대 4줄로 제한한다.
    return lines[:4]


def render_ai_decision_rag_text(strategy_lines: List[str], case_lines: List[str]) -> str:
    """
    Analyst 프롬프트용 RAG 블록 문자열을 렌더링한다.

    설계 의도:
    - 28-01 보정의 핵심은 retrieval 소스 수를 바꾸는 것이 아니라,
      "무엇을 먼저 보게 할 것인가"를 조정하는 것이다.
    - 과거 사례를 전략 요약보다 먼저 배치해, 정적 운영 원칙보다
      실제 유사 사례와 최근 병목을 우선 참고하게 만든다.
    """
    blocks: List[str] = []
    if case_lines:
        blocks.append("[과거 사례 요약]\n- " + "\n- ".join(case_lines))
    if strategy_lines:
        blocks.append("[전략 문서 핵심]\n- " + "\n- ".join(strategy_lines))
    return "\n\n".join(blocks).strip()


async def build_recent_case_reference_lines(
    symbol: str,
    regime: str,
    strategy_name: str,
    lookback_days: int = 30,
) -> List[str]:
    """
    최근 운영 사례를 요약해 "과거 사례" 레이어를 구성한다.

    왜 이렇게 요약하는가:
    - Phase 1의 목표는 정교한 학습이 아니라 "현재 신호와 유사한 운영 병목/결과"를
      짧게 상기시키는 것이다.
    - 원문 reasoning 전체를 그대로 넣으면 잡음과 토큰 낭비가 커지므로, stage/reason/최근 결과를
      집계형 bullet로 압축한다.
    """
    since = datetime.now(timezone.utc) - timedelta(days=max(1, int(lookback_days)))
    normalized_regime = (regime or "").strip().upper()
    normalized_symbol = (symbol or "").strip().upper()
    normalized_strategy = (strategy_name or "").strip()

    lines: List[str] = []

    async with get_db_session() as session:
        funnel_stmt = (
            select(RuleFunnelEvent)
            .where(RuleFunnelEvent.created_at >= since)
            .where(
                (RuleFunnelEvent.symbol == normalized_symbol)
                | (RuleFunnelEvent.regime == normalized_regime)
            )
            .order_by(RuleFunnelEvent.created_at.desc())
            .limit(200)
        )
        funnel_rows = (await session.execute(funnel_stmt)).scalars().all()

        if funnel_rows:
            stage_counter = Counter((row.stage or "unknown") for row in funnel_rows)
            reason_counter = Counter(
                f"{row.stage}:{row.reason_code or 'unknown'}" for row in funnel_rows if row.stage
            )

            top_stages = ", ".join(
                f"{stage}={count}" for stage, count in stage_counter.most_common(3)
            )
            if top_stages:
                lines.append(f"최근 퍼널 상위 단계: {top_stages}")

            top_reasons = ", ".join(
                f"{reason}={count}" for reason, count in reason_counter.most_common(3)
            )
            if top_reasons:
                lines.append(f"최근 퍼널 상위 사유: {top_reasons}")

        decision_stmt = (
            select(AgentDecision)
            .where(AgentDecision.created_at >= since)
            .where(
                (AgentDecision.symbol == normalized_symbol)
                | (AgentDecision.regime == normalized_regime)
            )
            .order_by(AgentDecision.created_at.desc())
            .limit(6)
        )
        decision_rows = (await session.execute(decision_stmt)).scalars().all()

        if decision_rows:
            decision_counter = Counter((row.decision or "UNKNOWN") for row in decision_rows)
            lines.append(
                "최근 AI 결정 분포: "
                + ", ".join(f"{decision}={count}" for decision, count in decision_counter.items())
            )

            latest = decision_rows[0]
            reasoning = (latest.reasoning or "").strip().replace("\n", " ")
            preview = reasoning[:180] + ("..." if len(reasoning) > 180 else "")
            if preview:
                lines.append(
                    f"가장 최근 AI 사례: decision={latest.decision}, confidence={latest.confidence}, reasoning={preview}"
                )

        trade_stmt = (
            select(TradingHistory)
            .where(TradingHistory.created_at >= since)
            .where(TradingHistory.symbol == normalized_symbol)
            .where(TradingHistory.strategy_name == normalized_strategy)
            .where(TradingHistory.side == "SELL")
            .order_by(TradingHistory.created_at.desc())
            .limit(5)
        )
        trade_rows = (await session.execute(trade_stmt)).scalars().all()

        if trade_rows:
            exit_counter = Counter((row.exit_reason or "UNKNOWN") for row in trade_rows)
            lines.append(
                "최근 청산 사유: "
                + ", ".join(f"{reason}={count}" for reason, count in exit_counter.items())
            )

    return lines[:5]


async def build_ai_decision_rag_context(
    symbol: str,
    regime: str,
    strategy_name: str,
    lookback_days: int = 30,
) -> Dict[str, Any]:
    """
    AI Decision에서 사용할 2계층 RAG 컨텍스트를 생성한다.

    반환 구조:
    - strategy_lines: 전략 문서 기반 bullet
    - case_lines: 과거 사례 기반 bullet
    - source_summary: 운영/디버깅용 요약 메타
    - text: 프롬프트에 직접 삽입 가능한 문자열
    """
    strategy_lines = build_strategy_reference_lines(regime=regime)
    case_lines = await build_recent_case_reference_lines(
        symbol=symbol,
        regime=regime,
        strategy_name=strategy_name,
        lookback_days=lookback_days,
    )

    return {
        "strategy_lines": strategy_lines,
        "case_lines": case_lines,
        "source_summary": [
            f"strategy:{len(strategy_lines)}",
            f"cases:{len(case_lines)}",
        ],
        "text": render_ai_decision_rag_text(strategy_lines=strategy_lines, case_lines=case_lines),
    }
