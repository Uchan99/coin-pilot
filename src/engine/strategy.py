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

class MeanReversionStrategy(BaseStrategy):
    """
    過매도 구간의 반등을 노리는 평균 회귀(Mean Reversion) 전략
    - RSI, Moving Average, Bollinger Bands를 조합하여 사용
    """
    def __init__(self, 
                 rsi_threshold: float = 30.0,
                 tp_ratio: float = 0.05,
                 sl_ratio: float = 0.03,
                 max_hold_hours: int = 48):
        super().__init__("MeanReversion")
        self.rsi_threshold = rsi_threshold
        self.tp_ratio = Decimal(str(tp_ratio))
        self.sl_ratio = Decimal(str(sl_ratio))
        self.max_hold_hours = max_hold_hours

    def check_entry_signal(self, indicators: Dict) -> bool:
        """
        진입 조건 (모두 AND 만족 시):
        1. RSI < 30 (과매도)
        2. 현재가 > MA 200 (장기 상승 추세 유지 중인 낙폭 과대)
        3. 현재가 <= BB 하단 밴드 (통계적 저점)
        4. 현재 거래량 > 과거 20일 평균 거래량 * 1.5 (의미 있는 매수 유입/패닉 셀)
        """
        rsi = indicators.get("rsi")
        ma_200 = indicators.get("ma_200")
        bb_lower = indicators.get("bb_lower")
        vol_ratio = indicators.get("vol_ratio")
        close = indicators.get("close")

        # 모든 데이터 존재 여부 확인 (indicators.py에서 검증하지만 안전장치)
        if None in [rsi, ma_200, bb_lower, vol_ratio, close]:
            return False

        # 전략 로직 수행 (AND 조건)
        is_rsi_low = rsi < self.rsi_threshold
        is_above_trend = close > ma_200
        is_bb_low = close <= bb_lower
        is_vol_surge = vol_ratio > 1.5

        signal = is_rsi_low and is_above_trend and is_bb_low and is_vol_surge
        
        if signal:
            print(f"[*] [Signal: {self.name}] Entry Signal Detected! "
                  f"(RSI: {rsi:.2f}, Price: {close}, BB_L: {bb_lower:.2f}, VolRatio: {vol_ratio:.2f})")
        
        return signal

    def check_exit_signal(self, indicators: Dict, position_info: Dict) -> Tuple[bool, str]:
        """
        청산 조건 (OR 만족 시):
        1. Take Profit (+5%)
        2. Stop Loss (-3%)
        3. RSI > 70 (과매수 구간 진입)
        4. Time Exit (48시간 경과)
        """
        close = Decimal(str(indicators.get("close")))
        rsi = indicators.get("rsi")
        
        entry_price = Decimal(str(position_info.get("avg_price", 0)))
        opened_at = position_info.get("opened_at")
        
        if entry_price == 0 or not opened_at:
            return False, ""

        # 현재 수익률 계산
        pnl_ratio = (close - entry_price) / entry_price

        # 1. 익절 체크
        if pnl_ratio >= self.tp_ratio:
            return True, f"Take Profit (+{pnl_ratio*100:.2f}%)"
            
        # 2. 손절 체크
        if pnl_ratio <= -self.sl_ratio:
            return True, f"Stop Loss ({pnl_ratio*100:.2f}%)"
            
        # 3. RSI 과매수 체크
        if rsi and rsi > 70:
            return True, f"Signal Exit (RSI: {rsi:.2f} > 70)"
            
        # 4. 시간 기반 청산 체크
        now = datetime.now(timezone.utc)
        # opened_at이 aware인지 naive인지 확인하여 처리
        aware_opened_at = opened_at if opened_at.tzinfo else opened_at.replace(tzinfo=timezone.utc)
        
        hold_time = now - aware_opened_at
        if hold_time > timedelta(hours=self.max_hold_hours):
            return True, f"Time Exit ({hold_time.total_seconds()/3600:.1f} hours passed)"
            
        return False, ""
