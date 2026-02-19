from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.common.models import AccountState, DailyRiskState
from src.engine.risk_manager import RiskManager


@pytest.mark.asyncio
async def test_update_after_trade_buy_increments_buy_and_total(test_db):
    test_db.add(AccountState(id=1, balance=Decimal("1000000")))
    await test_db.flush()

    risk_manager = RiskManager(max_daily_trades=10)

    await risk_manager.update_after_trade(test_db, Decimal("0"), side="BUY")

    state = await risk_manager.get_daily_state(test_db)
    assert state.buy_count == 1
    assert state.sell_count == 0
    assert state.trade_count == 1
    assert state.total_pnl == 0


@pytest.mark.asyncio
async def test_update_after_trade_sell_increments_sell_and_total(test_db):
    test_db.add(AccountState(id=1, balance=Decimal("1000000")))
    await test_db.flush()

    risk_manager = RiskManager(max_daily_trades=10)

    await risk_manager.update_after_trade(test_db, Decimal("1000"), side="SELL")

    state = await risk_manager.get_daily_state(test_db)
    assert state.buy_count == 0
    assert state.sell_count == 1
    assert state.trade_count == 1
    assert state.total_pnl == Decimal("1000")


@pytest.mark.asyncio
async def test_max_daily_trades_checks_buy_count_only(test_db):
    test_db.add(AccountState(id=1, balance=Decimal("1000000")))
    test_db.add(
        DailyRiskState(
            date=datetime.now(timezone.utc).date(),
            total_pnl=Decimal("0"),
            buy_count=10,
            sell_count=0,
            trade_count=10,
            consecutive_losses=0,
        )
    )
    await test_db.flush()

    risk_manager = RiskManager(max_daily_trades=10)

    passed, reason = await risk_manager.check_order_validity(
        test_db,
        "KRW-BTC",
        Decimal("1000"),
    )
    assert passed is False
    assert "최대 거래 횟수" in reason
