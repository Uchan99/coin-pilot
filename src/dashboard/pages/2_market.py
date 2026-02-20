import streamlit as st
import plotly.graph_objects as go
import os
import json
import redis
import datetime
from src.dashboard.utils.db_connector import get_data_as_dataframe
from src.dashboard.components.floating_chat import render_floating_chat

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

def get_bot_status(symbol: str) -> dict:
    """
    Redis에서 봇 상태를 조회합니다.
    심볼 형식이 다를 수 있으므로 여러 형식으로 시도합니다.
    - DB: KRW-BTC 또는 BTC-KRW
    - Bot: KRW-BTC
    """
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_timeout=2)

        # 원본 심볼로 먼저 시도
        data = r.get(f"bot:status:{symbol}")
        if data:
            return json.loads(data)

        # 심볼 형식 변환 시도 (BTC-KRW -> KRW-BTC 또는 반대)
        if "-" in symbol:
            parts = symbol.split("-")
            reversed_symbol = f"{parts[1]}-{parts[0]}"
            data = r.get(f"bot:status:{reversed_symbol}")
            if data:
                return json.loads(data)

        return None
    except redis.ConnectionError:
        return None
    except Exception:
        return None


st.title("📈 Market Analysis")

from src.config.strategy import get_config

# 1. 사이드바 컨트롤
st.sidebar.markdown("### Chart Settings")

# 설정 파일 및 DB에서 심볼 목록 로드
config = get_config()
symbols_df = get_data_as_dataframe("SELECT DISTINCT symbol FROM market_data ORDER BY symbol")
db_symbols = symbols_df['symbol'].tolist() if not symbols_df.empty else []

# Config에 정의된 심볼을 우선으로 하고, DB에만 있는 심볼(과거 데이터 등)을 뒤에 추가
symbol_list = config.SYMBOLS + [s for s in db_symbols if s not in config.SYMBOLS]

# 기본값 설정 (KRW-BTC 우선, 없으면 첫 번째)
default_index = 0
if "KRW-BTC" in symbol_list:
    default_index = symbol_list.index("KRW-BTC")

selected_symbol = st.sidebar.selectbox("Select Symbol", symbol_list, index=default_index)
interval_map = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
selected_interval = st.sidebar.selectbox("Interval", list(interval_map.keys()), index=2) # Default 15m
limit = st.sidebar.slider("Candle Limit", 50, 500, 200)

# --- Bot Brain Visualization (Moved here to use selected_symbol) ---
bot_status = get_bot_status(selected_symbol)
with st.expander(f"🤖 Bot Brain: {selected_symbol} (Live Status)", expanded=True):
    if bot_status:
        # 레짐 표시 (v3.0)
        regime = bot_status.get("regime", "UNKNOWN")
        regime_colors = {
            "BULL": "🟢",
            "SIDEWAYS": "🟡",
            "BEAR": "🔴",
            "UNKNOWN": "⚪"
        }
        regime_descriptions = {
            "BULL": "상승장 - 풀백 매수 전략",
            "SIDEWAYS": "횡보장 - Mean Reversion 전략",
            "BEAR": "하락장 - 보수적 진입",
            "UNKNOWN": "데이터 수집 중"
        }
        regime_icon = regime_colors.get(regime, "⚪")
        regime_desc = regime_descriptions.get(regime, "")

        st.markdown(f"### {regime_icon} Market Regime: **{regime}**")
        st.caption(regime_desc)
        st.divider()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Action", bot_status.get("action", "UNKNOWN"))
        with col2:
            indicators = bot_status.get("indicators", {})
            st.metric("RSI (14)", f"{indicators.get('rsi', 0):.1f}")
        with col3:
            # HWM 표시 (트레일링 스탑용)
            hwm = indicators.get('hwm', 0)
            if hwm > 0:
                st.metric("HWM", f"{hwm:,.0f}")
            else:
                st.metric("HWM", "N/A")
        with col4:
            # Freshness
            ts_str = bot_status.get("timestamp")
            if ts_str:
                updated_at = datetime.datetime.fromisoformat(ts_str)
                now = datetime.datetime.now(datetime.timezone.utc)
                age = (now - updated_at).total_seconds()

                status_color = "normal"
                if age > 120: status_color = "off" # 회색 (stale)

                st.metric("Last Update", f"{int(age)}s ago", delta="-Stale" if age > 120 else "Live", delta_color=status_color)

        reason = bot_status.get('reason', 'No reasoning available').replace('\n', '  \n')
        st.info(f"💭 **Reasoning**:\n\n{reason}")
        
    else:
        st.warning(f"⚠️ Bot Status not found for {selected_symbol}")
        st.caption("""
        **가능한 원인:**
        1. 봇이 실행 중이 아님 (`kubectl get pods -l app=bot -n coin-pilot-ns`)
        2. Redis 포트 포워딩 누락 (`kubectl port-forward -n coin-pilot-ns service/redis 6379:6379`)
        3. 봇이 아직 첫 번째 루프를 완료하지 않음 (1분 대기)
        """)


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

render_floating_chat()
