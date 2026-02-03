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

def build_status_reason(indicators: Dict, pos: Dict, config, risk_valid: bool = True, risk_reason: str = None) -> str:
    """
    봇의 판단 근거를 사람이 읽기 쉬운 문장으로 생성합니다.
    통과된 조건도 함께 표시하여 현재 상태를 명확히 파악할 수 있도록 합니다.
    """
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

    # 통과된 조건들을 누적
    passed = []

    # 1. RSI Check (config 기반)
    rsi_threshold = config.RSI_OVERSOLD
    if rsi > rsi_threshold:
        return f"관망 중: RSI({rsi:.1f}) > {rsi_threshold} (과매도 아님)"
    passed.append(f"✓ RSI({rsi:.1f}) < {rsi_threshold}")

    # 2. Trend Check (MA 200)
    if close <= ma_200:
        passed_str = "\n".join(passed) if passed else ""
        return f"진입 대기: 하락 추세 (현재가 {close:,.0f} ≤ MA200 {ma_200:,.0f})\n{passed_str}"
    passed.append(f"✓ 추세(Price > MA200)")

    # 3. Volume Check (config 기반) - BB보다 먼저 체크 (BB는 선택적이므로)
    vol_threshold = config.VOLUME_MULTIPLIER
    if vol_ratio <= vol_threshold:
        passed_str = "\n".join(passed) if passed else ""
        return f"진입 대기: 거래량 부족 (Vol/Avg: {vol_ratio:.2f}x ≤ {vol_threshold}x)\n{passed_str}"
    passed.append(f"✓ 거래량({vol_ratio:.2f}x)")

    # 4. BB Check (선택적 - config.USE_BB_CONDITION이 True인 경우만)
    if config.USE_BB_CONDITION:
        if close > bb_lower:
            passed_str = "\n".join(passed) if passed else ""
            return f"진입 대기: 아직 저점 아님 (현재가 {close:,.0f} > BB하단 {bb_lower:,.0f})\n{passed_str}"
        passed.append(f"✓ BB하단 터치")

    passed_str = "\n".join(passed)
    return f"✅ 진입 조건 충족! AI 검증 대기 중...\n{passed_str}"


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


from src.config.strategy import get_config

