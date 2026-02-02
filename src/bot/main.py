import asyncio
import time
import signal
import os
import sys
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
import pandas as pd
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_client import make_asgi_app
import uvicorn

from sqlalchemy import select, desc

# Add project root to path
sys.path.append(os.getcwd())

from src.common.db import get_db_session, get_redis_client
from src.common.models import MarketData
from src.common.indicators import get_all_indicators
from src.engine.strategy import MeanReversionStrategy
from src.engine.executor import PaperTradingExecutor
from src.engine.risk_manager import RiskManager
from src.utils.metrics import metrics

# Graceful Shutdown Handler
SHUTDOWN = False

def handle_sigterm(signum, frame):
    global SHUTDOWN
    print(f"[*] Signal {signum} received. Initiating graceful shutdown...")
    SHUTDOWN = True

# Register signals
signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

def build_status_reason(indicators: Dict, pos: Dict, risk_valid: bool = True, risk_reason: str = None) -> str:
    """봇의 판단 근거를 사람이 읽기 쉬운 문장으로 생성합니다."""
    if pos:
        pnl_pct = (indicators["close"] - pos["avg_price"]) / pos["avg_price"] * 100
        return f"포지션 보유 중 (수익률: {pnl_pct:.2f}%) - 매도 조건 감시 중"
    
    if not risk_valid:
        return f"진입 보류: {risk_reason}"

    # 전략 조건 상세 분석
    rsi = indicators.get("rsi", 0)
    ma_200 = indicators.get("ma_200", 0)
    bb_lower = indicators.get("bb_lower", 0)
    vol_ratio = indicators.get("vol_ratio", 0)
    close = indicators.get("close", 0)

    # 데이터 부족 체크
    if ma_200 == 0 or bb_lower == 0:
        return "데이터 수집 중: 지표 계산 대기 (200봉 필요)"

    # 1. RSI Check
    if rsi > 30:
        return f"관망 중: RSI({rsi:.1f}) > 30 (과매도 아님)"

    # 2. Trend Check (MA 200)
    if close <= ma_200:
        return f"진입 대기: 하락 추세 (현재가 {close:,.0f} ≤ MA200 {ma_200:,.0f})"

    # 3. BB Check
    if close > bb_lower:
        return f"진입 대기: 아직 저점 아님 (현재가 {close:,.0f} > BB하단 {bb_lower:,.0f})"

    # 4. Volume Check
    if vol_ratio <= 1.5:
        return f"진입 대기: 거래량 부족 (Vol/Avg: {vol_ratio:.2f}x ≤ 1.5x)"

    return "✅ 진입 조건 충족! AI 검증 대기 중..."


async def get_recent_candles(session, symbol: str, limit: int = 200) -> pd.DataFrame:
    """
    DB에서 최근 캔들 데이터를 조회하여 DataFrame으로 변환합니다.
    """
    start_time = time.time()
    try:
        # 1. DB 조회 (최신순 정렬)
        stmt = select(MarketData).where(
            MarketData.symbol == symbol
        ).order_by(desc(MarketData.timestamp)).limit(limit)
        
        result = await session.execute(stmt)
        rows = result.scalars().all()
        
        if not rows:
            return pd.DataFrame()
            
        # 2. 데이터 변환 및 정렬 (최신순 -> 과거순)
        data = [{
            "timestamp": r.timestamp.replace(tzinfo=timezone.utc) if r.timestamp.tzinfo is None else r.timestamp,
            "open": float(r.open_price),
            "high": float(r.high_price),
            "low": float(r.low_price),
            "close": float(r.close_price),
            "volume": float(r.volume)
        } for r in reversed(rows)]
        
        return pd.DataFrame(data)
    finally:
        # API Latency Metric Update
        latency = time.time() - start_time
        metrics.api_latency.observe(latency)


