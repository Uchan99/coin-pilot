from src.common.models import (
    ExchangeAccountSnapshot,
    ExchangeFill,
    ExchangeOrder,
    ReconciliationRun,
)


def test_live_trading_foundation_table_names():
    assert ExchangeAccountSnapshot.__tablename__ == "exchange_account_snapshots"
    assert ExchangeOrder.__tablename__ == "exchange_orders"
    assert ExchangeFill.__tablename__ == "exchange_fills"
    assert ReconciliationRun.__tablename__ == "reconciliation_runs"


def test_exchange_order_unique_constraint_exists():
    table = ExchangeOrder.__table__
    constraint_names = {constraint.name for constraint in table.constraints}
    assert "uq_exchange_orders_exchange_order_id" in constraint_names


def test_reconciliation_run_core_columns_exist():
    columns = ReconciliationRun.__table__.columns
    for name in (
        "mode",
        "status",
        "account_mismatch_count",
        "order_mismatch_count",
        "fill_mismatch_count",
        "portfolio_mismatch_count",
        "details",
    ):
        assert name in columns
