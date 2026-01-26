import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import asyncio
import os
from sqlalchemy import select, desc
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.common.db import DATABASE_URL  # Import DATABASE_URL instead of get_db_session
from src.common.models import AgentDecision, MarketData, TradingHistory

# 대시보드 전용 DB 설정 (NullPool 사용으로 Loop 충돌 방지)
dashboard_engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
    echo=False
)

async_session_dashboard = async_sessionmaker(
    bind=dashboard_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 비동기 DB 조회를 위한 헬퍼 함수
async def get_recent_decisions(limit=10):
    async with async_session_dashboard() as session:
        stmt = select(AgentDecision).order_by(desc(AgentDecision.created_at)).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

async def get_market_data(symbol="KRW-BTC", limit=100):
    async with async_session_dashboard() as session:
        stmt = select(MarketData).where(
            MarketData.symbol == symbol, 
            MarketData.interval == "1m"
        ).order_by(desc(MarketData.timestamp)).limit(limit)
        result = await session.execute(stmt)
        data = result.scalars().all()
        return sorted(data, key=lambda x: x.timestamp)

def run_async(coroutine):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coroutine)

import subprocess

# 사이드바 설정
st.sidebar.header("Controls")
if st.sidebar.button("Run Simulation"):
    with st.spinner("Running AI Simulation..."):
        result = subprocess.run(
            [".venv/bin/python", "scripts/simulate_with_ai.py"],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": "."}
        )
        
    if result.returncode == 0:
        st.sidebar.success("Simulation Completed!")
    else:
        st.sidebar.error(f"Error: {result.stderr}")

# 메인 레이아웃
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📈 Market Chart (KRW-BTC)")
    
    # 데이터 조회
    market_data = run_async(get_market_data())
    
    if market_data:
        df = pd.DataFrame([{
            "timestamp": d.timestamp,
            "open": float(d.open_price),
            "high": float(d.high_price),
            "low": float(d.low_price),
            "close": float(d.close_price),
            "volume": float(d.volume)
        } for d in market_data])
        
        # User requested KST conversion for display
        # DB is UTC. We convert to 'Asia/Seoul'
        if df['timestamp'].dt.tz is None:
             # Fallback if naive: assume UTC then convert
             df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
             
        df['timestamp_kst'] = df['timestamp'].dt.tz_convert('Asia/Seoul')
        
        # 캔들스틱 차트
        fig = go.Figure(data=[go.Candlestick(
            x=df['timestamp_kst'], # Use KST
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close']
        )])
        
        fig.update_layout(
            height=500, 
            margin=dict(l=20, r=20, t=20, b=20),
            title="KRW-BTC (KST)",
            xaxis_rangeslider_visible=False
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No market data found.")

with col2:
    st.subheader("🧠 AI Decisions")
    
    # AI 결정 조회
    decisions = run_async(get_recent_decisions())
    
    if decisions:
        for d in decisions:
            color = "green" if d.decision in ["CONFIRM", "SAFE"] else "red"
            with st.container(border=True):
                st.markdown(f"**[{d.decision}]** {d.symbol} - {d.strategy_name}")
                st.caption(f"{d.created_at.strftime('%H:%M:%S')} | Confidence: {d.confidence or 'N/A'}")
                st.write(d.reasoning)
    else:
        st.info("No AI decisions recorded yet.")

# 하단: 거래 이력
st.subheader("📝 Recent Trades")
# (추후 TradingHistory 연동 가능)
st.info("Trading history implementation coming soon.")
