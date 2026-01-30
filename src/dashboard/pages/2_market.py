import streamlit as st
import plotly.graph_objects as go
import os
import json
import redis
import datetime
from src.dashboard.utils.db_connector import get_data_as_dataframe

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

def get_bot_status(symbol: str) -> dict:
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        data = r.get(f"bot:status:{symbol}")
        return json.loads(data) if data else None
    except:
        return None


st.title("📈 Market Analysis")

# 1. 사이드바 컨트롤
st.sidebar.markdown("### Chart Settings")

# models.py: MarketData table uses 'symbol' column
symbols_df = get_data_as_dataframe("SELECT DISTINCT symbol FROM market_data ORDER BY symbol")
symbol_list = symbols_df['symbol'].tolist() if not symbols_df.empty else ["BTC-KRW", "ETH-KRW", "XRP-KRW"]

selected_symbol = st.sidebar.selectbox("Select Symbol", symbol_list)
interval_map = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
selected_interval = st.sidebar.selectbox("Interval", list(interval_map.keys()), index=2) # Default 15m
limit = st.sidebar.slider("Candle Limit", 50, 500, 200)

# --- Bot Brain Visualization (Moved here to use selected_symbol) ---
bot_status = get_bot_status(selected_symbol)
with st.expander(f"🤖 Bot Brain: {selected_symbol} (Live Status)", expanded=True):
    if bot_status:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Action", bot_status.get("action", "UNKNOWN"))
        with col2:
            indicators = bot_status.get("indicators", {})
            st.metric("RSI (14)", f"{indicators.get('rsi', 0):.1f}")
        with col3:
            # Freshness
            ts_str = bot_status.get("timestamp")
            if ts_str:
                updated_at = datetime.datetime.fromisoformat(ts_str)
                now = datetime.datetime.now(datetime.timezone.utc)
                age = (now - updated_at).total_seconds()
                
                status_color = "normal"
                if age > 120: status_color = "off" # 회색 (stale)
                
                st.metric("Last Update", f"{int(age)}s ago", delta="-Stale" if age > 120 else "Live", delta_color=status_color)
        
        st.info(f"💭 **Reasoning**: {bot_status.get('reason', 'No reasoning available')}")
        
    else:
        st.warning(f"⚠️ Bot Status not found for {selected_symbol}. Is the bot running?")


# 2. 데이터 조회
# models.py columns: open_price, high_price, low_price, close_price, volume
query = f"""
    SELECT 
        time_bucket('{selected_interval}', timestamp) + interval '9 hours' as bucket,
        FIRST(open_price, timestamp) as open,
        MAX(high_price) as high,
        MIN(low_price) as low,
        LAST(close_price, timestamp) as close,
        SUM(volume) as volume
    FROM market_data
    WHERE symbol = :symbol
    GROUP BY bucket
    ORDER BY bucket DESC
    LIMIT :limit
"""

df_candles = get_data_as_dataframe(query, {"symbol": selected_symbol, "limit": limit})

# 3. 차트 그리기
if not df_candles.empty:
    # 시간순 정렬 (과거 -> 현재) for plotting
    df_candles = df_candles.sort_values('bucket')
    
    fig = go.Figure(data=[go.Candlestick(
        x=df_candles['bucket'],
        open=df_candles['open'],
        high=df_candles['high'],
        low=df_candles['low'],
        close=df_candles['close'],
        name=selected_symbol
    )])

    fig.update_layout(
        title=f"{selected_symbol} ({selected_interval})",
        yaxis_title="Price (KRW)",
        xaxis_title="Time",
        template="plotly_dark",
        height=600
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 4. 최근 데이터 표시
    last_candle = df_candles.iloc[-1]
    st.metric(
        label=f"Current Price ({last_candle['bucket']})", 
        value=f"{last_candle['close']:,.0f} KRW",
        delta=f"H: {last_candle['high']:,.0f} / L: {last_candle['low']:,.0f}"
    )

else:
    st.warning(f"No data found for {selected_symbol}. Collector가 켜져 있는지 확인하세요.")
    st.code("kubectl get pods -l app=collector", language="bash")
