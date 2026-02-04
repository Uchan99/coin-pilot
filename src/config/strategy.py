from dataclasses import dataclass, field
from typing import List

@dataclass
class StrategyConfig:
    """
    전략 설정 - v2.0 (멀티 코인 + 조건 완화 및 포트폴리오 리스크 관리)
    
    기존 단일 코인(BTC) 전략에서 다중 코인으로 대상을 확장하고, 
    진입 조건을 완화하여 거래 기회를 늘리되, 포트폴리오 리스크 관리 규칙을 추가하여 안정성을 확보함.
    """
    
    # ========== 대상 코인 (Target Assets) ==========
    # 선정 기준: 시총 상위, 거래량 풍부, 업비트 원화 마켓 상장, 충분한 유동성
    SYMBOLS: List[str] = field(default_factory=lambda: [
        "KRW-BTC",   # 비트코인: 시장 기준 자산
        "KRW-ETH",   # 이더리움: 시총 2위, 독자 생태계
        "KRW-XRP",   # 리플: 국내 거래량 상위, 비트코인과 다른 패턴
        "KRW-SOL",   # 솔라나: 높은 변동성으로 인한 기회 포착
        "KRW-DOGE",  # 도지코인: 밈 코인 특유의 독자 패턴 활용
    ])
    
    # ========== 진입 조건 (Entry Conditions - Relaxed) ==========
    # 기존 RSI 30 기준은 너무 엄격하여 기회가 적었으므로 소폭 완화
    RSI_OVERSOLD: int = 33              # 기존 30 -> 33 (과매도 기준 완화)
    RSI_PERIOD: int = 14
    
    # 추세 필터 완화 (역추세 매매 방지, 단 MA200은 RSI 과매도와 상충하여 MA50으로 변경)
    MA_TREND_PERIOD: int = 50           # 기존 200 -> 50 (중기 추세로 완화)

    # 거래량 급증 기준 완화 (1.5배 -> 1.2배)
    VOLUME_MULTIPLIER: float = 1.2      # 기존 1.5 -> 1.3 -> 1.2
    VOLUME_MA_PERIOD: int = 20
    
    # 볼린저 밴드 조건은 RSI와 중복 성향이 강해 선택적 요소로 변경 (기본 비활성)
    USE_BB_CONDITION: bool = False      # BB 하단 터치 조건 해제
    
    # ========== 청산 조건 (Exit Conditions - Unchanged) ==========
    TAKE_PROFIT: float = 0.05           # 목표 수익률 +5%
    STOP_LOSS: float = 0.03             # 손절률 -3%
    RSI_OVERBOUGHT: int = 70            # 과매수 도달 시 청산
    MAX_HOLD_HOURS: int = 48            # 최대 보유 시간 (자금 회전률 제고)
    
    # ========== 단일 포지션 리스크 (Single Position Risk) ==========
    MAX_POSITION_SIZE: float = 0.05     # 건당 최대 투자금 (전체 자산의 5%)
    
    # ========== 포트폴리오 리스크 (Portfolio Risk - New) ==========
    # 다중 코인 거래 시 전체 노출 리스크 관리
    MAX_TOTAL_EXPOSURE: float = 0.20    # 전체 포지션 합계 최대 20% (보수적 운용)
    MAX_CONCURRENT_POSITIONS: int = 3   # 동시에 최대 3개 코인만 보유 (상관관계 리스크 분산)
    ALLOW_SAME_COIN_DUPLICATE: bool = False # 동일 코인 중복 진입 불가 (피라미딩 금지)
    
    # ========== 일일 제한 (Daily Limits) ==========
    MAX_DAILY_LOSS: float = 0.05        # 일일 최대 손실 -5% 도달 시 거래 중단
    MAX_DAILY_TRADES: int = 10          # 잦은 거래로 인한 수수료 과다 방지
    
    # 연속 손실 발생 시 쿨다운 (감정적 매매 방지)
    COOLDOWN_AFTER_CONSECUTIVE_LOSSES: int = 3
    COOLDOWN_HOURS: int = 2
    MIN_TRADE_INTERVAL_MINUTES: int = 30 # 동일 코인 재진입 최소 간격


# 보수적 모드 설정 (문제 발생 시 롤백용 Fallback Config)
# 롤백 시 이 설정을 사용하여 초기 전략(매우 보수적, BTC only)으로 복귀
CONSERVATIVE_CONFIG = StrategyConfig(
    SYMBOLS=["KRW-BTC"],
    RSI_OVERSOLD=30,
    MA_TREND_PERIOD=200,        # 보수적 모드는 기존 MA200 유지
    VOLUME_MULTIPLIER=1.5,
    USE_BB_CONDITION=True,
    MAX_TOTAL_EXPOSURE=0.05,
    MAX_CONCURRENT_POSITIONS=1,
)

# ========== 모드 전환 스위치 (Switch) ==========
# 문제 발생 시 이 값을 True로 변경하면 즉시 보수적 모드로 전환됨
USE_CONSERVATIVE_MODE = False

def get_config() -> StrategyConfig:
    """
    현재 활성화된 전략 설정을 반환합니다.
    USE_CONSERVATIVE_MODE 플래그에 따라 일반 설정 또는 보수적 설정을 반환하여,
    코드 수정 없이 설정 전환이 가능하도록 함.
    """
    if USE_CONSERVATIVE_MODE:
        return CONSERVATIVE_CONFIG
    return StrategyConfig()
