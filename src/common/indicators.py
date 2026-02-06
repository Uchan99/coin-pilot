import pandas as pd
from typing import Dict, Optional
import numpy as np

class InsufficientDataError(Exception):
    """지표 계산을 위한 데이터가 부족할 때 발생하는 예외"""
    pass

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    RSI (Relative Strength Index)를 계산합니다.
    pandas-ta 없이 직접 구현.

    Args:
        series: 종가(Close) 데이터 시리즈
        period: 계산 기간 (기본값: 14)

    Returns:
        pd.Series: RSI 값 (0~100)

    Raises:
        InsufficientDataError: 데이터가 계산 기간보다 적을 경우
    """
    if len(series) < period + 1:
        raise InsufficientDataError(f"RSI 계산을 위해 최소 {period + 1}개의 데이터가 필요합니다. (현재: {len(series)}개)")

    # 가격 변화량 계산
    delta = series.diff()

    # 상승분과 하락분 분리
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    # Wilder's smoothing (EMA와 유사)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    # RS 및 RSI 계산
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi

def calculate_ma(series: pd.Series, period: int = 200) -> pd.Series:
    """
    단순 이동 평균 (Simple Moving Average)을 계산합니다.

    Args:
        series: 가격 데이터 시리즈
        period: 계산 기간 (기본값: 200)

    Returns:
        pd.Series: SMA 값

    Raises:
        InsufficientDataError: 데이터가 계산 기간보다 적을 경우
    """
    if len(series) < period:
        raise InsufficientDataError(f"MA 계산을 위해 최소 {period}개의 데이터가 필요합니다. (현재: {len(series)}개)")

    return series.rolling(window=period).mean()

def calculate_bb(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """
    볼린저 밴드 (Bollinger Bands)를 계산합니다.

    Args:
        series: 종가 데이터 시리즈
        period: 계산 기간 (기본값: 20)
        std_dev: 표준편차 배수 (기본값: 2.0)

    Returns:
        pd.DataFrame: [BBL, BBM, BBU] (하단, 중앙, 상단)

    Raises:
        InsufficientDataError: 데이터가 계산 기간보다 적을 경우
    """
    if len(series) < period:
        raise InsufficientDataError(f"Bollinger Bands 계산을 위해 최소 {period}개의 데이터가 필요합니다. (현재: {len(series)}개)")

    # 중앙선 (SMA)
    middle = series.rolling(window=period).mean()

    # 표준편차
    std = series.rolling(window=period).std()

    # 상단/하단 밴드
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)

    return pd.DataFrame({
        'BBL': lower,
        'BBM': middle,
        'BBU': upper
    })

def calculate_volume_ratio(volume_series: pd.Series, period: int = 20) -> float:
    """
    현재 거래량이 과거 N일 평균 거래량 대비 몇 배인지 계산합니다.

    Args:
        volume_series: 거래량 데이터 시리즈
        period: 평균을 구할 기간 (기본값: 20)

    Returns:
        float: 거래량 비율 (현재 거래량 / 과거 평균 거래량)

    Raises:
        InsufficientDataError: 데이터가 기간보다 적을 경우
    """
    if len(volume_series) < period + 1:
        raise InsufficientDataError(f"거래량 비율 계산을 위해 최소 {period + 1}개의 데이터가 필요합니다.")

    # 현재 거래량을 제외한 과거 N일의 평균 거래량 계산
    previous_volumes = volume_series.iloc[-(period+1):-1]
    avg_volume = previous_volumes.mean()

    if avg_volume == 0:
        return 0.0

    current_volume = volume_series.iloc[-1]
    return float(current_volume / avg_volume)

def resample_to_hourly(df_1m: pd.DataFrame) -> pd.DataFrame:
    """
    1분봉 데이터를 1시간봉으로 리샘플링

    Args:
        df_1m: 1분봉 DataFrame (columns: timestamp, open, high, low, close, volume)
               또는 (columns: timestamp, open_price, high_price, low_price, close_price, volume)

    Returns:
        1시간봉 DataFrame (columns: open, high, low, close, volume)
    """
    df = df_1m.copy()
    if 'timestamp' in df.columns:
        df = df.set_index('timestamp')

    # 컬럼명 감지 (open vs open_price)
    if 'open_price' in df.columns:
        agg_dict = {
            'open_price': 'first',
            'high_price': 'max',
            'low_price': 'min',
            'close_price': 'last',
            'volume': 'sum'
        }
    else:
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }

    resampled = df.resample('1h').agg(agg_dict).dropna()

    # 컬럼명 통일
    resampled.columns = ['open', 'high', 'low', 'close', 'volume']
    return resampled

def detect_regime(ma50: Optional[float], ma200: Optional[float]) -> str:
    """
    마켓 레짐 감지

    Args:
        ma50: 50기간(1시간봉) 이동평균선 값 (None이면 데이터 부족)
        ma200: 200기간(1시간봉) 이동평균선 값 (None이면 데이터 부족)

    Returns:
        "BULL" | "SIDEWAYS" | "BEAR" | "UNKNOWN"
    """
    # Fallback: 데이터 부족 시 UNKNOWN 반환
    if ma50 is None or ma200 is None or np.isnan(ma50) or np.isnan(ma200):
        return "UNKNOWN"

    diff_pct = (ma50 - ma200) / ma200 * 100

    if diff_pct > 2.0:
        return "BULL"       # 상승장: MA50이 MA200보다 2% 이상 위
    elif diff_pct < -2.0:
        return "BEAR"       # 하락장: MA50이 MA200보다 2% 이상 아래
    else:
        return "SIDEWAYS"   # 횡보장: MA50과 MA200 차이 ±2% 이내

def check_bb_touch_recovery(df: pd.DataFrame, lookback: int = 3) -> bool:
    """
    최근 N캔들 내 볼린저밴드 하단 터치 후 현재 복귀 여부 판정

    Args:
        df: DataFrame (columns: close, bb_lower)
        lookback: 터치 확인 캔들 수 (기본 3)

    Returns:
        True이면 BB 하단 터치 후 복귀 확인
    """
    if len(df) < lookback + 1:
        return False

    recent = df.tail(lookback + 1)
    # 직전 N캔들 중 BB 하단 이하 터치가 있었는지
    touched = any(recent['close'].iloc[:-1] <= recent['bb_lower'].iloc[:-1])
    # 현재 캔들은 BB 하단 위에 있는지
    recovered = recent['close'].iloc[-1] > recent['bb_lower'].iloc[-1]
    return touched and recovered

def calculate_volume_ratios(volume_series: pd.Series, period: int = 20) -> pd.Series:
    """
    각 시점의 거래량이 과거 N일 평균 거래량 대비 몇 배인지 시리즈로 계산합니다.
    (v3.1 거래량 급증 체크용)

    Args:
        volume_series: 거래량 데이터 시리즈
        period: 평균을 구할 기간 (기본값: 20)

    Returns:
        pd.Series: 각 시점의 거래량 비율
    """
    # 각 시점에서 직전 N개의 평균 거래량 대비 비율 계산
    avg_volume = volume_series.rolling(window=period).mean().shift(1)
    vol_ratios = volume_series / avg_volume
    return vol_ratios.fillna(0.0)


def get_all_indicators(df: pd.DataFrame, ma_period: int = 20,
                       rsi_period: int = 14, rsi_short_period: int = 7) -> Dict:
    """
    전략 수행에 필요한 모든 보조 지표를 한 번에 계산하여 마지막 행의 값을 반환합니다.

    Args:
        df: 'open', 'high', 'low', 'close', 'volume' 컬럼을 가진 DataFrame
        ma_period: 추세 필터용 이동평균 기간 (기본값: 20)
        rsi_period: 중기 RSI 기간 (기본값: 14)
        rsi_short_period: 단기 RSI 기간 (기본값: 7, 모멘텀 반전 감지용)

    Returns:
        Dict: 계산된 지표 값들이 담긴 딕셔너리
    """
    # 1. RSI (14) - 중기 과매도 판단용
    rsi_series = calculate_rsi(df['close'], period=rsi_period)

    # 2. RSI (7) - 단기 모멘텀 반전 감지용 (현재 + 이전값 필요)
    rsi_short_series = calculate_rsi(df['close'], period=rsi_short_period)

    # 3. MA (추세 필터용)
    ma_trend_series = calculate_ma(df['close'], period=ma_period)

    # 4. Bollinger Bands (20, 2.0)
    bb_df = calculate_bb(df['close'], period=20, std_dev=2.0)

    # 5. Volume Ratio (20) - 현재 시점
    vol_ratio = calculate_volume_ratio(df['volume'], period=20)

    # 6. Volume Ratios (v3.1) - 시리즈 (거래량 급증 체크용)
    vol_ratios_series = calculate_volume_ratios(df['volume'], period=20)
    # 최근 5캔들의 거래량 비율 리스트 (volume_surge_check에서 사용)
    recent_vol_ratios = vol_ratios_series.tail(5).tolist()

    # 마지막 시점의 데이터를 딕셔너리로 구성
    return {
        # RSI 듀얼 타임프레임
        "rsi": float(rsi_series.iloc[-1]),              # RSI(14) 현재
        "rsi_short": float(rsi_short_series.iloc[-1]),  # RSI(7) 현재
        "rsi_short_prev": float(rsi_short_series.iloc[-2]) if len(rsi_short_series) >= 2 else None,  # RSI(7) 이전 (상향돌파 감지용)

        # MA 추세
        "ma_trend": float(ma_trend_series.iloc[-1]),
        "ma_period": ma_period,

        # 볼린저 밴드
        "bb_lower": float(bb_df['BBL'].iloc[-1]),
        "bb_mid": float(bb_df['BBM'].iloc[-1]),
        "bb_upper": float(bb_df['BBU'].iloc[-1]),

        # 거래량
        "vol_ratio": vol_ratio,
        "recent_vol_ratios": recent_vol_ratios,  # v3.1: 최근 5캔들 거래량 비율

        # 가격
        "close": float(df['close'].iloc[-1]),
        "volume": float(df['volume'].iloc[-1])
    }
