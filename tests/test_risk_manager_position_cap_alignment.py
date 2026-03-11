from decimal import Decimal

import pytest

from src.engine.risk_manager import RiskManager


@pytest.mark.asyncio
async def test_target_order_sizing_clamps_regime_symbol_ratio_to_hard_cap(monkeypatch):
    risk_manager = RiskManager(max_per_order=0.20)

    async def _mock_volatility_multiplier():
        return 1.0

    monkeypatch.setattr(risk_manager, "get_volatility_multiplier", _mock_volatility_multiplier)

    sizing = await risk_manager.build_target_order_sizing(
        reference_equity=Decimal("1000000"),
        regime_ratio=Decimal("0.9"),
        symbol_multiplier=Decimal("1.2"),
    )

    assert sizing["raw_effective_ratio"] == Decimal("1.08")
    assert sizing["effective_ratio"] == Decimal("1")
    assert sizing["max_order_amount"] == Decimal("200000.00")
    assert sizing["target_invest_amount"] == Decimal("200000.00")


@pytest.mark.asyncio
async def test_target_order_sizing_applies_volatility_cap_before_target(monkeypatch):
    risk_manager = RiskManager(max_per_order=0.20)

    async def _mock_volatility_multiplier():
        return 0.5

    monkeypatch.setattr(risk_manager, "get_volatility_multiplier", _mock_volatility_multiplier)

    sizing = await risk_manager.build_target_order_sizing(
        reference_equity=Decimal("1000000"),
        regime_ratio=Decimal("1.0"),
        symbol_multiplier=Decimal("1.0"),
    )

    assert sizing["volatility_multiplier"] == Decimal("0.5")
    assert sizing["max_order_amount"] == Decimal("100000.00")
    assert sizing["target_invest_amount"] == Decimal("100000.00")


@pytest.mark.asyncio
async def test_target_order_sizing_never_exceeds_dynamic_max_order_amount(monkeypatch):
    risk_manager = RiskManager(max_per_order=0.20)

    async def _mock_volatility_multiplier():
        return 0.5

    monkeypatch.setattr(risk_manager, "get_volatility_multiplier", _mock_volatility_multiplier)

    sizing = await risk_manager.build_target_order_sizing(
        reference_equity=Decimal("1000000"),
        regime_ratio=Decimal("0.9"),
        symbol_multiplier=Decimal("1.2"),
    )

    assert sizing["raw_effective_ratio"] == Decimal("1.08")
    assert sizing["effective_ratio"] == Decimal("1")
    assert sizing["max_order_amount"] == Decimal("100000.00")
    assert sizing["target_invest_amount"] == Decimal("100000.00")
    assert sizing["target_invest_amount"] <= sizing["max_order_amount"]
