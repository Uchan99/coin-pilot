import pandas as pd
from typing import Dict
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

def get_all_indicators(df: pd.DataFrame) -> Dict:
    """
    전략 수행에 필요한 모든 보조 지표를 한 번에 계산하여 마지막 행의 값을 반환합니다.

    Args:
        df: 'open', 'high', 'low', 'close', 'volume' 컬럼을 가진 DataFrame

    Returns:
        Dict: 계산된 지표 값들이 담긴 딕셔너리
    """
    # 1. RSI (14)
    rsi_series = calculate_rsi(df['close'], period=14)

    # 2. MA (200) - 추세 필터용
    ma_200_series = calculate_ma(df['close'], period=200)

    # 3. Bollinger Bands (20, 2.0)
    bb_df = calculate_bb(df['close'], period=20, std_dev=2.0)

    # 4. Volume Ratio (20)
    vol_ratio = calculate_volume_ratio(df['volume'], period=20)

    # 마지막 시점의 데이터를 딕셔너리로 구성
    return {
        "rsi": float(rsi_series.iloc[-1]),
        "ma_200": float(ma_200_series.iloc[-1]),
        "bb_lower": float(bb_df['BBL'].iloc[-1]),
        "bb_mid": float(bb_df['BBM'].iloc[-1]),
        "bb_upper": float(bb_df['BBU'].iloc[-1]),
        "vol_ratio": vol_ratio,
        "close": float(df['close'].iloc[-1]),
        "volume": float(df['volume'].iloc[-1])
    }