async def bot_loop():
    """
    CoinPilot Trading Bot Main Loop (Infinite Daemon) - 멀티 심볼 지원
    
    설정된 모든 코인 심볼에 대해 순차적으로 시장 데이터를 분석하고,
    전략 및 리스크 관리 규칙에 따라 매매를 수행함.
    """
    # 설정 로드 (롤백 모드 지원)
    config = get_config()
    
    # 컴포넌트 초기화 (설정 주입)
    strategy = MeanReversionStrategy(config)   # 매매 전략 (평균 회귀 v2.0)
    executor = PaperTradingExecutor()          # 주문 실행기 (모의 투자)
    risk_manager = RiskManager(config)         # 리스크 관리자 (포트폴리오 리스크 포함)
    
    print(f"[*] CoinPilot Trading Bot Started for {len(config.SYMBOLS)} symbols")
    print(f"[*] Strategy: {strategy.name}")
    print(f"[*] Target Symbols: {config.SYMBOLS}")
    
    while not SHUTDOWN:
        loop_start_time = time.time()
        
        try:
            async with get_db_session() as session:
                # -----------------------------------------------------------
                # Step 0. 전역 상태 및 메트릭 업데이트
                # -----------------------------------------------------------
                # 일일 리스크 상태(PnL 등) 조회 및 메트릭 반영
                risk_state = await risk_manager.get_daily_state(session)
                metrics.total_pnl.set(float(risk_state.total_pnl))
                
                # 전체 활성 포지션 수 조회 (메트릭용)
                open_positions_count = await risk_manager.count_open_positions(session)
                metrics.active_positions.set(open_positions_count)

                # Redis 클라이언트 초기화 (상태 전송용)
                try:
                    redis_client = await get_redis_client()
                except Exception as e:
                    print(f"[!] Redis Init Error: {e}")
                    redis_client = None

                # ========== 멀티 심볼 반복 처리 ==========
                for symbol in config.SYMBOLS:
                    try:
                        # -----------------------------------------------------------
                        # Step 1. Market Data Fetching
                        # -----------------------------------------------------------
                        df = await get_recent_candles(session, symbol)
                        
                        # 데이터 부족 시 스킵
                        if len(df) < 200:
                            # 잦은 로그 방지를 위해 print는 생략하거나 조건부 출력
                            # print(f"[-] {symbol}: Not enough data ({len(df)} < 200). Waiting...")
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
                            continue

                        # 데이터 신선도 체크 (2분 이상 지연되면 경고)
                        last_ts = df.iloc[-1]["timestamp"]
                        now = datetime.now(timezone.utc)
                        if (now - last_ts) > timedelta(minutes=2):
                            # print(f"[!] {symbol}: Data stale. Last candle: {last_ts.isoformat()}")
                            continue

                        # -------------------------------------------------------
                        # Step 2. Market Analysis (지표 계산)
                        # -------------------------------------------------------
                        indicators = get_all_indicators(df)
                        current_price = Decimal(str(indicators["close"]))
                        
                        # -------------------------------------------------------
                        # Step 3. Position & Signal Check
                        # -------------------------------------------------------
                        pos = await executor.get_position(session, symbol)
                        
                        # [Redis Status Update 준비]
                        bot_action = "HOLD"
                        bot_reason = ""
                        
                        if pos:
                            # [Case A] 포지션 보유 중 -> 청산(Exit) 체크
                            bot_action = "HOLD (POS)"
                            should_exit, exit_reason = strategy.check_exit_signal(indicators, pos)
                            
                            if should_exit:
                                bot_action = "SELL"
                                print(f"[{symbol}] Exit Triggered: {exit_reason}")
                                success = await executor.execute_order(
                                    session, symbol, "SELL", 
                                    current_price, pos["quantity"], 
                                    strategy.name, 
                                    {"reason": exit_reason, "indicators": indicators}
                                )
                                if success:
                                    # 리스크 상태 업데이트 (PnL 반영)
                                    pnl = (current_price - pos["avg_price"]) * pos["quantity"]
                                    await risk_manager.update_after_trade(session, pnl)
                                    print(f"[+] {symbol} Trade Closed. PnL: {pnl:,.0f} KRW")
                                    metrics.trade_count.inc()
                            
                            bot_reason = build_status_reason(indicators, pos, config)

                        else:
                            # [Case B] 포지션 미보유 -> 진입(Entry) 체크
                            if strategy.check_entry_signal(indicators):
                                print(f"[{symbol}] Entry Signal Detected!")
                                
                                # 리스크 관리 검증
                                balance = await executor.get_balance(session)
                                invest_amount = balance * risk_manager.max_per_order
                                
                                is_valid, risk_reason = await risk_manager.check_order_validity(
                                    session, symbol, invest_amount
                                )
                                
                                if is_valid:
                                    bot_action = "BUY"
                                    # 수량 계산 (투자금 / 현재가)
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
                                        metrics.trade_count.inc()
                                else:
                                    # 리스크 관리로 인한 거부
                                    bot_action = "SKIP"
                                    bot_reason = f"Risk Rejected: {risk_reason}"
                                    print(f"[-] {symbol} Order Skipped: {risk_reason}")
                            else:
                                # 시그널 없음
                                bot_reason = build_status_reason(indicators, None, config)

                        # [Redis Status Update 실행]
                        if redis_client:
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
                                    "quantity": float(pos["quantity"]) if pos else None,
                                    "pnl_pct": float((current_price - pos["avg_price"])/pos["avg_price"]*100) if pos else 0.0
                                },
                                "action": bot_action,
                                "reason": bot_reason
                            }
                            try:
                                await redis_client.set(f"bot:status:{symbol}", json.dumps(status_data), ex=300)
                            except Exception:
                                pass

                    except Exception as e_sym:
                        # 특정 심볼 처리 중 에러가 발생해도 다른 심볼은 계속 처리
                        print(f"[!] Error processing {symbol}: {e_sym}")
                        import traceback
                        traceback.print_exc()

        except Exception as e:
            print(f"[!] Critical Bot Loop Error: {e}")
            import traceback
            traceback.print_exc()
        
        if SHUTDOWN:
            break
            
        elapsed = time.time() - loop_start_time
        sleep_time = max(10, 60 - elapsed) # 최소 10초는 대기 보장
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
