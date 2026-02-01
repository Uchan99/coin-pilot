from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Tuple
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
import os
import json

from src.common.models import DailyRiskState, AccountState, RiskAudit
from src.common.notification import notifier
import asyncio

class RiskManager:
    """
    리스크 관리자: 매매 주문의 유효성을 검증하고 일일 한도를 관리합니다.
    - 단일 포지션 한도: 총 자산의 5% (변동성 높으면 50% 축소)
    - 일일 최대 손실: -5%
    - 쿨다운: 3연패 시 2시간 중단
    """
    def __init__(self, 
                 max_per_order: float = 0.05, 
                 max_daily_loss: float = 0.05,
                 max_daily_trades: int = 10,
                 cooldown_hours: int = 2,
                 redis_url: str = "redis://localhost:6379/0"):
        self.max_per_order = Decimal(str(max_per_order))
        self.max_daily_loss = Decimal(str(max_daily_loss))
        self.max_daily_trades = max_daily_trades
        self.cooldown_hours = cooldown_hours
        
        # Redis 연결 (환경 변수 우선)
        redis_url = os.getenv("REDIS_URL", redis_url)
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

    async def get_volatility_multiplier(self) -> float:
        """
        Redis에서 변동성 상태를 조회하여 포지션 크기 배율을 반환합니다.
        - High Volatility: 0.5 (50% 축소)
        - Normal / Error: 1.0 (기본)
        """
        try:
            data = await self.redis_client.get("coinpilot:volatility_state")
            if data:
                state = json.loads(data)
                if state.get("is_high_volatility", False):
                    # 로그는 너무 자주 찍히지 않도록 주의하거나 필요한 곳에서만 호출
                    return 0.5
            return 1.0
        except Exception as e:
            print(f"[RiskManager] Redis Error (Volatility): {e}")
            return 1.0 # Fallback

    async def get_daily_state(self, session: AsyncSession) -> DailyRiskState:
        """
        오늘의 리스크 상태를 DB에서 가져오거나 새로 생성합니다.
        """
        today = datetime.now(timezone.utc).date()
        stmt = select(DailyRiskState).where(DailyRiskState.date == today)
        result = await session.execute(stmt)
        state = result.scalar_one_or_none()
        
        if not state:
            state = DailyRiskState(date=today, total_pnl=0, trade_count=0, consecutive_losses=0)
            session.add(state)
            await session.flush() # ID 등 반영
        return state

    async def check_order_validity(self, session: AsyncSession, symbol: str, amount: Decimal) -> Tuple[bool, str]:
        """
        주문 실행 전 리스크 규칙을 검증합니다.
        
        Returns: (통과여부, 거절사유)
        """
        # 1. 일일 상태 및 계좌 잔고 조회
        state = await self.get_daily_state(session)
        
        stmt = select(AccountState).where(AccountState.id == 1)
        result = await session.execute(stmt)
        account = result.scalar_one_or_none()
        
        if not account:
            return False, "계좌 정보(AccountState)가 존재하지 않습니다."

        # 2. 거래 중단 확인 (Halt)
        if state.is_trading_halted:
            return False, "일일 리스크 한도 초과로 인해 거래가 중단된 상태입니다."

        # 3. 쿨다운 확인
        if state.cooldown_until and state.cooldown_until > datetime.now(timezone.utc):
            remain = state.cooldown_until - datetime.now(timezone.utc)
            return False, f"3연패로 인한 쿨다운 중입니다. (남은 시간: {remain.total_seconds()/60:.1f}분)"

        # 4. 일일 최대 거래 횟수 확인
        if state.trade_count >= self.max_daily_trades:
            return False, f"일일 최대 거래 횟수({self.max_daily_trades}회)를 초과했습니다."

        # 5. 일일 최대 손실 확인
        if state.total_pnl <= -(account.balance * self.max_daily_loss):
            # 상태 업데이트: 거래 중단 설정
            state.is_trading_halted = True
            return False, f"일일 최대 손실 한도(-{self.max_daily_loss*100}%)에 도달하여 거래를 중단합니다."

        # 6. 단일 주문 한도 확인 (자산의 5% * 변동성 배율)
        vol_multiplier = await self.get_volatility_multiplier()
        base_max_amount = account.balance * self.max_per_order
        max_order_amount = base_max_amount * Decimal(str(vol_multiplier))
        
        if amount > max_order_amount:
            msg = f"단일 주문 한도({self.max_per_order*100}%)를 초과했습니다."
            if vol_multiplier < 1.0:
                msg += f" (고변동성으로 인해 비중 {vol_multiplier*100:.0f}% 축소 적용됨)"
            msg += f" (요청: {amount:.0f}, 한도: {max_order_amount:.0f})"
            return False, msg

        return True, ""

    async def log_risk_violation(self, session: AsyncSession, v_type: str, desc: str):
        """
        리스크 위반 로그를 DB에 남깁니다.
        """
        audit = RiskAudit(
            violation_type=v_type,
            description=desc
        )
        session.add(audit)
        
        # n8n 리스크 알림 발송
        asyncio.create_task(notifier.send_webhook("/webhook/risk", {
            "type": v_type,
            "message": desc,
            "level": "WARNING"
        }))
        
        print(f"[!] Risk Violation: {v_type} - {desc}")

    async def update_after_trade(self, session: AsyncSession, pnl: Decimal):
        """
        매매 종료 후 리스크 상태를 업데이트합니다. (PnL 반영, 연패 계산, 쿨다운 등)
        """
        state = await self.get_daily_state(session)
        state.total_pnl += pnl
        state.trade_count += 1
        
        if pnl < 0:
            state.consecutive_losses += 1
            # 3연패 시 2시간 쿨다운 설정
            if state.consecutive_losses >= 3:
                state.cooldown_until = datetime.now(timezone.utc) + timedelta(hours=self.cooldown_hours)
                state.consecutive_losses = 0 # 쿨다운 진입 후 초기화
                
                # n8n 쿨다운 알림 발송
                asyncio.create_task(notifier.send_webhook("/webhook/risk", {
                    "type": "COOLDOWN",
                    "message": f"3연패로 인해 {self.cooldown_hours}시간 동안 거래를 중단합니다.",
                    "level": "CRITICAL"
                }))
                
                print(f"[!] 3 consecutive losses detected. Cooldown for {self.cooldown_hours} hours.")
        else:
            state.consecutive_losses = 0 # 수익 발생 시 연패 초기화
            
        await session.flush()
