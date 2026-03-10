from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from src.common.db import get_db_session
from src.common.models import TradingHistory


@dataclass
class AnalystReplaySample:
    sample_id: str
    symbol: str
    strategy_name: str
    regime: str
    indicators: Dict[str, Any]
    market_context: List[Dict[str, Any]]
    created_at: datetime


def build_replay_sample_from_signal_info(
    *,
    sample_id: str,
    symbol: str,
    strategy_name: str,
    regime: Optional[str],
    created_at: datetime,
    signal_info: Any,
) -> Optional[AnalystReplaySample]:
    """
    trading_history.signal_info에서 replay 가능한 Analyst 입력 샘플을 복원한다.

    왜 BUY signal_info를 쓰는가:
    - BUY 시점 signal_info에는 당시 AI 입력용 indicators와 market_context가 함께 저장된다.
    - 별도 스키마를 추가하지 않고 과거 운영 입력을 가장 가깝게 복원할 수 있는 현재의 source of truth다.
    """
    if not isinstance(signal_info, dict):
        return None

    market_context = signal_info.get("market_context")
    if not isinstance(market_context, list) or not market_context:
        return None

    indicators = dict(signal_info)
    indicators.pop("market_context", None)
    indicators.setdefault("symbol", symbol)
    indicators.setdefault("regime", regime or indicators.get("regime") or "UNKNOWN")

    return AnalystReplaySample(
        sample_id=sample_id,
        symbol=symbol,
        strategy_name=strategy_name,
        regime=str(indicators.get("regime") or "UNKNOWN"),
        indicators=indicators,
        market_context=market_context,
        created_at=created_at,
    )


async def load_recent_analyst_replay_samples(
    *,
    hours: int = 168,
    limit: int = 50,
) -> List[AnalystReplaySample]:
    """
    최근 BUY 주문의 signal_info에서 replay 샘플을 적재한다.

    설계 의도:
    - live canary 표본이 적을 때도 과거 실제 입력을 재생해 baseline/RAG-on 차이를 비교하기 위함
    - SELL/청산 데이터는 진입 Analyst 입력과 맥락이 다르므로 Phase 1에서는 제외한다.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=max(1, int(hours)))
    cap = max(1, int(limit))

    async with get_db_session() as session:
        stmt = (
            select(TradingHistory)
            .where(TradingHistory.created_at >= since)
            .where(TradingHistory.side == "BUY")
            .order_by(TradingHistory.created_at.desc())
            .limit(cap * 3)
        )
        rows = (await session.execute(stmt)).scalars().all()

    samples: List[AnalystReplaySample] = []
    for row in rows:
        sample = build_replay_sample_from_signal_info(
            sample_id=str(row.id),
            symbol=row.symbol,
            strategy_name=row.strategy_name or "UNKNOWN",
            regime=row.regime,
            created_at=row.created_at,
            signal_info=row.signal_info,
        )
        if sample is None:
            continue
        samples.append(sample)
        if len(samples) >= cap:
            break

    return samples
