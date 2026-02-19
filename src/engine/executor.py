import os
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, Dict
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.models import AccountState, Position, TradingHistory
from src.common.db import get_redis_client
from src.agents.guardrails import update_ai_guardrails_after_decision
from src.common.json_utils import to_builtin

class PaperTradingExecutor:
    """
    모의 투자(Paper Trading) 실행기: 실제 API 호출 없이 DB 상의 잔고와 포지션을 업데이트합니다.
    """
    def __init__(self, initial_balance: Optional[float] = None):
        self.default_balance = Decimal(str(initial_balance)) if initial_balance else Decimal(os.getenv("PAPER_BALANCE", "10000000"))

    async def get_balance(self, session: AsyncSession) -> Decimal:
        """
        현재 계좌 잔고를 DB에서 조회합니다.
        """
        stmt = select(AccountState).where(AccountState.id == 1)
        result = await session.execute(stmt)
        account = result.scalar_one_or_none()
        
        if not account:
            # 잔고 정보가 없으면 초기값으로 생성
            account = AccountState(id=1, balance=self.default_balance)
            session.add(account)
            await session.flush()
            print(f"[*] Initialized account balance with {self.default_balance:,.0f} KRW.")
        
        return account.balance

    async def get_position(self, session: AsyncSession, symbol: str) -> Optional[Dict]:
        """
        특정 심볼의 현재 포지션 정보를 조회합니다.
        """
        stmt = select(Position).where(Position.symbol == symbol)
        result = await session.execute(stmt)
        pos = result.scalar_one_or_none()
        
        if pos:
            return {
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "avg_price": pos.avg_price,
                "opened_at": pos.opened_at,
                "regime": pos.regime,
                "high_water_mark": pos.high_water_mark
            }
        return None

    async def execute_order(self, 
                            session: AsyncSession, 
                            symbol: str, 
                            side: str, 
                            price: Decimal, 
                            quantity: Decimal,
                            strategy_name: str,
                            signal_info: Dict) -> bool:
        """
        주문을 실행하고 DB 상태를 업데이트합니다.
        (BUY 주문 시 AI 에이전트의 2차 검증을 수행합니다.)
        """
        try:
            safe_signal_info = to_builtin(signal_info or {})

            # 0. AI 에이전트 검증 (BUY 주문인 경우에만 수행)
            if side == "BUY":
                from src.agents.runner import runner
                # market_context는 signal_info에서 추출하거나 별도로 전달받아야 함
                # 현재는 signal_info를 context로 활용
                is_approved, reasoning = await runner.run(
                    symbol=symbol,
                    strategy_name=strategy_name,
                    market_context=safe_signal_info.get("market_context", {}),
                    indicators=safe_signal_info
                )
                
                if not is_approved:
                    print(f"[-] Trade Rejected by AI Agent: {reasoning}")
                    try:
                        redis_client = await get_redis_client()
                    except Exception:
                        redis_client = None
                    await update_ai_guardrails_after_decision(
                        redis_client=redis_client,
                        symbol=symbol,
                        approved=False,
                        reasoning=reasoning,
                        cfg=safe_signal_info.get("entry_config", {}),
                    )
                    return False
                print(f"[+] Trade Approved by AI Agent: {reasoning}")
                try:
                    redis_client = await get_redis_client()
                except Exception:
                    redis_client = None
                await update_ai_guardrails_after_decision(
                    redis_client=redis_client,
                    symbol=symbol,
                    approved=True,
                    reasoning=reasoning,
                    cfg=safe_signal_info.get("entry_config", {}),
                )

            # 1. 잔고 조회 및 업데이트
            current_balance = await self.get_balance(session)
            order_amount = price * quantity
            
            if side == "BUY":
                if current_balance < order_amount:
                    print(f"[!] Insufficient balance for BUY: {current_balance} < {order_amount}")
                    return False
                # 잔고 차감
                await session.execute(
                    update(AccountState).where(AccountState.id == 1).values(balance=AccountState.balance - order_amount)
                )
                # 포지션 추가 (동시성 제어를 위해 with_for_update 사용)
                stmt = select(Position).where(Position.symbol == symbol).with_for_update()
                res = await session.execute(stmt)
                existing_pos = res.scalar_one_or_none()
                
                # 레짐 정보 및 초기 HWM 설정
                regime = safe_signal_info.get("regime")
                
                if existing_pos:
                    # 평균 단가 계산 및 수량 업데이트
                    new_qty = existing_pos.quantity + quantity
                    new_avg_price = (existing_pos.avg_price * existing_pos.quantity + price * quantity) / new_qty
                    existing_pos.quantity = new_qty
                    existing_pos.avg_price = new_avg_price
                    existing_pos.regime = regime
                    # 추가 매수 시 HWM은 합산 후 가격 또는 현재가 중 높은 것으로 갱신 가능하나 일단 현재가로 갱신
                    existing_pos.high_water_mark = price if price > existing_pos.high_water_mark else existing_pos.high_water_mark
                else:
                    new_pos = Position(
                        symbol=symbol, 
                        quantity=quantity, 
                        avg_price=price,
                        regime=regime,
                        high_water_mark=price
                    )
                    session.add(new_pos)
                    
            elif side == "SELL":
                # 포지션 조회
                stmt = select(Position).where(Position.symbol == symbol)
                res = await session.execute(stmt)
                existing_pos = res.scalar_one_or_none()
                
                if not existing_pos or existing_pos.quantity < quantity:
                    print(f"[!] Insufficient quantity for SELL")
                    return False
                
                # 잔고 증가 (매도 금액 가산)
                await session.execute(
                    update(AccountState).where(AccountState.id == 1).values(balance=AccountState.balance + order_amount)
                )
                
                # 포지션 차감 또는 삭제
                if existing_pos.quantity == quantity:
                    await session.execute(delete(Position).where(Position.symbol == symbol))
                else:
                    existing_pos.quantity -= quantity

            # 2. 거래 이력 기록
            history = TradingHistory(
                symbol=symbol,
                side=side,
                order_type="MARKET", # 모의 투자는 단순화를 위해 시장가 체결 가정
                price=price,
                quantity=quantity,
                status="FILLED",
                strategy_name=strategy_name,
                signal_info=safe_signal_info,
                regime=safe_signal_info.get("regime"),
                high_water_mark=safe_signal_info.get("new_hwm") or price,
                exit_reason=safe_signal_info.get("exit_reason") if side == "SELL" else None,
                executed_at=datetime.now(timezone.utc)
            )
            session.add(history)
            
            # 3. n8n 알림 발송 (비동기)
            from src.common.notification import notifier
            asyncio.create_task(notifier.send_webhook("/webhook/trade", {
                "symbol": symbol,
                "side": side,
                "price": float(price),
                "quantity": float(quantity),
                "strategy": strategy_name,
                "executed_at": history.executed_at.isoformat()
            }))
            
            print(f"[+] Order Executed: {side} {symbol} (Qty: {quantity}, Price: {price:,.0f})")
            return True
            
        except Exception as e:
            print(f"[!] Execution Error: {e}")
            return False
