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
from sqlalchemy import select, desc

# Add project root to path
sys.path.append(os.getcwd())

from src.common.db import get_db_session, get_redis_client
from src.common.models import MarketData
from src.common.indicators import get_all_indicators
from src.engine.strategy import MeanReversionStrategy
from src.engine.executor import PaperTradingExecutor
from src.engine.risk_manager import RiskManager

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

    rsi = indicators.get("rsi", 0)
    if rsi > 30:
        return f"관망 중: RSI({rsi:.1f}) > 30 (과매도 아님)"
    
    return "진입 조건 충족! AI 검증 대기 중..."


async def get_recent_candles(session, symbol: str, limit: int = 200) -> pd.DataFrame:
    """
    DB에서 최근 캔들 데이터를 조회하여 DataFrame으로 변환합니다.
    
    [Architecture Note]
    - DB에는 최신 데이터가 쌓여있지만, 지표 계산 라이브러리(pandas-ta)는 과거->현재 순서의 시계열 데이터를 필요로 합니다.
    - 따라서 DB에서는 'Timestamp 내림차순(최신순)'으로 빠르게 N개를 가져온 후,
      Python 레벨에서 다시 'reversed(오름차순)'하여 DataFrame을 생성합니다.
      
    Args:
        session: SQLAlchemy AsyncSession
        symbol: 조회할 코인 심볼 (예: KRW-BTC)
        limit: 조회할 캔들 개수 (기본 200개 - MA200 계산 최소 요건)
    """
    # 1. DB 조회 (최신순 정렬)
    stmt = select(MarketData).where(
        MarketData.symbol == symbol
    ).order_by(desc(MarketData.timestamp)).limit(limit)
    
    result = await session.execute(stmt)
    rows = result.scalars().all()
    
    if not rows:
        return pd.DataFrame()
        
    # 2. 데이터 변환 및 정렬 (최신순 -> 과거순)
    # 지표 계산의 정확성을 위해 반드시 시간 순서대로 정렬되어야 합니다.
    data = [{
        "timestamp": r.timestamp.replace(tzinfo=timezone.utc) if r.timestamp.tzinfo is None else r.timestamp,
        "open": float(r.open_price),
        "high": float(r.high_price),
        "low": float(r.low_price),
        "close": float(r.close_price),
        "volume": float(r.volume)
    } for r in reversed(rows)]
    
    return pd.DataFrame(data)

