import streamlit as st
import pandas as pd
from src.dashboard.utils.db_connector import get_data_as_dataframe

st.title("📊 Overview")

# 1. Total Asset & PnL
# AccountState: 현재 잔고 (Paper Trading)
# DailyRiskState: 일별 손익 (Total PnL 계산용)
# TradingHistory: 거래 횟수

# 1-1. Balance
balance_df = get_data_as_dataframe("SELECT balance FROM account_state ORDER BY updated_at DESC LIMIT 1")
current_balance = float(balance_df.iloc[0]['balance']) if not balance_df.empty else 0.0

# 1-2. Total PnL (누적 손익)
pnl_df = get_data_as_dataframe("SELECT SUM(total_pnl) as cum_pnl FROM daily_risk_state")
total_pnl = float(pnl_df.iloc[0]['cum_pnl']) if not pnl_df.empty and pnl_df.iloc[0]['cum_pnl'] is not None else 0.0

# 1-3. Total Trades
trades_df = get_data_as_dataframe("SELECT COUNT(*) as cnt FROM trading_history WHERE status = 'FILLED'")
total_trades = int(trades_df.iloc[0]['cnt']) if not trades_df.empty else 0

# 1-4. Win Rate (추정)
# models.py에는 승/패 여부를 직접 저장하는 컬럼이 없음 (DailyRiskState에 'consecutive_losses'만 있음)
# 정확한 승률 계산을 위해서는 TradingHistory를 분석해야 하나, 현재는 DailyRiskState의 'trade_count' 대비 이익일수 등을 봐야 함.
# 임시로 '오늘의 승률' 또는 '단순 표시'로 대체하거나, 추후 TradingHistory 분석 로직 추가 필요.
# 여기서는 N/A로 표시하고 추후 고도화.
win_rate = 0.0 

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="Total Trades", value=f"{total_trades}회")

with col2:
    st.metric(label="Win Rate", value="N/A", help="승률 데이터는 추후 고도화 예정")

with col3:
    st.metric(label="Total PnL", value=f"{total_pnl:,.0f} KRW", 
              delta=f"{total_pnl:,.0f} KRW", delta_color="normal")

with col4:
    st.metric(label="Current Balance", value=f"{current_balance:,.0f} KRW")

st.markdown("---")

# 2. Active Positions
st.subheader("Holdings (Active Positions)")

# Position 테이블 구조: symbol, quantity, avg_price, opened_at, updated_at
# market_data 테이블에서 최신 현재가(close_price)를 가져와서 조인해야 정확한 미실현손익 계산 가능
# 하지만 단순화를 위해 현재는 positions 테이블만 보여주고, 현재가는 market_data의 최신값으로 별도 조회하거나 생략.

query_positions = """
    SELECT 
        p.symbol, 
        p.side, 
        p.quantity, 
        p.avg_price, 
        m.close_price as current_price
    FROM positions p
    LEFT JOIN (
        SELECT DISTINCT ON (symbol) symbol, close_price 
        FROM market_data 
        ORDER BY symbol, timestamp DESC
    ) m ON p.symbol = m.symbol
"""
# 주의: positions 테이블에 'side' 컬럼이 models.py에는 안 보였음. 확인 필요.
# models.py의 Position 클래스: symbol, quantity, avg_price (side 없음, 보통 Long Only면 생략 가능)
# models.py 다시 보니 side 없음. Long Only 가정.

query_positions_fixed = """
    SELECT 
        p.symbol, 
        p.quantity, 
        p.avg_price, 
        m.close_price as current_price
    FROM positions p
    LEFT JOIN (
        SELECT DISTINCT ON (symbol) symbol, close_price 
        FROM market_data 
        ORDER BY symbol, timestamp DESC
    ) m ON p.symbol = m.symbol
"""

positions_df = get_data_as_dataframe(query_positions_fixed)

if not positions_df.empty:
    display_df = positions_df.copy()
    
    # PnL 계산
    display_df['current_price'] = pd.to_numeric(display_df['current_price'])
    display_df['avg_price'] = pd.to_numeric(display_df['avg_price'])
    display_df['unrealized_pnl_pct'] = (display_df['current_price'] - display_df['avg_price']) / display_df['avg_price'] * 100
    
    # 포맷팅
    display_df['unrealized_pnl_pct'] = display_df['unrealized_pnl_pct'].map('{:,.2f}%'.format)
    display_df['avg_price'] = display_df['avg_price'].map('{:,.0f}'.format)
    display_df['current_price'] = display_df['current_price'].map('{:,.0f}'.format)
    
    st.dataframe(
        display_df,
        column_config={
            "symbol": "Symbol",
            "quantity": "Qty",
            "avg_price": "Avg Price",
            "current_price": "Cur Price",
            "unrealized_pnl_pct": "P&L (%)"
        },
        width="stretch",
        hide_index=True
    )
else:
    st.info("현재 보유 중인 포지션이 없습니다. (No Active Positions)")
