import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict

@dataclass
class RegimeEntryConfig:
    rsi_14_max: int
    rsi_7_trigger: int
    rsi_7_recover: int
    ma_condition: str  # "crossover" | "proximity"
    ma_period: int
    ma_proximity_pct: Optional[float] = None
    bb_enabled: bool = False
    bb_period: int = 20
    bb_std: float = 2.0
    bb_touch_lookback: int = 30
    volume_ratio: Optional[float] = None

@dataclass
class RegimeExitConfig:
    take_profit_pct: float
    stop_loss_pct: float
    trailing_stop_pct: float
    trailing_stop_activation_pct: float
    rsi_overbought: int
    rsi_exit_min_profit_pct: float
    time_limit_hours: int

@dataclass
class StrategyConfig:
    """
    전략 설정 - v3.0 (마켓 레짐 기반 적응형 전략)
    """
    # ========== 공통 설정 ==========
    SYMBOLS: List[str] = field(default_factory=lambda: [
        "KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE"
    ])
    
    # 레짐 감지 설정
    MA_FAST_PERIOD: int = 50
    MA_SLOW_PERIOD: int = 200
    BULL_THRESHOLD_PCT: float = 2.0
    BEAR_THRESHOLD_PCT: float = -2.0
    
    # 데이터 설정
    MIN_HOURLY_CANDLES_FOR_REGIME: int = 200
    
    # 레짐별 설정 (v3.2 기본값)
    REGIMES: Dict[str, Any] = field(default_factory=lambda: {
        "BULL": {
            "entry": {
                "rsi_14_max": 50, "rsi_7_trigger": 42, "rsi_7_recover": 42,
                "min_rsi_7_bounce_pct": 2.0,  # RSI(7) 최소 반등 폭
                "ma_condition": "crossover", "ma_period": 20,
                "volume_ratio": 1.0,           # 상한 조건
                "volume_min_ratio": None       # 하한 조건 미적용
            },
            "exit": {
                "take_profit_pct": 0.05, "stop_loss_pct": 0.03, "trailing_stop_pct": 0.03,
                "trailing_stop_activation_pct": 0.01, "rsi_overbought": 75,
                "rsi_exit_min_profit_pct": 0.01, "time_limit_hours": 72
            },
            "position_size_ratio": 1.0
        },
        "SIDEWAYS": {
            "entry": {
                "rsi_14_max": 48, "rsi_7_trigger": 40, "rsi_7_recover": 40,
                "min_rsi_7_bounce_pct": 2.0,
                "ma_condition": "proximity", "ma_period": 20, "ma_proximity_pct": 0.97,
                "bb_enabled": True,
                "require_price_above_bb_lower": True,  # BB 하단 아래 진입 금지
                "volume_ratio": None,           # 상한 조건 미적용
                "volume_min_ratio": 0.3         # 하한 조건: 최소 30%
            },
            "exit": {
                "take_profit_pct": 0.03, "stop_loss_pct": 0.04, "trailing_stop_pct": 0.025,
                "trailing_stop_activation_pct": 0.01, "rsi_overbought": 70,
                "rsi_exit_min_profit_pct": 0.01, "time_limit_hours": 48
            },
            "position_size_ratio": 0.8
        },
        "BEAR": {
            "entry": {
                "rsi_14_max": 42, "rsi_7_trigger": 30, "rsi_7_recover": 30,
                "min_rsi_7_bounce_pct": 2.0,
                "ma_condition": "proximity_or_above", "ma_period": 20, "ma_proximity_pct": 0.97,
                "require_price_above_bb_lower": True,  # BB 하단 아래 진입 금지
                "volume_ratio": None,           # 상한 조건 미적용
                "volume_min_ratio": 0.2,        # 하한 조건: 최소 20%
                "volume_surge_check": True,     # 거래량 급증 체크
                "volume_surge_ratio": 2.0       # 평균 대비 2배 이상 급증 시 보류
            },
            "exit": {
                "take_profit_pct": 0.03, "stop_loss_pct": 0.05, "trailing_stop_pct": 0.02,
                "trailing_stop_activation_pct": 0.01, "rsi_overbought": 70,
                "rsi_exit_min_profit_pct": 0.005, "time_limit_hours": 24
            },
            "position_size_ratio": 0.5
        }
    })
    
    # 리스크 및 포트폴리오 관리 (기존 v2.0 유지)
    MAX_POSITION_SIZE: float = 0.05
    MAX_TOTAL_EXPOSURE: float = 0.20
    MAX_CONCURRENT_POSITIONS: int = 3
    ALLOW_SAME_COIN_DUPLICATE: bool = False
    MAX_DAILY_LOSS: float = 0.05
    MAX_DAILY_TRADES: int = 10
    COOLDOWN_AFTER_CONSECUTIVE_LOSSES: int = 3
    COOLDOWN_HOURS: int = 2
    MIN_TRADE_INTERVAL_MINUTES: int = 30

def load_strategy_config(path: str = "config/strategy_v3.yaml") -> StrategyConfig:
    """
    YAML 파일에서 전략 설정을 로드합니다. 파일이 없으면 기본값을 사용합니다.
    YAML 구조를 StrategyConfig 필드에 매핑합니다.
    """
    config_path = Path(path)
    if not config_path.exists():
        return StrategyConfig()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not data:
                return StrategyConfig()

        # YAML 구조를 StrategyConfig 필드에 매핑
        kwargs = {}

        # regime_detection 섹션 매핑
        if "regime_detection" in data:
            rd = data["regime_detection"]
            if "ma_fast_period" in rd:
                kwargs["MA_FAST_PERIOD"] = rd["ma_fast_period"]
            if "ma_slow_period" in rd:
                kwargs["MA_SLOW_PERIOD"] = rd["ma_slow_period"]
            if "bull_threshold_pct" in rd:
                kwargs["BULL_THRESHOLD_PCT"] = rd["bull_threshold_pct"]
            if "bear_threshold_pct" in rd:
                kwargs["BEAR_THRESHOLD_PCT"] = rd["bear_threshold_pct"]

        # data 섹션 매핑
        if "data" in data:
            d = data["data"]
            if "min_hourly_candles_for_regime" in d:
                kwargs["MIN_HOURLY_CANDLES_FOR_REGIME"] = d["min_hourly_candles_for_regime"]

        # regimes 섹션 매핑
        if "regimes" in data:
            kwargs["REGIMES"] = data["regimes"]

        return StrategyConfig(**kwargs)
    except Exception as e:
        print(f"[Warning] Failed to load strategy config: {e}. Using defaults.")
        return StrategyConfig()

# ========== 모드 전환 스위치 (v3.0에서는 StrategyConfig 내부에 통합 가능) ==========
def get_config() -> StrategyConfig:
    return load_strategy_config()
