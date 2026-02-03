
import asyncio
from decimal import Decimal
from src.config.strategy import StrategyConfig
from src.engine.risk_manager import RiskManager
from src.common.db import get_db_session

async def test():
    config = StrategyConfig()
    rm = RiskManager(config)

    print(f'=== 포트폴리오 리스크 설정 ===')
    print(f'단일 포지션 한도: {config.MAX_POSITION_SIZE * 100}%')
    print(f'전체 노출 한도: {config.MAX_TOTAL_EXPOSURE * 100}%')
    print(f'동시 포지션 한도: {config.MAX_CONCURRENT_POSITIONS}개')
    print(f'동일 코인 중복: {"허용" if config.ALLOW_SAME_COIN_DUPLICATE else "불가"}')

    async with get_db_session() as session:
        # 현재 열린 포지션 수 확인
        open_count = await rm.count_open_positions(session)
        print(f'\n현재 열린 포지션: {open_count}개')
        
        # 전체 노출 금액 확인
        exposure = await rm.get_total_exposure(session)
        print(f'현재 전체 노출 금액: {exposure:,.0f} KRW')

        # 테스트: 주문 가능 여부 (KRW-BTC, 50만원)
        # Note: Account Balance가 DB에 있어야 정확히 테스트 가능. 없으면 Fail 뜰 수 있음.
        ok, msg = await rm.check_order_validity(session, 'KRW-BTC', Decimal('500000'))
        print(f'KRW-BTC 50만원 주문: {"가능" if ok else "불가"} - {msg}')

if __name__ == "__main__":
    asyncio.run(test())
