import streamlit as st
import pandas as pd
import plotly.express as px
from src.dashboard.utils.db_connector import get_data_as_dataframe

st.title("📜 Trade History")

# 1. Filters
col1, col2 = st.columns(2)
with col1:
    symbol_filter = st.text_input("Filter by Symbol", placeholder="e.g. BTC-KRW")
with col2:
    side_filter = st.selectbox("Filter by Side", ["All", "BUY", "SELL"])

# 2. Query Construction
base_query = """
    SELECT 
        created_at + interval '9 hours' as created_at, 
        symbol, 
        side, 
        price, 
        quantity, 
        (price * quantity) as total_value,
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

base_query += " ORDER BY created_at DESC LIMIT 100"

df = get_data_as_dataframe(base_query, params)

# 3. Display Data
if not df.empty:
    # 포맷팅
    display_df = df.copy()
    display_df['price'] = pd.to_numeric(display_df['price']).map('{:,.0f}'.format)
    display_df['total_value'] = pd.to_numeric(display_df['total_value']).map('{:,.0f}'.format)
    
    st.dataframe(
        display_df,
        column_config={
            "created_at": "Time",
            "symbol": "Symbol",
            "side": "Side",
            "price": "Price",
            "quantity": "Qty",
            "total_value": "Value (KRW)",
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
