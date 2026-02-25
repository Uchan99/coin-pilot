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
    - 단일 포지션 한도: 기준자산의 max_per_order (변동성 높으면 축소)
    - 일일 최대 손실: 기준자산의 max_daily_loss
    - 쿨다운: 3연패 시 2시간 중단
    - 포트폴리오 리스크: 전체 노출 한도, 동시 보유 종목 수, 중복 매수 제한
    """
    def __init__(self,
                 config: StrategyConfig = None,
                 max_per_order: Optional[float] = None,
                 max_daily_loss: Optional[float] = None,
                 max_daily_trades: Optional[int] = None,
                 cooldown_hours: Optional[int] = None,
                 redis_url: str = "redis://localhost:6379/0"):
        
        self.config = config or StrategyConfig()
        
        # 운영 설정 우선순위:
        # 1) 생성자 인자(명시 오버라이드)
        # 2) StrategyConfig(YAML 포함)
        # 이 우선순위를 강제해 설정 파일 변경이 실제 주문/리스크 로직에 반영되도록 맞춥니다.
        self.max_per_order = Decimal(str(
            self.config.MAX_POSITION_SIZE if max_per_order is None else max_per_order
        ))
        self.max_daily_loss = Decimal(str(
            self.config.MAX_DAILY_LOSS if max_daily_loss is None else max_daily_loss
        ))
        self.max_daily_trades = int(
            self.config.MAX_DAILY_TRADES if max_daily_trades is None else max_daily_trades
        )
        self.cooldown_hours = int(
            self.config.COOLDOWN_HOURS if cooldown_hours is None else cooldown_hours
        )

        fee_buffer_raw = os.getenv("ORDER_FEE_BUFFER_PCT", "0.002")
        try:
            fee_buffer = Decimal(str(fee_buffer_raw))
            if fee_buffer < 0 or fee_buffer >= 1:
                raise ValueError("fee buffer out of range")
            self.fee_buffer = fee_buffer
        except Exception:
            # 잘못된 환경값으로 주문이 전부 차단되는 것을 방지하기 위해 안전 기본값 적용
            self.fee_buffer = Decimal("0.002")
        
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

    async def get_total_equity(self, session: AsyncSession) -> Decimal:
        """
        총자산(현금 + 평가 노출)을 계산합니다.
        """
        stmt = select(AccountState).where(AccountState.id == 1)
        result = await session.execute(stmt)
        account = result.scalar_one_or_none()
        if not account:
            return Decimal(0)

        exposure = await self.get_total_exposure(session)
        return account.balance + exposure

    async def get_reference_equity(self, session: AsyncSession) -> Decimal:
        """
        주문 기준자산(reference equity)을 반환합니다.

        정책:
        - REFERENCE_EQUITY 환경변수가 있으면 고정값으로 사용
        - 없으면 UTC 일자 기준 1회 스냅샷(일중 고정)
        """
        env_override = os.getenv("REFERENCE_EQUITY", "").strip()
        if env_override:
            try:
                fixed = Decimal(env_override)
                if fixed > 0:
                    return fixed
            except Exception:
                pass

        today = datetime.now(timezone.utc).date().isoformat()
        key = f"coinpilot:reference_equity:{today}"

        try:
            cached = await self.redis_client.get(key)
            if cached:
                value = Decimal(cached)
                if value > 0:
                    return value
        except Exception:
            # Redis 문제 시에도 계산 경로로 계속 진행
            pass

        reference = await self.get_total_equity(session)
        if reference <= 0:
            stmt = select(AccountState).where(AccountState.id == 1)
            result = await session.execute(stmt)
            account = result.scalar_one_or_none()
            reference = account.balance if account else Decimal(0)

        try:
            now = datetime.now(timezone.utc)
            tomorrow = (now + timedelta(days=1)).date()
            expiry_seconds = int((datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc) - now).total_seconds())
            await self.redis_client.set(key, str(reference), ex=max(expiry_seconds, 3600))
        except Exception:
            pass

        return reference

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
        if amount <= 0:
            return False, "주문 금액이 0 이하입니다."

        reference_equity = await self.get_reference_equity(session)
        if reference_equity <= 0:
            return False, "기준 자산(reference equity)이 0 이하입니다."

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
        if state.total_pnl <= -(reference_equity * self.max_daily_loss):
            # 상태 업데이트: 거래 중단 설정
            state.is_trading_halted = True
            return False, f"일일 최대 손실 한도(-{self.max_daily_loss*100}%)에 도달하여 거래를 중단합니다."

        # 6. 단일 주문 한도 확인 (기준자산 * 주문비중 * 변동성 배율)
        vol_multiplier = await self.get_volatility_multiplier()
        base_max_amount = reference_equity * self.max_per_order
        max_order_amount = base_max_amount * Decimal(str(vol_multiplier))
        
        if amount > max_order_amount:
            msg = f"단일 주문 한도({self.max_per_order*100}%)를 초과했습니다."
            if vol_multiplier < 1.0:
                msg += f" (고변동성으로 인해 비중 {vol_multiplier*100:.0f}% 축소 적용됨)"
            msg += f" (요청: {amount:.0f}, 한도: {max_order_amount:.0f})"
            return False, msg

        # 6-1. 가용 현금 한도 확인 (수수료/슬리피지 완충 포함)
        available_cash = account.balance * (Decimal("1") - self.fee_buffer)
        if amount > available_cash:
            return False, (
                f"가용 현금 부족 (요청: {amount:,.0f}, 가용: {available_cash:,.0f}, "
                f"수수료 버퍼: {self.fee_buffer*100:.2f}%)"
            )

        # ========== 추가된 포트폴리오 리스크 검증 (v2.0) ==========

        # 7. 전체 노출 한도 확인 (기준자산 * MAX_TOTAL_EXPOSURE)
        current_exposure = await self.get_total_exposure(session)
        max_total_exposure = reference_equity * Decimal(str(self.config.MAX_TOTAL_EXPOSURE))
        
        if current_exposure + amount > max_total_exposure:
            exposure_pct = float(Decimal(str(self.config.MAX_TOTAL_EXPOSURE)) * Decimal("100"))
            return False, (
                f"전체 노출 한도({exposure_pct:.0f}%) 초과 "
                f"({current_exposure + amount:,.0f} > {max_total_exposure:,.0f})"
            )

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