async def bot_loop():
    """
    CoinPilot Trading Bot Main Loop (Infinite Daemon)
    """
    symbol = "KRW-BTC"
    
    # 컴포넌트 초기화
    strategy = MeanReversionStrategy()   # 매매 전략 (평균 회귀)
    executor = PaperTradingExecutor()    # 주문 실행기 (모의 투자)
    risk_manager = RiskManager()         # 리스크 관리자 (자금 관리 및 보호)
    
    print(f"[*] CoinPilot Trading Bot Started for {symbol}")
    print(f"[*] Strategy: {strategy.name}")
    
    while not SHUTDOWN:
        loop_start_time = time.time()
        
        try:
            async with get_db_session() as session:
                # -----------------------------------------------------------
                # Step 0. Update Metrics (PnL, Position)
                # -----------------------------------------------------------
                # 현재 PnL 상태 업데이트
                risk_state = await risk_manager.get_daily_state(session)
                metrics.total_pnl.set(float(risk_state.total_pnl))
                
                # 활성 포지션 확인
                pos = await executor.get_position(session, symbol)
                if pos:
                    metrics.active_positions.set(1)
                else:
                    metrics.active_positions.set(0)

                # Volatility Index (Redis에서 가져와서 업데이트)
                vol_mult = await risk_manager.get_volatility_multiplier() # 0.5 or 1.0
                # 역으로 추산하거나 Redis 직접 조회 필요하지만, 여기선 multiplier로 간접 유추
                # 정확한 값은 VolatilityModel이 업데이트 해야 함.

                # -----------------------------------------------------------
                # Step 1. Market Data Fetching
                # -----------------------------------------------------------
                df = await get_recent_candles(session, symbol)
                
                # Redis 클라이언트 초기화
                try:
                    redis_client = await get_redis_client()
                except Exception as e:
                    print(f"[!] Redis Init Error: {e}")
                    redis_client = None

                # 데이터 부족 시 대기
                if len(df) < 200:
                    msg = f"[-] Not enough data ({len(df)} < 200). Waiting for collector..."
                    print(msg)
                    if redis_client:
                        try:
                            status_data = {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "symbol": symbol,
                                "action": "WAITING",
                                "reason": f"데이터 부족: {len(df)} lines",
                                "indicators": {}
                            }
                            await redis_client.set(f"bot:status:{symbol}", json.dumps(status_data), ex=300)
                        except Exception:
                            pass
                else:
                    # 데이터 신선도 체크
                    last_ts = df.iloc[-1]["timestamp"]
                    now = datetime.now(timezone.utc)
                    
                    if (now - last_ts) > timedelta(minutes=2):
                        msg = f"[!] Data stale. Last candle: {last_ts.isoformat()}."
                        print(msg)
                    else:
                        # -------------------------------------------------------
                        # Step 2. Market Analysis
                        # -------------------------------------------------------
                        indicators = get_all_indicators(df)
                        current_price = Decimal(str(indicators["close"]))
                        
                        # -------------------------------------------------------
                        # Step 3. Position & Signal Check
                        # -------------------------------------------------------
                        pos = await executor.get_position(session, symbol)
                        
                        # Redis Status Update
                        if redis_client:
                            bot_action = "HOLD"
                            bot_reason = ""
                            risk_valid_flag = True
                            risk_reason_msg = None

                            if not pos:
                                balance = await executor.get_balance(session)
                                invest_amount = balance * risk_manager.max_per_order
                                is_valid, method_reason = await risk_manager.check_order_validity(session, symbol, invest_amount)
                                if not is_valid:
                                    risk_valid_flag = False
                                    risk_reason_msg = method_reason
                                    
                            bot_reason = build_status_reason(indicators, pos, risk_valid_flag, risk_reason_msg)
                            
                            status_data = {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "symbol": symbol,
                                "current_price": float(current_price),
                                "indicators": {
                                    "rsi": float(indicators.get("rsi", 0)),
                                    "bb_upper": float(indicators.get("bb_upper", 0)),
                                    "bb_lower": float(indicators.get("bb_lower", 0)),
                                    "ma_200": float(indicators.get("ma_200", 0))
                                },
                                "position": {
                                    "has_position": bool(pos),
                                    "avg_price": float(pos["avg_price"]) if pos else None,
                                    "quantity": float(pos["quantity"]) if pos else None
                                },
                                "action": bot_action,
                                "reason": bot_reason
                            }
                            try:
                                await redis_client.set(f"bot:status:{symbol}", json.dumps(status_data), ex=300)
                            except Exception:
                                pass
                        
                        if pos:
                            # [Case A] 포지션 보유 -> 청산 체크
                            should_exit, exit_reason = strategy.check_exit_signal(indicators, pos)
                            
                            if should_exit:
                                print(f"[Signal] Exit Triggered: {exit_reason}")
                                success = await executor.execute_order(
                                    session, symbol, "SELL", 
                                    current_price, pos["quantity"], 
                                    strategy.name, 
                                    {"reason": exit_reason, "indicators": indicators}
                                )
                                if success:
                                    avg_price = pos["avg_price"]
                                    quantity = pos["quantity"]
                                    pnl = (current_price - avg_price) * quantity
                                    await risk_manager.update_after_trade(session, pnl)
                                    print(f"[+] Risk Manager Updated. PnL: {pnl:,.0f} KRW")
                                    
                                    # Trade Count Metric Increment
                                    metrics.trade_count.inc()

                        else:
                            # [Case B] 미보유 -> 진입 체크
                            if strategy.check_entry_signal(indicators):
                                print(f"[Signal] Entry Triggered!")
                                balance = await executor.get_balance(session)
                                invest_amount = balance * risk_manager.max_per_order
                                
                                is_valid, risk_reason = await risk_manager.check_order_validity(session, symbol, invest_amount)
                                
                                if not is_valid:
                                    print(f"[-] Order Skipped by Risk Manager: {risk_reason}")
                                else:
                                    quantity = invest_amount / current_price
                                    if quantity > 0:
                                        market_context = df.tail(10).to_dict(orient="records")
                                        signal_info = {
                                            **indicators,
                                            "market_context": market_context
                                        }
                                        await executor.execute_order(
                                            session, symbol, "BUY", 
                                            current_price, quantity, 
                                            strategy.name, 
                                            signal_info
                                        )
                                        # Trade execution is tracked by executor, but we can inc trade_count here if successful? 
                                        # Actually execution might fail. Let's assume execute_order returns success/fail if updated to do so. 
                                        # But currently it returns None or awaits.
                                        # For BUY, we just trigger.
                                        metrics.trade_count.inc()

        except Exception as e:
            print(f"[!] Critical Bot Error: {e}")
            import traceback
            traceback.print_exc()
        
        if SHUTDOWN:
            break
            
        elapsed = time.time() - loop_start_time
        sleep_time = max(0, 60 - elapsed)
        await asyncio.sleep(sleep_time)

    print("[*] Bot Loop Terminated Gracefully.")

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.analytics.volatility_model import VolatilityModel

