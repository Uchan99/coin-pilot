import streamlit as st
import pandas as pd
import plotly.express as px
from src.dashboard.utils.db_connector import get_data_as_dataframe
from src.dashboard.components.floating_chat import render_floating_chat

st.title("📜 Trade History")

# 1. Filters
col1, col2 = st.columns(2)
with col1:
    symbol_filter = st.text_input("Filter by Symbol", placeholder="e.g. KRW-BTC")
with col2:
    side_filter = st.selectbox("Filter by Side", ["All", "BUY", "SELL"])

# 2. Query Construction
base_query = """
    SELECT 
        COALESCE(executed_at, created_at) + interval '9 hours' as filled_at, 
        symbol, 
        side, 
        price, 
        quantity, 
        (price * quantity) as total_value,
        (signal_info->>'entry_avg_price')::numeric AS entry_avg_price,
        CASE
            WHEN side = 'SELL'
             AND (signal_info->>'entry_avg_price') IS NOT NULL
             AND (signal_info->>'entry_avg_price')::numeric > 0
            THEN (price - (signal_info->>'entry_avg_price')::numeric) * quantity
            ELSE NULL
        END AS realized_pnl_krw,
        CASE
            WHEN side = 'SELL'
             AND (signal_info->>'entry_avg_price') IS NOT NULL
             AND (signal_info->>'entry_avg_price')::numeric > 0
            THEN (price - (signal_info->>'entry_avg_price')::numeric) / (signal_info->>'entry_avg_price')::numeric * 100
            ELSE NULL
        END AS realized_pnl_pct,
        COALESCE(regime, 'UNKNOWN') AS regime,
        COALESCE(exit_reason, 'UNKNOWN') AS exit_reason,
        status,
        strategy_name
    FROM trading_history
    WHERE 1=1
"""
params = {}

if symbol_filter:
    base_query += " AND symbol LIKE :symbol"
    params['symbol'] = f"%{symbol_filter}%"

if side_filter != "All":
    base_query += " AND side = :side"
    params['side'] = side_filter

base_query += " ORDER BY COALESCE(executed_at, created_at) DESC LIMIT 100"

df = get_data_as_dataframe(base_query, params)

# 3. Display Data
if not df.empty:
    # 포맷팅
    display_df = df.copy()
    # SELL 행에서만 실현손익 관련 컬럼을 의미 있게 노출하고, BUY는 N/A 처리합니다.
    sell_mask = display_df["side"] == "SELL"
    display_df.loc[~sell_mask, ["entry_avg_price", "realized_pnl_krw", "realized_pnl_pct"]] = pd.NA

    display_df["price"] = pd.to_numeric(display_df["price"], errors="coerce").map(
        lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
    )
    display_df["total_value"] = pd.to_numeric(display_df["total_value"], errors="coerce").map(
        lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
    )
    display_df["entry_avg_price"] = pd.to_numeric(display_df["entry_avg_price"], errors="coerce").map(
        lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
    )
    display_df["realized_pnl_krw"] = pd.to_numeric(display_df["realized_pnl_krw"], errors="coerce").map(
        lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
    )
    display_df["realized_pnl_pct"] = pd.to_numeric(display_df["realized_pnl_pct"], errors="coerce").map(
        lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A"
    )
    
    st.dataframe(
        display_df,
        column_config={
            "filled_at": "Time",
            "symbol": "Symbol",
            "side": "Side",
            "price": "Price",
            "quantity": "Qty",
            "total_value": "Value (KRW)",
            "entry_avg_price": "Entry Avg (KRW)",
            "realized_pnl_krw": "Realized PnL (KRW)",
            "realized_pnl_pct": "Realized PnL (%)",
            "regime": "Regime",
            "exit_reason": "Exit Reason",
            "status": "Status",
        },
        use_container_width=True,
        hide_index=True
    )
    
    # 4. Summary Chart
    st.markdown("### Summary")
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        # Side 분포 (Pie Chart)
        fig_side = px.pie(df, names='side', title='Buy/Sell Ratio', hole=0.4)
        st.plotly_chart(fig_side, use_container_width=True)
        
    with chart_col2:
        # Status 분포 (Bar Chart)
        status_counts = df['status'].value_counts().reset_index()
        status_counts.columns = ['status', 'count']
        fig_status = px.bar(status_counts, x='status', y='count', title='Order Status', color='status')
        st.plotly_chart(fig_status, use_container_width=True)

else:
    st.info("검색된 거래 내역이 없습니다.")

render_floating_chat()
