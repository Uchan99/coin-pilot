import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from src.engine.risk_manager import RiskManager
from src.common.models import AccountState, DailyRiskState

@pytest.mark.asyncio
async def test_risk_manager_order_limit(test_db):
    # 1. 계좌 기초 데이터 설정 (잔고 1,000,000)
    account = AccountState(id=1, balance=Decimal("1000000"))
    test_db.add(account)
    await test_db.flush()
    
    risk_manager = RiskManager(max_per_order=0.05) # 5% 한도 = 50,000
    
    # 2. 통과되는 주문 (40,000)
    passed, reason = await risk_manager.check_order_validity(test_db, "KRW-BTC", Decimal("40000"))
    assert passed is True
    
    # 3. 거절되는 주문 (60,000)
    passed, reason = await risk_manager.check_order_validity(test_db, "KRW-BTC", Decimal("60000"))
    assert passed is False
    assert "단일 주문 한도" in reason

@pytest.mark.asyncio
async def test_risk_manager_cooldown(test_db):
    account = AccountState(id=1, balance=Decimal("1000000"))
    test_db.add(account)
    await test_db.flush()
    
    risk_manager = RiskManager(cooldown_hours=2)
    
    # 1. 3번 연속 손실 발생시키기
    await risk_manager.update_after_trade(test_db, Decimal("-100"))
    await risk_manager.update_after_trade(test_db, Decimal("-100"))
    await risk_manager.update_after_trade(test_db, Decimal("-100"))
    
    # 2. 주문 금지 확인 (쿨다운)
    passed, reason = await risk_manager.check_order_validity(test_db, "KRW-BTC", Decimal("1000"))
    assert passed is False
    assert "쿨다운" in reason

@pytest.mark.asyncio
async def test_risk_manager_daily_loss_limit(test_db):
    # 잔고 100만, 최대 손실 5% = 5만
    account = AccountState(id=1, balance=Decimal("1000000"))
    test_db.add(account)
    await test_db.flush()
    
    risk_manager = RiskManager(max_daily_loss=0.05)
    
    # 6만 원 손실 기록
    await risk_manager.update_after_trade(test_db, Decimal("-60000"))
    
    # 주문 시도 -> 중단 확인
    passed, reason = await risk_manager.check_order_validity(test_db, "KRW-BTC", Decimal("1000"))
    assert passed is False
    assert "최대 손실 한도" in reason
