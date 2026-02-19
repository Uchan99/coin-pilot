from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.models import TradingHistory, MarketData
from src.utils.metrics import metrics

TRACK_WINDOWS = {
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "12h": timedelta(hours=12),
    "24h": timedelta(hours=24),
}


def _get_base_time(order: TradingHistory) -> datetime:
    """추적 기준 시각: executed_at 우선, 없으면 created_at fallback."""
    return order.executed_at or order.created_at


def _is_complete(post_exit_prices: Optional[Dict]) -> bool:
    if not isinstance(post_exit_prices, dict):
        return False
    return all(k in post_exit_prices for k in TRACK_WINDOWS)


async def _get_nearest_close_price(
    session: AsyncSession,
    symbol: str,
    target_ts: datetime,
    tolerance_minutes: int = 5,
) -> Optional[Decimal]:
    """
    목표 시각 ±tolerance 내 가장 가까운 1분봉 close 가격을 조회한다.
    """
    start_ts = target_ts - timedelta(minutes=tolerance_minutes)
    end_ts = target_ts + timedelta(minutes=tolerance_minutes)

    distance_expr = func.abs(func.extract("epoch", MarketData.timestamp - target_ts))

    stmt = (
        select(MarketData.close_price)
        .where(
            and_(
                MarketData.symbol == symbol,
                MarketData.interval == "1m",
                MarketData.timestamp >= start_ts,
                MarketData.timestamp <= end_ts,
            )
        )
        .order_by(distance_expr)
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def track_post_exit_prices(session: AsyncSession, now: Optional[datetime] = None) -> Dict[str, int]:
    """
    SELL 체결 이후 1h/4h/12h/24h 시점의 후속 가격을 추적해 post_exit_prices에 기록한다.
    """
    now = now or datetime.now(timezone.utc)
    tracked_points = 0
    missed_points = 0
    updated_orders = 0

    stmt = (
        select(TradingHistory)
        .where(
            and_(
                TradingHistory.side == "SELL",
                TradingHistory.status == "FILLED",
                TradingHistory.price.is_not(None),
            )
        )
        .order_by(TradingHistory.executed_at.desc().nullslast(), TradingHistory.created_at.desc())
        .limit(300)
    )
    result = await session.execute(stmt)
    sell_orders = result.scalars().all()

    for order in sell_orders:
        base_time = _get_base_time(order)
        if not base_time:
            continue

        post_exit = dict(order.post_exit_prices or {})
        if _is_complete(post_exit):
            continue

        changed = False
        exit_price = Decimal(str(order.price))
        if exit_price <= 0:
            continue

        for label, window in TRACK_WINDOWS.items():
            if label in post_exit:
                continue

            target_time = base_time + window
            if now < target_time:
                continue

            tracked_price = await _get_nearest_close_price(session, order.symbol, target_time)
            if tracked_price is None:
                missed_points += 1
                metrics.post_exit_missed.inc()
                continue

            tracked_price_dec = Decimal(str(tracked_price))
            change_pct = (tracked_price_dec - exit_price) / exit_price * Decimal("100")
            post_exit[label] = {
                "price": float(tracked_price_dec),
                "change_pct": float(round(change_pct, 6)),
                "tracked_at": now.isoformat(),
            }
            tracked_points += 1
            metrics.post_exit_tracked.inc()
            changed = True

        if changed:
            order.post_exit_prices = post_exit
            updated_orders += 1

    if updated_orders > 0:
        await session.flush()

    return {
        "orders_scanned": len(sell_orders),
        "orders_updated": updated_orders,
        "points_tracked": tracked_points,
        "points_missed": missed_points,
    }


async def track_post_exit_prices_job() -> None:
    """Scheduler에서 호출되는 post-exit tracker 작업."""
    from src.common.db import get_db_session

    print("[Scheduler] Running post-exit price tracker...")
    try:
        async with get_db_session() as session:
            stats = await track_post_exit_prices(session)
            print(
                "[Scheduler] Post-exit tracker done: "
                f"scanned={stats['orders_scanned']}, "
                f"updated={stats['orders_updated']}, "
                f"tracked={stats['points_tracked']}, "
                f"missed={stats['points_missed']}"
            )
    except Exception as e:
        print(f"[Scheduler] Post-exit tracker failed: {e}")