# ... existing code ...

async def retrain_volatility_job():
    """
    일일 변동성 모델 재학습 작업
    """
    print("[Scheduler] Starting Daily Volatility Model Retraining...")
    symbol = "KRW-BTC"
    try:
        async with get_db_session() as session:
            # 1. 데이터 조회 (최근 1000개 정도? GARCH 학습용)
            df = await get_recent_candles(session, symbol, limit=1000)
            if len(df) < 500:
                print(f"[Scheduler] Not enough data for training ({len(df)})")
                return

            # 2. 모델 학습
            model = VolatilityModel()
            
            # GARCH fitting
            vol = model.fit_predict(df['close'])
            is_high = vol > 2.0
            
            # 3. 상태 업데이트
            model.update_volatility_state(vol, threshold=2.0)
            print(f"[Scheduler] Retraining Complete. High Volatility: {is_high} (Vol: {vol:.4f})")
            
    except Exception as e:
        print(f"[Scheduler] Retraining Failed: {e}")

# FastAPI App Setup for Health & Metrics
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Scheduler Setup
    scheduler = AsyncIOScheduler()
    # 매일 00:05 UTC에 실행
    scheduler.add_job(retrain_volatility_job, 'cron', hour=0, minute=5, timezone=timezone.utc)
    scheduler.start()
    print("[*] Scheduler started.")
    
    # Startup Bot Loop
    task = asyncio.create_task(bot_loop())
    yield
    # Shutdown
    global SHUTDOWN
    SHUTDOWN = True
    scheduler.shutdown()
    await task

app = FastAPI(lifespan=lifespan)
# ...

# Add Prometheus Metrics Endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

if __name__ == "__main__":
    # 봇 서비스 포트는 8000 (monitoring config와 일치)
    uvicorn.run(app, host="0.0.0.0", port=8000)
