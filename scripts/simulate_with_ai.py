import asyncio
import pandas as pd
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import select

from src.common.db import get_db_session
from src.common.models import MarketData
from src.common.indicators import get_all_indicators
from src.engine.strategy import MeanReversionStrategy
from src.engine.risk_manager import RiskManager
from src.engine.executor import PaperTradingExecutor

async def simulate_with_ai():
    """
    AI 에이전트가 포함된 전략 시뮬레이션을 수행합니다.
    """
    symbol = "KRW-BTC"
    print(f"[*] Starting AI-Integrated Strategy Simulation for {symbol}...")
    
    # 1. 컴포넌트 초기화
    strategy = MeanReversionStrategy()
    risk_manager = RiskManager()
    executor = PaperTradingExecutor()
    
    async with get_db_session() as session:
        # 데이터 로드 (시뮬레이션 단순화를 위해 1분봉 데이터 사용)
        
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
        
        ma_200 = float(df_day['close'].rolling(window=200).mean().iloc[-1])
        print(f"[*] Current MA200 (Daily): {ma_200:,.0f}")
        
        # 분봉 데이터 로드 (최근 500개만 테스트)
        stmt_min = select(MarketData).where(MarketData.symbol == symbol, MarketData.interval == "1m").order_by(MarketData.timestamp.asc()).limit(500)
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
            window = df_min.iloc[:i+1]
            current_candle = window.iloc[-1]
            
            try:
                indicators = get_all_indicators(window)
                indicators["ma_200"] = ma_200
                
                # AI를 위한 Context 추가 (최근 10개 캔들 요약)
                indicators["market_context"] = window.tail(10).to_dict(orient="records")
            except Exception:
                continue

            position = await executor.get_position(session, symbol)
            
            if not position:
                # 4. 진입 신호 체크
                if strategy.check_entry_signal(indicators):
                    price = Decimal(str(current_candle['close']))
                    balance = await executor.get_balance(session)
                    amount_to_use = balance * Decimal("0.01")
                    quantity = amount_to_use / price
                    
                    passed, reason = await risk_manager.check_order_validity(session, symbol, amount_to_use)
                    
                    if passed:
                        # 매수 실행 (내부적으로 AI Agent 호출됨)
                        success = await executor.execute_order(
                            session, symbol, "BUY", price, quantity, 
                            strategy.name, indicators
                        )
                        if success:
                            print(f"[ENTRY-AI] {current_candle['timestamp']} | Price: {price:,.0f}")
                    else:
                        await risk_manager.log_risk_violation(session, "ORDER_REJECTED", reason)
            else:
                # 5. 청산 신호 체크
                should_exit, reason = strategy.check_exit_signal(indicators, position)
                if should_exit:
                    price = Decimal(str(current_candle['close']))
                    quantity = Decimal(str(position['quantity']))
                    success = await executor.execute_order(
                        session, symbol, "SELL", price, quantity,
                        strategy.name, indicators
                    )
                    
                    if success:
                        pnl = (price - Decimal(str(position['avg_price']))) * quantity
                        await risk_manager.update_after_trade(session, pnl)
                        print(f"[EXIT] {current_candle['timestamp']} | Price: {price:,.0f} | Reason: {reason} | PnL: {pnl:,.0f}")

    print("[*] AI-Integrated Simulation finished.")

if __name__ == "__main__":
    asyncio.run(simulate_with_ai())
