import numpy as np
import pandas as pd
import streamlit as st
from src.dashboard.components.auth_guard import enforce_dashboard_access

from src.dashboard.utils.db_connector import get_data_as_dataframe
from src.dashboard.utils.formatters import (
    format_krw,
    format_krw_compact,
    format_pct,
    format_qty,
)
from src.dashboard.components.floating_chat import render_floating_chat

enforce_dashboard_access()

st.title("📊 Overview")

# 1) Portfolio KPI
balance_df = get_data_as_dataframe(
    "SELECT balance FROM account_state ORDER BY updated_at DESC LIMIT 1"
)
current_balance = float(balance_df.iloc[0]["balance"]) if not balance_df.empty else 0.0

pnl_df = get_data_as_dataframe("SELECT SUM(total_pnl) as cum_pnl FROM daily_risk_state")
total_pnl = (
    float(pnl_df.iloc[0]["cum_pnl"])
    if not pnl_df.empty and pnl_df.iloc[0]["cum_pnl"] is not None
    else 0.0
)

trades_df = get_data_as_dataframe(
    "SELECT COUNT(*) as cnt FROM trading_history WHERE status = 'FILLED'"
)
total_trades = int(trades_df.iloc[0]["cnt"]) if not trades_df.empty else 0

# Holdings 조회 (KPI + 테이블 공용)
query_positions = """
    SELECT
        p.symbol,
        p.quantity,
        p.avg_price,
        m.close_price AS current_price
    FROM positions p
    LEFT JOIN (
        SELECT DISTINCT ON (symbol) symbol, close_price
        FROM market_data
        ORDER BY symbol, timestamp DESC
    ) m ON p.symbol = m.symbol
"""
positions_df = get_data_as_dataframe(query_positions)

holdings_current_value = 0.0
if not positions_df.empty:
    _kpi_df = positions_df.copy()
    _kpi_df["quantity"] = pd.to_numeric(_kpi_df["quantity"], errors="coerce")
    _kpi_df["current_price"] = pd.to_numeric(_kpi_df["current_price"], errors="coerce")
    _kpi_df["valuation_krw"] = _kpi_df["quantity"] * _kpi_df["current_price"]
    holdings_current_value = float(_kpi_df["valuation_krw"].fillna(0).sum())

total_valuation = current_balance + holdings_current_value

compact_amount = st.toggle("금액 축약 표시 (만 원)", value=True)


def _fmt_amount(v: float, signed: bool = False) -> str:
    if compact_amount:
        return format_krw_compact(v, signed=signed)
    return format_krw(v, signed=signed)


row1_col1, row1_col2, row1_col3 = st.columns(3)
with row1_col1:
    st.metric(label="총 체결", value=f"{total_trades}회")
with row1_col2:
    st.metric(
        label="누적 손익",
        value=f"{_fmt_amount(total_pnl, signed=True)}",
        delta=f"{_fmt_amount(total_pnl, signed=True)}",
        delta_color="normal",
    )
with row1_col3:
    st.metric(label="총 평가액", value=f"{_fmt_amount(total_valuation)}")

row2_col1, row2_col2 = st.columns(2)
with row2_col1:
    st.metric(label="현재 잔고", value=f"{_fmt_amount(current_balance)}")
with row2_col2:
    st.metric(label="승률", value="N/A", help="승률 데이터는 Exit 분석 탭에서 확인")

st.markdown("---")

# 2) Holdings
st.subheader("보유 자산 (활성 포지션)")

if positions_df.empty:
    st.info("현재 보유 중인 포지션이 없습니다. (No Active Positions)")
    render_floating_chat()
    st.stop()

calc_df = positions_df.copy()
for col in ["quantity", "avg_price", "current_price"]:
    calc_df[col] = pd.to_numeric(calc_df[col], errors="coerce")

# invalid rows safe handling
valid_base = (
    calc_df["quantity"].notna()
    & (calc_df["quantity"] > 0)
    & calc_df["avg_price"].notna()
    & (calc_df["avg_price"] > 0)
)
has_price = calc_df["current_price"].notna() & (calc_df["current_price"] > 0)

calc_df["invested_krw"] = np.where(
    valid_base,
    calc_df["avg_price"] * calc_df["quantity"],
    np.nan,
)
calc_df["valuation_krw"] = np.where(
    valid_base & has_price,
    calc_df["current_price"] * calc_df["quantity"],
    np.nan,
)
calc_df["unrealized_pnl_krw"] = np.where(
    calc_df["invested_krw"].notna() & calc_df["valuation_krw"].notna(),
    calc_df["valuation_krw"] - calc_df["invested_krw"],
    np.nan,
)
calc_df["unrealized_pnl_pct"] = np.where(
    calc_df["invested_krw"].notna() & (calc_df["invested_krw"] > 0) & calc_df["unrealized_pnl_krw"].notna(),
    calc_df["unrealized_pnl_krw"] / calc_df["invested_krw"] * 100.0,
    np.nan,
)

display_df = calc_df[
    [
        "symbol",
        "quantity",
        "avg_price",
        "invested_krw",
        "valuation_krw",
        "unrealized_pnl_krw",
        "unrealized_pnl_pct",
    ]
].copy()

display_df = display_df.sort_values("symbol", ascending=True, na_position="last")

display_df["quantity"] = display_df["quantity"].map(format_qty)
display_df["avg_price"] = display_df["avg_price"].map(format_krw)
display_df["invested_krw"] = display_df["invested_krw"].map(format_krw)
display_df["valuation_krw"] = display_df["valuation_krw"].map(format_krw)
display_df["unrealized_pnl_krw"] = display_df["unrealized_pnl_krw"].map(
    lambda x: format_krw(x, signed=True)
)
display_df["unrealized_pnl_pct"] = display_df["unrealized_pnl_pct"].map(
    lambda x: format_pct(x, signed=True)
)

st.dataframe(
    display_df,
    column_config={
        "symbol": "심볼",
        "quantity": "수량",
        "avg_price": "평단가 (KRW)",
        "invested_krw": "투자금 (KRW)",
        "valuation_krw": "현재가치 (KRW)",
        "unrealized_pnl_krw": "손익 (KRW)",
        "unrealized_pnl_pct": "수익률 (%)",
    },
    use_container_width=True,
    hide_index=True,
)

render_floating_chat()
