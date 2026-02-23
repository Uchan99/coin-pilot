import streamlit as st
from src.dashboard.components.auth_guard import enforce_dashboard_access
import pandas as pd
import plotly.express as px
from src.dashboard.utils.db_connector import get_data_as_dataframe
from src.dashboard.components.floating_chat import render_floating_chat

enforce_dashboard_access()

st.title("📜 거래 이력")
st.caption("`FILLED`는 주문이 실제로 체결 완료된 상태를 의미합니다. (미체결/취소 아님)")

# 1. Filters
col1, col2, col3 = st.columns([1.2, 1.2, 1.0])
with col1:
    symbol_filter = st.text_input("심볼 필터", placeholder="예: KRW-BTC")
with col2:
    side_filter_ui = st.selectbox("매수/매도 필터", ["전체", "매수(BUY)", "매도(SELL)"])
with col3:
    view_mode = st.selectbox("표시 모드", ["기본 보기", "상세 보기"])

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

if side_filter_ui != "전체":
    side_filter = "BUY" if side_filter_ui == "매수(BUY)" else "SELL"
    base_query += " AND side = :side"
    params["side"] = side_filter

base_query += " ORDER BY COALESCE(executed_at, created_at) DESC LIMIT 100"

df = get_data_as_dataframe(base_query, params)

# 3. Display Data
if not df.empty:
    # 포맷팅
    display_df = df.copy()
    # SELL 행에서만 실현손익 관련 컬럼을 의미 있게 노출하고, BUY는 N/A 처리합니다.
    sell_mask = display_df["side"] == "SELL"
    display_df.loc[~sell_mask, ["entry_avg_price", "realized_pnl_krw", "realized_pnl_pct"]] = pd.NA
    display_df["side"] = display_df["side"].map({"BUY": "매수", "SELL": "매도"}).fillna(display_df["side"])
    display_df["status"] = display_df["status"].map({"FILLED": "체결완료(FILLED)"}).fillna(display_df["status"])

    display_df["price"] = pd.to_numeric(display_df["price"], errors="coerce").map(
        lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
    )
    display_df["quantity"] = pd.to_numeric(display_df["quantity"], errors="coerce").map(
        lambda x: f"{x:,.8f}" if pd.notna(x) else "N/A"
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

    # 한국어 가독성 및 가로폭 개선:
    # - 기본 보기: 핵심 손익 컬럼 위주
    # - 상세 보기: 레짐/청산사유/전략명까지 확장
    base_columns = [
        "filled_at",
        "symbol",
        "side",
        "entry_avg_price",
        "price",
        "quantity",
        "realized_pnl_krw",
        "realized_pnl_pct",
        "total_value",
        "status",
    ]
    detail_only_columns = ["regime", "exit_reason", "strategy_name"]
    selected_columns = base_columns + detail_only_columns if view_mode == "상세 보기" else base_columns

    st.dataframe(
        display_df[selected_columns],
        column_config={
            "filled_at": st.column_config.DatetimeColumn("체결 시각", format="YYYY-MM-DD HH:mm:ss"),
            "symbol": "심볼",
            "side": "구분",
            "price": "매도/매수 가격",
            "quantity": "수량",
            "total_value": "체결 금액 (KRW)",
            "entry_avg_price": "평균 매수가 (KRW)",
            "realized_pnl_krw": "실현 손익 (KRW)",
            "realized_pnl_pct": "실현 손익률 (%)",
            "regime": "레짐",
            "exit_reason": "청산 사유",
            "strategy_name": "전략",
            "status": "상태",
        },
        use_container_width=True,
        hide_index=True
    )
    
    # 4. Summary Chart
    st.markdown("### 요약 차트")
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        # Side 분포 (Pie Chart)
        side_df = df.copy()
        side_df["side"] = side_df["side"].map({"BUY": "매수", "SELL": "매도"}).fillna(side_df["side"])
        fig_side = px.pie(side_df, names="side", title="매수/매도 비중", hole=0.4)
        st.plotly_chart(fig_side, use_container_width=True)
        
    with chart_col2:
        # Status 분포 (Bar Chart)
        status_counts = df["status"].map({"FILLED": "체결완료(FILLED)"}).fillna(df["status"]).value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        fig_status = px.bar(status_counts, x="status", y="count", title="주문 상태 분포", color="status")
        st.plotly_chart(fig_status, use_container_width=True)

else:
    st.info("조건에 맞는 거래 내역이 없습니다.")

render_floating_chat()
