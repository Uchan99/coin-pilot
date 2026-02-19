import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.dashboard.utils.db_connector import get_data_as_dataframe

st.title("🛡️ Risk Monitor")

# Week 6 목표: "손절 한도", "거래 횟수 제한" 등 리스크 규칙 준수 여부 시각화

# 1. Daily Risk State 조회 (오늘 날짜 기준)
# models.py: daily_risk_state
# (date, total_pnl, buy_count, sell_count, trade_count, consecutive_losses, is_trading_halted)
risk_df = get_data_as_dataframe("SELECT * FROM daily_risk_state ORDER BY date DESC LIMIT 1")

# 기본값 설정
current_loss_pct = 0.0
current_pnl = 0.0
trade_count = 0
buy_count = 0
sell_count = 0
consecutive_losses = 0
is_halted = False
loss_limit = -5.0 # -5%
trade_limit = 10  # 10회

if not risk_df.empty:
    row = risk_df.iloc[0]
    # 손실률 계산 (총 자산 대비 비율이 필요하나, 여기서는 단순 PnL을 1억 원 기준 예시로 계산하거나
    # 실제로는 RiskManager가 계산한 %를 저장해야 함. 현재는 PnL 금액만 있음)
    # 임시: PnL이 -500,000원이면 -5%라고 가정 (자산 1000만원 기준)
    # 정확히는 account_state와 연동해야 하지만, 시각화를 위해 PnL 그대로 사용하거나 가정치 사용.
    # 여기서는 "PnL 값" 자체를 보여주겠습니다.
    
    current_pnl = float(row['total_pnl'])
    trade_count = int(row['trade_count'])
    buy_count = int(row['buy_count']) if 'buy_count' in row else 0
    sell_count = int(row['sell_count']) if 'sell_count' in row else 0
    consecutive_losses = int(row['consecutive_losses'])
    is_halted = bool(row['is_trading_halted'])

st.subheader("Daily Limits Status")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 📉 Daily Loss Limit")
    # 게이지 차트 (Plotly Indicator)
    fig_loss = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = current_pnl,
        title = {'text': "Today PnL (KRW)"},
        gauge = {
            'axis': {'range': [-1000000, 1000000]}, # 예시 범위
            'bar': {'color': "red" if current_pnl < 0 else "green"},
            'steps': [
                {'range': [-1000000, -500000], 'color': "lightpink"}, # 위험 구간
                {'range': [-500000, 1000000], 'color': "lightgreen"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': -500000 # -5% 가정 (예: 50만원)
            }
        }
    ))
    fig_loss.update_layout(height=300)
    st.plotly_chart(fig_loss, use_container_width=True)
    
    if current_pnl <= -500000: # 예시 한도
        st.error("🚨 Daily Loss Limit Reached! (Trading Halted)")

with col2:
    st.markdown("#### 🔢 Daily Buy Count")
    # Progress Bar로 표현
    # 리스크 제한은 BUY 기준
    progress = min(buy_count / trade_limit, 1.0)
    st.progress(progress)
    st.metric("Buy Count", f"{buy_count} / {trade_limit}")
    
    if buy_count >= trade_limit:
        st.warning("⚠️ Max Buy Count Reached")

st.markdown("#### 📊 Fill Counts (Today)")
col_fill1, col_fill2, col_fill3 = st.columns(3)
total_fills = buy_count + sell_count
with col_fill1:
    st.metric("BUY Fills", f"{buy_count}")
with col_fill2:
    st.metric("SELL Fills", f"{sell_count}")
with col_fill3:
    st.metric("Total Fills", f"{total_fills}")

if trade_count != total_fills:
    st.warning(
        f"Trade count mismatch detected: trade_count={trade_count}, "
        f"buy_count+sell_count={total_fills}"
    )

st.markdown("---")

# 2. Cooldown & Halt Status
st.subheader("System Constraints")
col3, col4 = st.columns(2)

with col3:
    st.metric("Consecutive Losses", f"{consecutive_losses}회", 
              help="3연패 시 쿨다운 발동")
    if consecutive_losses >= 3:
        st.error("🧊 Cooldown Active (3 Consecutive Losses)")

with col4:
    status_icon = "🔴" if is_halted else "🟢"
    status_text = "HALTED" if is_halted else "RUNNING"
    st.metric("Trading Status", f"{status_icon} {status_text}")

st.markdown("---")

# 3. Risk Audit Logs (최근 리스크 이벤트)
st.subheader("📜 Risk Log History")
audit_df = get_data_as_dataframe("""
    SELECT timestamp + interval '9 hours' as timestamp, violation_type, description
    FROM risk_audit
    ORDER BY timestamp DESC
    LIMIT 20
""")

if not audit_df.empty:
    st.dataframe(audit_df, use_container_width=True)
else:
    st.info("Risk 이벤트 기록이 없습니다. (Clean!)")
