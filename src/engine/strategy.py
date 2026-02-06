from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta, timezone

class BaseStrategy(ABC):
    """
    모든 매매 전략의 기반이 되는 추상 클래스
    """
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def check_entry_signal(self, indicators: Dict) -> bool:
        """
        진입(매수) 신호를 확인합니다.
        """
        pass

    @abstractmethod
    def check_exit_signal(self, indicators: Dict, position_info: Dict) -> Tuple[bool, str]:
        """
        청산(매도) 신호를 확인합니다.
        Returns: (신호발생여부, 청산사유)
        """
        pass

from src.config.strategy import StrategyConfig

class TrailingStop:
    """
    트레일링 스탑 관리 (v3.0)
    """
    def __init__(self, entry_price: float, trailing_stop_pct: float,
                 activation_pct: float = 0.01, high_water_mark: float = None):
        self.entry_price = entry_price
        self.high_water_mark = high_water_mark or entry_price
        self.trailing_stop_pct = trailing_stop_pct
        self.activation_pct = activation_pct
        self.activated = (high_water_mark is not None and (high_water_mark - entry_price) / entry_price >= activation_pct)

    def update(self, current_price: float) -> bool:
        """
        현재가로 트레일링 스탑 업데이트 및 청산 여부 반환
        """
        # 최고가 갱신 (현재가가 기존 최고가보다 높을 때만)
        if current_price > self.high_water_mark:
            self.high_water_mark = current_price

        # 현재 수익률
        profit_pct = (current_price - self.entry_price) / self.entry_price
        
        # 활성화 여부 업데이트: 한 번이라도 activation_pct를 넘으면 활성 상태 유지
        if not self.activated and profit_pct >= self.activation_pct:
            self.activated = True

        # 활성화 상태에서만 하락 감시
        if self.activated:
            # 청산 조건 체크: 최고가 대비 trailing_stop_pct 이상 하락 시
            stop_price = self.high_water_mark * (1 - self.trailing_stop_pct)
            if current_price <= stop_price:
                return True

        return False

