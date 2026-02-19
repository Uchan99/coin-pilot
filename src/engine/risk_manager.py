from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Tuple
from sqlalchemy import select, update, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
import os
import json

from src.common.models import DailyRiskState, AccountState, RiskAudit, Position, MarketData
from src.common.notification import notifier
from src.common.db import get_db_session
from src.config.strategy import StrategyConfig
import asyncio

class RiskManager:
    """
    리스크 관리자: 매매 주문의 유효성을 검증하고 일일 한도를 관리합니다.
    - 단일 포지션 한도: 총 자산의 5% (변동성 높으면 50% 축소)
    - 일일 최대 손실: -5%
    - 쿨다운: 3연패 시 2시간 중단
    - 포트폴리오 리스크 (New): 전체 노출 20% 한도, 최대 3종목, 중복 매수 제한
    """
    def __init__(self, 
                 config: StrategyConfig = None,
                 max_per_order: float = 0.05, 
                 max_daily_loss: float = 0.05,
                 max_daily_trades: int = 10,
                 cooldown_hours: int = 2,
                 redis_url: str = "redis://localhost:6379/0"):
        
        self.config = config or StrategyConfig()
        
        # 이전 하위 호환성을 위해 parameter가 있으면 그걸 쓰고, 없으면 config 값 사용 가능하도록 할 수도 있으나,
        # 여기서는 기존 parameter를 우선하되 config와 싱크를 맞춤
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
            state = DailyRiskState(
                date=today,
                total_pnl=0,
                buy_count=0,
                sell_count=0,
                trade_count=0,
                consecutive_losses=0,
            )
            session.add(state)
            await session.flush() # ID 등 반영
        return state

    # ========== 신규 메서드: 포트폴리오 리스크 관리 (Portfolio Risk) ==========

    async def count_open_positions(self, session: AsyncSession) -> int:
        """
        현재 열린 포지션의 개수를 반환합니다. (수량 > 0)
        """
        stmt = select(func.count()).select_from(Position).where(
            Position.quantity > 0
        )
        result = await session.execute(stmt)
        return result.scalar() or 0

    async def _get_current_price(self, symbol: str) -> Decimal:
        """
        현재가 조회 (Redis 캐시 우선, 없으면 DB 최신 캔들 Fallback)
        """
        # Option 1: Redis에서 실시간 가격 조회 (Bot이 업데이트함)
        try:
            price_str = await self.redis_client.get(f"price:{symbol}")
            if price_str:
                return Decimal(price_str)
        except Exception:
            pass

        # Option 2: DB에서 최신 캔들 조회 (Fallback)
        # 주의: 이 메서드는 별도의 DB 세션을 사용함 (호출하는 쪽 세션과 분리)
        async with get_db_session() as session:
            stmt = select(MarketData.close_price).where(
                MarketData.symbol == symbol
            ).order_by(desc(MarketData.timestamp)).limit(1)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return Decimal(str(row)) if row else Decimal(0)

    async def get_total_exposure(self, session: AsyncSession) -> Decimal:
        """
        현재 전체 노출 금액 (Total Exposure) 계산
        - 모든 열린 포지션의 (평가 금액) 합계
        - 평가 금액 = 보유 수량 * 현재가
        """
        # 현재 열린 포지션 조회
        stmt = select(Position).where(Position.quantity > 0)
        result = await session.execute(stmt)
        positions = result.scalars().all()

        total = Decimal(0)
        for pos in positions:
            current_price = await self._get_current_price(pos.symbol)
            # 현재가가 없으면(0) 매입가(avg_price)로 대체하는 것도 방법이나, 여기선 0으로 처리됨
            # 더 안전한 방법: current_price가 0이면 pos.avg_price 사용
            if current_price == 0:
                current_price = pos.avg_price
            
            total += pos.quantity * current_price
            
        return total

    async def has_position(self, session: AsyncSession, symbol: str) -> bool:
        """특정 심볼의 포지션 보유 여부 확인"""
        stmt = select(Position).where(
            Position.symbol == symbol,
            Position.quantity > 0
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def check_order_validity(self, session: AsyncSession, symbol: str, amount: Decimal) -> Tuple[bool, str]:
        """
        주문 실행 전 리스크 규칙을 검증합니다.
        (기존 규칙 + 포트폴리오 규칙 추가됨)
        
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
        if state.buy_count >= self.max_daily_trades:
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

        # ========== 추가된 포트폴리오 리스크 검증 (v2.0) ==========

        # 7. 전체 노출 한도 확인 (Account Balance * 20%)
        current_exposure = await self.get_total_exposure(session)
        max_total_exposure = account.balance * Decimal(str(self.config.MAX_TOTAL_EXPOSURE))
        
        if current_exposure + amount > max_total_exposure:
            return False, f"전체 노출 한도(20%) 초과 ({current_exposure + amount:,.0f} > {max_total_exposure:,.0f})"

        # 8. 동시 포지션 수 확인 (Max 3개)
        # 주의: 이미 보유 중인 상태에서 추가 매수(물타기/불타기)인 경우는 포지션 수가 늘어나지 않음.
        # has_position 체크 필요
        is_existing_position = await self.has_position(session, symbol)
        open_count = await self.count_open_positions(session)
        
        if not is_existing_position and open_count >= self.config.MAX_CONCURRENT_POSITIONS:
            return False, f"동시 보유 포지션 한도({self.config.MAX_CONCURRENT_POSITIONS}개) 도달"

        # 9. 동일 코인 중복 진입 방지 (설정에 따름)
        if not self.config.ALLOW_SAME_COIN_DUPLICATE:
            if is_existing_position:
                return False, f"{symbol} 이미 포지션 보유 중 (중복 진입 금지)"

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

    async def update_after_trade(self, session: AsyncSession, pnl: Decimal, side: str = "SELL"):
        """
        매매 종료 후 리스크 상태를 업데이트합니다. (PnL 반영, 연패 계산, 쿨다운 등)
        """
        state = await self.get_daily_state(session)

        normalized_side = (side or "SELL").upper()
        if normalized_side == "BUY":
            state.buy_count += 1
            state.trade_count += 1
            await session.flush()
            return

        # Default/legacy path: SELL 처리
        state.sell_count += 1
        state.trade_count += 1
        state.total_pnl += pnl

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