async def bot_loop():
    """
    CoinPilot Trading Bot Main Loop (Infinite Daemon)
    
    [Core Philosophy: Reaction over Prediction]
    이 봇은 미래 가격을 예측하지 않습니다. 
    1분마다 시장의 현재 상태(RSI, 볼린저밴드 등)를 확인하고, 
    미리 정의된 규칙(Rule)에 따라 기계적으로 반응합니다.
    
    [Flow]
    1. Data Fetch: 수집기가 저장한 최신 1분봉 데이터 조회
    2. Analyze: 기술적 지표(Technical Indicators) 계산
    3. Signal Check:
       - 보유 중이면? -> 청산(Exit) 조건 확인 (익절/손절/시간만료)
       - 미보유면? -> 진입(Entry) 조건 확인 (과매도 반등 등)
    4. Execution:
       - 진입 시 Risk Manager가 자금 관리(Position Sizing) 수행
       - 최종 주문 전 AI Agent(LLM)가 2차 검증 수행 (False Positive 필터링)
    """
    symbol = "KRW-BTC"
    
    # 컴포넌트 초기화
    strategy = MeanReversionStrategy()   # 매매 전략 (평균 회귀)
    executor = PaperTradingExecutor()    # 주문 실행기 (모의 투자)
    risk_manager = RiskManager()         # 리스크 관리자 (자금 관리 및 보호)
    
    print(f"[*] CoinPilot Trading Bot Started for {symbol}")
    print(f"[*] Strategy: {strategy.name}")
    print(f"[*] Press Ctrl+C to stop.")
    
    while not SHUTDOWN:
        loop_start_time = time.time()
        
        try:
            async with get_db_session() as session:
                # -----------------------------------------------------------
                # Step 1. Market Data Fetching
                # 수집기(Collector)가 DB에 저장해둔 최신 데이터를 가져옵니다.
                # -----------------------------------------------------------
                df = await get_recent_candles(session, symbol)
                
                # Redis 클라이언트 초기화 (모든 분기에서 사용)
                try:
                    redis_client = await get_redis_client()
                except Exception as e:
                    print(f"[!] Redis Init Error: {e}")
                    redis_client = None

                # 데이터 부족 시 대기 (최소 200개 필요 for MA 200)
                if len(df) < 200:
                    msg = f"[-] Not enough data ({len(df)} < 200). Waiting for collector..."
                    print(msg)
                    if redis_client:
                        status_data = {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "symbol": symbol,
                            "action": "WAITING",
                            "reason": f"데이터 부족: {len(df)} lines (Need 200+)",
                            "indicators": {}
                        }
                        await redis_client.set(f"bot:status:{symbol}", json.dumps(status_data), ex=300)

                else:
                    # 데이터 신선도(Freshness) 체크
                    # 수집기가 죽어서 과거 데이터만 남았을 경우 매매를 방지합니다.
                    last_ts = df.iloc[-1]["timestamp"]
                    now = datetime.now(timezone.utc)
                    
                    if (now - last_ts) > timedelta(minutes=2):
                        msg = f"[!] Data stale. Last candle: {last_ts.isoformat()}. Waiting for updates..."
                        print(msg)
                        if redis_client:
                            status_data = {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "symbol": symbol,
                                "action": "WAITING",
                                "reason": f"데이터 지연됨: {last_ts.isoformat()} (Collector 확인 필요)",
                                "indicators": {}
                            }
                            await redis_client.set(f"bot:status:{symbol}", json.dumps(status_data), ex=300)
                    else:
                        # -------------------------------------------------------
                        # Step 2. Market Analysis
                        # pandas-ta 라이브러리를 사용해 모든 지표를 한 번에 계산합니다.
                        # -------------------------------------------------------
                        indicators = get_all_indicators(df)
                        current_price = Decimal(str(indicators["close"]))
                        
                        # -------------------------------------------------------
                        # Step 3. Position & Signal Check
                        # 현재 내가 이 코인을 들고 있는지 확인합니다.
                        # -------------------------------------------------------
                        pos = await executor.get_position(session, symbol)
                        
                        # 4-1. 상태 요약 및 Redis 저장 (Dashboard Visualization)
                        if redis_client:
                            # redis_client = await get_redis_client() # 이미 위에서 초기화함

                            
                            # 기본적으로 'HOLD' 상태, 신호 발생 시 변경
                            bot_action = "HOLD"
                            bot_reason = ""
                            
                            # 임시 변수들
                            risk_valid_flag = True
                            risk_reason_msg = None

                            if not pos:
                                # 진입 전 리스크 체크 (가상으로 미리 확인해서 reason 생성)
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
                                "action": bot_action, # 다음 로직에서 BUY/SELL 발생 시 덮어쓰기 로직 필요하지만, 단순화를 위해 루프 끝단에서 갱신하거나 여기서 1차 저장
                                "reason": bot_reason
                            }
                            
                            
                            # 1차 저장 (분석 직후)
                            try:
                                await redis_client.set(f"bot:status:{symbol}", json.dumps(status_data), ex=300)
                            except Exception as e:
                                print(f"[!] Redis Publish Error: {e}")
                            
                        # except Exception as redis_err: # 삭제
                        #     print(f"[!] Redis Publish Error: {redis_err}")
                        
                        if pos:
                            # [Case A] 포지션 보유 중 -> 청산(Exit) 로직 가동
                            # 익절(+5%), 손절(-3%), RSI 과열(70+), 시간 만료(48h) 등을 체크합니다.
                            should_exit, exit_reason = strategy.check_exit_signal(indicators, pos)
                            
                            if should_exit:
                                print(f"[Signal] Exit Triggered: {exit_reason}")
                                
                                # 매도 주문 실행
                                success = await executor.execute_order(
                                    session, symbol, "SELL", 
                                    current_price, 
                                    pos["quantity"], 
                                    strategy.name, 
                                    {"reason": exit_reason, "indicators": indicators}
                                )
                                
                                if success:
                                    # 매도 성공 시 PnL(손익)을 계산하여 리스크 매니저에 반영
                                    # (연패 시 쿨다운 등의 로직이 여기서 작동합니다)
                                    avg_price = pos["avg_price"]
                                    quantity = pos["quantity"]
                                    pnl = (current_price - avg_price) * quantity
                                    await risk_manager.update_after_trade(session, pnl)
                                    print(f"[+] Risk Manager Updated. PnL: {pnl:,.0f} KRW")

                        else:
                            # [Case B] 포지션 미보유 -> 진입(Entry) 로직 가동
                            # RSI < 30 등 과매도 조건이 충족되었는지 확인합니다.
                            if strategy.check_entry_signal(indicators):
                                print(f"[Signal] Entry Triggered!")
                                
                                # ---------------------------------------------------
                                # Step 4. Risk Management (Pre-trade Check)
                                # 전략이 신호를 줘도, 리스크 관리자가 거부하면 매매하지 않습니다.
                                # 예: 일일 손실 한도 초과, 연패로 인한 쿨다운 등
                                # ---------------------------------------------------
                                balance = await executor.get_balance(session)
                                invest_amount = balance * risk_manager.max_per_order # 1회당 자산의 5%만 투입
                                
                                is_valid, risk_reason = await risk_manager.check_order_validity(session, symbol, invest_amount)
                                
                                if not is_valid:
                                    print(f"[-] Order Skipped by Risk Manager: {risk_reason}")
                                else:
                                    # 진입 수량 계산
                                    quantity = invest_amount / current_price
                                    
                                    if quantity > 0:
                                        # -----------------------------------------------
                                        # Step 5. AI Agent Verification & Execution
                                        # 최종적으로 AI(S.O.P Agent)에게 시장 상황을 브리핑하고
                                        # 매매 승인을 요청합니다. (Executor 내부에서 수행)
                                        # -----------------------------------------------
                                        
                                        # AI에게 넘겨줄 최근 시장 데이터(Context) 준비
                                        market_context = df.tail(10).to_dict(orient="records")
                                        signal_info = {
                                            **indicators,
                                            "market_context": market_context
                                        }
                                        
                                        # 매수 주문 실행
                                        # (execute_order 함수 내부에서 runner.run()을 호출하여 AI 검증을 수행함)
                                        await executor.execute_order(
                                            session, symbol, "BUY", 
                                            current_price, quantity, 
                                            strategy.name, 
                                            signal_info
                                        )

        except Exception as e:
            print(f"[!] Critical Bot Error: {e}")
            import traceback
            traceback.print_exc()
        
        # -----------------------------------------------------------
        # Interval Management
        # 정확히 1분 간격을 맞추기 위해, 수행 시간을 제외한 남은 시간만큼 대기합니다.
        # 예: 로직 수행에 0.5초 걸렸으면 59.5초 대기
        # -----------------------------------------------------------
        if SHUTDOWN:
            break
            
        elapsed = time.time() - loop_start_time
        sleep_time = max(0, 60 - elapsed)
        
        # 로그 과다 방지를 위해 sleep 로그는 생략 가능
        # print(f"[*] Sleeping for {sleep_time:.1f}s...")
        await asyncio.sleep(sleep_time)

    print("[*] Bot Loop Terminated Gracefully.")

if __name__ == "__main__":
    try:
        asyncio.run(bot_loop())
    except KeyboardInterrupt:
        pass