class MeanReversionStrategy(BaseStrategy):
    """
    마켓 레짐 기반 적응형 평균 회귀 전략 - v3.0
    
    상승(BULL), 횡보(SIDEWAYS), 하락(BEAR) 레짐을 감지하고 
    각 상황에 맞는 진입/청산 로직을 적용함.
    """
    def __init__(self, config: StrategyConfig = None):
        super().__init__("AdaptiveMeanReversion")
        self.config = config or StrategyConfig()

    def check_entry_signal(self, indicators: Dict) -> bool:
        """
        레짐별 진입 신호 확인
        """
        regime = indicators.get("regime", "UNKNOWN")
        if regime == "UNKNOWN":
            return False

        # 레짐별 설정 로드
        regime_config = self.config.REGIMES.get(regime)
        if not regime_config:
            return False
            
        entry_config = regime_config["entry"]
        
        rsi_14 = indicators.get("rsi")
        rsi_7 = indicators.get("rsi_short")
        rsi_7_prev = indicators.get("rsi_short_prev")
        ma_20 = indicators.get("ma_trend")
        vol_ratio = indicators.get("vol_ratio")
        close = indicators.get("close")
        
        # 기본 공통 조건 (RSI 14)
        if rsi_14 is None or rsi_14 > entry_config["rsi_14_max"]:
            return False
            
        # RSI 7 반등 조건 (trigger -> recover)
        if None in [rsi_7, rsi_7_prev]:
            return False
        is_rsi_short_recovery = (rsi_7_prev < entry_config["rsi_7_trigger"]) and (rsi_7 >= entry_config["rsi_7_recover"])
        if not is_rsi_short_recovery:
            return False
            
        # MA 조건 (crossover | proximity)
        if ma_20 is None:
            return False
            
        if entry_config["ma_condition"] == "crossover":
            if close <= ma_20:
                return False
        elif entry_config["ma_condition"] == "proximity":
            proximity_pct = entry_config.get("ma_proximity_pct", 0.97)
            if close < ma_20 * proximity_pct:
                return False
                
        # 거래량 조건
        if entry_config.get("volume_ratio") is not None:
            if vol_ratio is None or vol_ratio < entry_config["volume_ratio"]:
                return False
                
        # 횡보장 전용 BB 조건
        if regime == "SIDEWAYS" and entry_config.get("bb_enabled"):
            from src.common.indicators import check_bb_touch_recovery
            # indicators에 리샘플링된 df가 포함되어 있다고 가정하거나 
            # 별도의 bb_touch_recovery 지표가 계산되어 넘어와야 함
            if not indicators.get("bb_touch_recovery", False):
                return False

        return True

    def get_adjusted_exit_config(self, entry_regime: str, current_regime: str) -> Dict:
        """
        레짐 변경 시 청산 파라미터 조정 (v3.0 섹션 6.4)

        정책:
        - Stop Loss: 기존과 새 레짐 중 타이트한(작은) 값 유지 → 리스크 확대 방지
        - 나머지(TP, 트레일링, RSI, 시간): 새 레짐 값 적용
        """
        entry_config = self.config.REGIMES.get(entry_regime, self.config.REGIMES["SIDEWAYS"])["exit"]
        current_config = self.config.REGIMES.get(current_regime, self.config.REGIMES["SIDEWAYS"])["exit"]

        # 레짐이 같으면 그대로 반환
        if entry_regime == current_regime:
            return entry_config

        # 레짐이 다르면 SL은 타이트한 쪽 유지
        adjusted = current_config.copy()
        adjusted["stop_loss_pct"] = min(entry_config["stop_loss_pct"], current_config["stop_loss_pct"])

        return adjusted

    def check_exit_signal(self, indicators: Dict, position_info: Dict) -> Tuple[bool, str]:
        """
        레짐별 청산 신호 확인 (트레일링 스탑 포함)
        레짐 변경 시 SL 타이트 유지 정책 적용 (v3.0)
        """
        close = Decimal(str(indicators.get("close")))
        rsi_14 = indicators.get("rsi")

        entry_price = Decimal(str(position_info.get("avg_price", 0)))
        opened_at = position_info.get("opened_at")
        entry_regime = position_info.get("regime", "SIDEWAYS")  # 진입 시 레짐
        current_regime = indicators.get("regime", entry_regime)  # 현재 레짐
        hwm = position_info.get("high_water_mark")

        if entry_price == 0:
            return False, ""

        # 레짐 변경 시 SL 타이트 유지 정책 적용
        exit_config = self.get_adjusted_exit_config(entry_regime, current_regime)

        # 현재 수익률
        pnl_ratio = float((close - entry_price) / entry_price)

        # 1. Stop Loss (고정) - 최우선 (레짐 변경 시 타이트한 값 적용)
        if pnl_ratio <= -exit_config["stop_loss_pct"]:
            return True, "STOP_LOSS"

        # 2. 트레일링 스탑
        ts = TrailingStop(
            entry_price=float(entry_price),
            trailing_stop_pct=exit_config["trailing_stop_pct"],
            activation_pct=exit_config["trailing_stop_activation_pct"],
            high_water_mark=float(hwm) if hwm else float(entry_price)
        )
        if ts.update(float(close)):
            # 포지션 정보의 HWM을 업데이트하기 위해 indicators에 새 HWM 저장 (상위 레벨에서 처리 필요)
            indicators["new_hwm"] = ts.high_water_mark
            return True, "TRAILING_STOP"
        indicators["new_hwm"] = ts.high_water_mark

        # 3. Take Profit (고정)
        if pnl_ratio >= exit_config["take_profit_pct"]:
            return True, "TAKE_PROFIT"

        # 4. RSI 과매수 청산 (최소 수익 조건부)
        if rsi_14 and rsi_14 > exit_config["rsi_overbought"]:
            if pnl_ratio >= exit_config["rsi_exit_min_profit_pct"]:
                return True, "RSI_OVERBOUGHT"

        # 5. 시간 초과
        if opened_at:
            now = datetime.now(timezone.utc)
            aware_opened_at = opened_at if opened_at.tzinfo else opened_at.replace(tzinfo=timezone.utc)
            hold_time = now - aware_opened_at
            if hold_time > timedelta(hours=exit_config["time_limit_hours"]):
                return True, "TIME_LIMIT"

        return False, ""
