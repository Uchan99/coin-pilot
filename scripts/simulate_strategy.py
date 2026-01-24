import asyncio
import pandas as pd
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import select

from src.common.db import get_db_session, engine
from src.common.models import MarketData
from src.common.indicators import get_all_indicators
from src.engine.strategy import MeanReversionStrategy
from src.engine.risk_manager import RiskManager
from src.engine.executor import PaperTradingExecutor

async def simulate():
    """
    DB에 저장된 과거 데이터를 사용하여 전략 시뮬레이션을 수행합니다.
    """
    symbol = "KRW-BTC"
    print(f"[*] Starting Strategy Simulation for {symbol}...")
    
    # 1. 컴포넌트 초기화
    strategy = MeanReversionStrategy()
    risk_manager = RiskManager()
    executor = PaperTradingExecutor()
    
    async with get_db_session() as session:
        # 2. 데이터 로드 (최근 1000개 분봉 + MA200을 위한 일봉)
        # 시뮬레이션 단순화를 위해 1분봉 데이터만 사용 (MA200은 고정값으로 가정하거나 일봉 병합 필요)
        # 여기서는 backfill된 일봉을 바탕으로 MA200을 계산해두고 1분봉 시뮬레이션 진행
        
        # 일봉 기반 MA200 계산
        stmt_day = select(MarketData).where(MarketData.symbol == symbol, MarketData.interval == "1d").order_by(MarketData.timestamp.desc()).limit(300)
        res_day = await session.execute(stmt_day)
        days = res_day.scalars().all()
        
        if len(days) < 200:
            print(f"[!] Insufficient daily data for MA200: {len(days)} < 200")
            return
            
        df_day = pd.DataFrame([{
            "close": float(d.close_price),
            "timestamp": d.timestamp
        } for d in days]).sort_values("timestamp")
        
        # 현재 시점의 MA200 (시뮬레이션 중에는 값이 크게 변하지 않는다고 가정하거나 매번 업데이트 가능)
        ma_200 = float(df_day['close'].rolling(window=200).mean().iloc[-1])
        print(f"[*] Current MA200 (Daily): {ma_200:,.0f}")
        
        # 분봉 데이터 로드
        stmt_min = select(MarketData).where(MarketData.symbol == symbol, MarketData.interval == "1m").order_by(MarketData.timestamp.asc())
        res_min = await session.execute(stmt_min)
        minutes = res_min.scalars().all()
        
        if not minutes:
            print("[!] No minute candles found in DB. Run backfill first.")
            return
            
        print(f"[*] Processing {len(minutes)} minute candles...")
        
        df_min = pd.DataFrame([{
            "open": float(m.open_price),
            "high": float(m.high_price),
            "low": float(m.low_price),
            "close": float(m.close_price),
            "volume": float(m.volume),
            "timestamp": m.timestamp
        } for m in minutes])

        # 3. 시뮬레이션 루프
        for i in range(30, len(df_min)):
            # 현재까지의 윈도우 데이터
            window = df_min.iloc[:i+1]
            current_candle = window.iloc[-1]
            
            # 지표 계산 (RSI, BB, Vol Ratio)
            # MA200은 위에서 구한 일봉 MA200 사용
            try:
                indicators = get_all_indicators(window)
                indicators["ma_200"] = ma_200 # 일봉 MA200 주입
            except Exception:
                continue

            # 포지션 확인
            position = await executor.get_position(session, symbol)
            
            if not position:
                # 4. 진입 신호 체크
                if strategy.check_entry_signal(indicators):
                    # 리스크 검증
                    price = Decimal(str(current_candle['close']))
                    # 주문 수량 결정 (단순하게 계좌의 1% 사용)
                    balance = await executor.get_balance(session)
                    amount_to_use = balance * Decimal("0.01")
                    quantity = amount_to_use / price
                    
                    passed, reason = await risk_manager.check_order_validity(session, symbol, amount_to_use)
                    
                    if passed:
                        # 매수 실행
                        success = await executor.execute_order(
                            session, symbol, "BUY", price, quantity, 
                            strategy.name, indicators
                        )
                        if success:
                            print(f"[ENTRY] {current_candle['timestamp']} | Price: {price:,.0f} | RSI: {indicators['rsi']:.2f}")
                    else:
                        await risk_manager.log_risk_violation(session, "ORDER_REJECTED", reason)
            else:
                # 5. 청산 신호 체크
                should_exit, reason = strategy.check_exit_signal(indicators, position)
                if should_exit:
                    price = Decimal(str(current_candle['close']))
                    quantity = Decimal(str(position['quantity']))
                    
                    # 매도 실행
                    success = await executor.execute_order(
                        session, symbol, "SELL", price, quantity,
                        strategy.name, indicators
                    )
                    
                    if success:
                        # 리스크 매니저 통계 업데이트 (PnL 계산)
                        pnl = (price - Decimal(str(position['avg_price']))) * quantity
                        await risk_manager.update_after_trade(session, pnl)
                        print(f"[EXIT] {current_candle['timestamp']} | Price: {price:,.0f} | Reason: {reason} | PnL: {pnl:,.0f}")

    print("[*] Simulation finished.")

if __name__ == "__main__":
    asyncio.run(simulate())
