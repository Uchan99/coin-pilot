"""
다중 근거 기술적 분석(Multi-Evidence TA) 피처 계산 모듈.
Plan 35: 오더블럭(OB) / FVG / 스윙 프렉탈 감지 + Unmitigated 추적 + 구조적 R:R + HTF 추세

사용처:
  - 백테스트: scripts/backtest_v3.py --multi-evidence
  - (Phase 2 이후) 실시간: src/engine/strategy.py check_entry_signal()
"""
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np


# ──────────────────────────────────────────────
# 1. 오더블럭 (Order Block) — Unmitigated 추적
# ──────────────────────────────────────────────
def detect_order_blocks(
    df: pd.DataFrame,
    lookback: int = 168,
) -> Dict:
    """
    최근 lookback(기본 7일, 1시간봉) 캔들에서 장악형 캔들(Engulfing) 감지 후
    미해소(Unmitigated) 구간만 반환.

    장악형 판단:
    - 강세 OB: 음봉 → 양봉, 양봉 몸통이 음봉 몸통을 완전히 감싸는 패턴
    - 약세 OB: 양봉 → 음봉, 음봉 몸통이 양봉 몸통을 완전히 감싸는 패턴
    해소(Mitigation): 이후 캔들 종가가 OB 구간 내부를 침범하면 해소 처리
    """
    if len(df) < 2:
        return _empty_ob_result()

    start = max(0, len(df) - lookback)
    current_price = df.iloc[-1]["close"]

    bullish_obs: List[Dict] = []
    bearish_obs: List[Dict] = []

    for i in range(start + 1, len(df)):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]

        prev_open, prev_close = prev["open"], prev["close"]
        curr_open, curr_close = curr["open"], curr["close"]

        prev_body_low = min(prev_open, prev_close)
        prev_body_high = max(prev_open, prev_close)
        curr_body_low = min(curr_open, curr_close)
        curr_body_high = max(curr_open, curr_close)

        # 몸통 크기가 0인 도지 캔들은 건너뜀
        if prev_body_high == prev_body_low or curr_body_high == curr_body_low:
            continue

        # 강세 OB: 이전 음봉 + 현재 양봉이 이전 몸통을 완전히 감쌈
        if prev_close < prev_open and curr_close > curr_open:
            if curr_body_low <= prev_body_low and curr_body_high >= prev_body_high:
                bullish_obs.append({
                    "price_low": prev_body_low,
                    "price_high": prev_body_high,
                    "candle_idx": i,
                    "formed_at": df.iloc[i].get("timestamp"),
                })

        # 약세 OB: 이전 양봉 + 현재 음봉이 이전 몸통을 완전히 감쌈
        if prev_close > prev_open and curr_close < curr_open:
            if curr_body_low <= prev_body_low and curr_body_high >= prev_body_high:
                bearish_obs.append({
                    "price_low": prev_body_low,
                    "price_high": prev_body_high,
                    "candle_idx": i,
                    "formed_at": df.iloc[i].get("timestamp"),
                })

    # Unmitigated 필터: OB 형성 이후 종가가 구간 내부를 침범했으면 해소
    unmitigated_bullish = _filter_unmitigated(bullish_obs, df, direction="bullish")
    unmitigated_bearish = _filter_unmitigated(bearish_obs, df, direction="bearish")

    # 현재가 기준 가장 가까운 OB
    nearest_bullish = _nearest_below(unmitigated_bullish, current_price)
    nearest_bearish = _nearest_above(unmitigated_bearish, current_price)

    # 현재가가 OB 구간 안에 있는지
    price_in_ob = any(
        ob["price_low"] <= current_price <= ob["price_high"]
        for ob in unmitigated_bullish + unmitigated_bearish
    )

    distance = _distance_to_nearest_pct(nearest_bullish, nearest_bearish, current_price)

    return {
        "unmitigated_bullish_obs": unmitigated_bullish,
        "unmitigated_bearish_obs": unmitigated_bearish,
        "nearest_bullish_ob": nearest_bullish,
        "nearest_bearish_ob": nearest_bearish,
        "distance_to_ob_pct": distance,
        "price_in_ob": price_in_ob,
        # 스코어링용 요약
        "has_bullish_ob_nearby": nearest_bullish is not None and abs(
            (current_price - nearest_bullish["price_high"]) / current_price
        ) <= 0.02,
    }


# ──────────────────────────────────────────────
# 2. FVG (Fair Value Gap) — Unmitigated 추적
# ──────────────────────────────────────────────
def detect_fvg(
    df: pd.DataFrame,
    lookback: int = 168,
) -> Dict:
    """
    최근 lookback 캔들에서 3캔들 갭 감지 후 미해소 갭만 반환.

    강세 FVG: candle[i-1].high < candle[i+1].low  (상승 갭 → 되돌림 시 지지)
    약세 FVG: candle[i-1].low > candle[i+1].high   (하락 갭 → 되돌림 시 저항)
    해소: 이후 캔들이 FVG 영역의 50% 이상을 침범하면 해소
    """
    if len(df) < 3:
        return _empty_fvg_result()

    start = max(0, len(df) - lookback)
    current_price = df.iloc[-1]["close"]

    bullish_fvgs: List[Dict] = []
    bearish_fvgs: List[Dict] = []

    for i in range(start + 1, len(df) - 1):
        prev = df.iloc[i - 1]
        nxt = df.iloc[i + 1]

        # 강세 FVG: 이전 캔들 high < 다음 캔들 low → 사이에 갭
        if prev["high"] < nxt["low"]:
            bullish_fvgs.append({
                "gap_low": prev["high"],
                "gap_high": nxt["low"],
                "candle_idx": i,
                "formed_at": df.iloc[i].get("timestamp"),
            })

        # 약세 FVG: 이전 캔들 low > 다음 캔들 high → 사이에 갭
        if prev["low"] > nxt["high"]:
            bearish_fvgs.append({
                "gap_low": nxt["high"],
                "gap_high": prev["low"],
                "candle_idx": i,
                "formed_at": df.iloc[i].get("timestamp"),
            })

    # Unmitigated 필터 (50% 이상 침범 시 해소)
    unmitigated_bullish = _filter_unmitigated_fvg(bullish_fvgs, df, direction="bullish")
    unmitigated_bearish = _filter_unmitigated_fvg(bearish_fvgs, df, direction="bearish")

    nearest_bullish = _nearest_fvg_below(unmitigated_bullish, current_price)
    price_in_fvg = any(
        fvg["gap_low"] <= current_price <= fvg["gap_high"]
        for fvg in unmitigated_bullish + unmitigated_bearish
    )

    return {
        "unmitigated_bullish_fvgs": unmitigated_bullish,
        "unmitigated_bearish_fvgs": unmitigated_bearish,
        "nearest_bullish_fvg": nearest_bullish,
        "price_in_fvg": price_in_fvg,
        # 스코어링용 요약
        "has_bullish_fvg_nearby": nearest_bullish is not None and abs(
            (current_price - nearest_bullish["gap_high"]) / current_price
        ) <= 0.02,
    }


# ──────────────────────────────────────────────
# 3. 스윙 프렉탈 (Swing Fractal)
# ──────────────────────────────────────────────
def detect_swing_fractals(
    df: pd.DataFrame,
    lookback: int = 168,
) -> Dict:
    """
    3캔들 중 가운데가 최고/최저인 프렉탈 포인트 감지.
    유동성 밀집 위치 파악 + R:R 계산의 SL/TP 기준점 제공.
    """
    if len(df) < 3:
        return _empty_fractal_result()

    start = max(0, len(df) - lookback)
    current_price = df.iloc[-1]["close"]

    swing_highs: List[Dict] = []
    swing_lows: List[Dict] = []

    for i in range(start + 1, len(df) - 1):
        prev_h = df.iloc[i - 1]["high"]
        curr_h = df.iloc[i]["high"]
        next_h = df.iloc[i + 1]["high"]

        prev_l = df.iloc[i - 1]["low"]
        curr_l = df.iloc[i]["low"]
        next_l = df.iloc[i + 1]["low"]

        if curr_h > prev_h and curr_h > next_h:
            swing_highs.append({
                "price": curr_h,
                "candle_idx": i,
                "formed_at": df.iloc[i].get("timestamp"),
            })

        if curr_l < prev_l and curr_l < next_l:
            swing_lows.append({
                "price": curr_l,
                "candle_idx": i,
                "formed_at": df.iloc[i].get("timestamp"),
            })

    # 현재가 아래 가장 가까운 스윙 저점
    nearest_low = None
    for sl in reversed(swing_lows):
        if sl["price"] < current_price:
            nearest_low = sl
            break

    # 현재가 위 가장 가까운 스윙 고점
    nearest_high = None
    for sh in reversed(swing_highs):
        if sh["price"] > current_price:
            nearest_high = sh
            break

    near_support = False
    if nearest_low:
        near_support = abs(current_price - nearest_low["price"]) / current_price <= 0.02

    return {
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
        "nearest_swing_low": nearest_low,
        "nearest_swing_high": nearest_high,
        "near_swing_support": near_support,
    }


# ──────────────────────────────────────────────
# 4. 구조적 R:R 사전 필터
# ──────────────────────────────────────────────
def calculate_structural_rr(
    current_price: float,
    structural_sl: Optional[float],
    structural_tp: Optional[float],
    atr_14: float,
    sl_buffer_multiplier: float = 0.5,
) -> Dict:
    """
    구조적 손절/익절 기반 R:R 비율 사전 계산.
    structural_sl: OB 하단 또는 스윙 저점
    structural_tp: 스윙 고점 또는 약세 OB
    SL에 ATR 버퍼를 추가하여 노이즈 방지.
    """
    if structural_sl is None or structural_tp is None or atr_14 <= 0:
        return {"rr_ratio": 0.0, "rr_valid": False, "sl_price": None, "tp_price": None,
                "risk_pct": 0.0, "reward_pct": 0.0}

    sl_price = structural_sl - (atr_14 * sl_buffer_multiplier)
    tp_price = structural_tp

    risk = current_price - sl_price
    reward = tp_price - current_price

    if risk <= 0 or reward <= 0:
        return {"rr_ratio": 0.0, "rr_valid": False, "sl_price": sl_price, "tp_price": tp_price,
                "risk_pct": 0.0, "reward_pct": 0.0}

    rr_ratio = reward / risk
    return {
        "sl_price": sl_price,
        "tp_price": tp_price,
        "risk_pct": risk / current_price * 100,
        "reward_pct": reward / current_price * 100,
        "rr_ratio": round(rr_ratio, 2),
        "rr_valid": rr_ratio >= 3.0,
    }


# ──────────────────────────────────────────────
# 5. 상위 타임프레임(HTF) 추세 정렬
# ──────────────────────────────────────────────
def resample_to_4h(df_1h: pd.DataFrame) -> pd.DataFrame:
    """
    1시간봉을 4시간봉으로 리샘플링.
    입력 df는 timestamp/open/high/low/close/volume 컬럼 필요.
    """
    df = df_1h.copy()
    if "timestamp" in df.columns:
        df = df.set_index("timestamp")

    resampled = df.resample("4h").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()

    return resampled.reset_index()


def calculate_htf_trend(df_1h: pd.DataFrame) -> Dict:
    """
    1시간봉을 4시간봉으로 리샘플링하여 상위 추세 방향 판단.

    판단 기준:
    - 4시간봉 MA20 기울기: 최근 3봉의 MA20 변화량
    - 최근 3개 4시간봉 고점/저점 추세: HH+HL=상승, LH+LL=하락
    """
    df_4h = resample_to_4h(df_1h)

    if len(df_4h) < 20:
        return {"htf_trend": "NEUTRAL", "htf_aligned": True, "htf_ma20_slope": 0.0}

    df_4h["ma20"] = df_4h["close"].rolling(20).mean()
    recent = df_4h.tail(4).dropna(subset=["ma20"])

    if len(recent) < 3:
        return {"htf_trend": "NEUTRAL", "htf_aligned": True, "htf_ma20_slope": 0.0}

    # MA20 기울기 (최근 3봉 평균 변화율)
    ma_values = recent["ma20"].values
    slope = (ma_values[-1] - ma_values[0]) / ma_values[0] * 100

    # 고점/저점 패턴
    highs = recent["high"].values[-3:]
    lows = recent["low"].values[-3:]

    higher_highs = highs[-1] > highs[-2] and highs[-2] > highs[-3]
    higher_lows = lows[-1] > lows[-2] and lows[-2] > lows[-3]
    lower_highs = highs[-1] < highs[-2] and highs[-2] < highs[-3]
    lower_lows = lows[-1] < lows[-2] and lows[-2] < lows[-3]

    if (higher_highs and higher_lows) or slope > 0.5:
        trend = "BULLISH"
    elif (lower_highs and lower_lows) or slope < -0.5:
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    return {
        "htf_trend": trend,
        "htf_aligned": True,  # 매수 전략 기준, BEARISH가 아니면 정렬
        "htf_ma20_slope": round(slope, 3),
    }


# ──────────────────────────────────────────────
# 6. 다중 근거 스코어링 종합
# ──────────────────────────────────────────────
def score_multi_evidence(
    ob_result: Dict,
    fvg_result: Dict,
    fractal_result: Dict,
    rr_result: Dict,
    htf_result: Dict,
) -> Dict:
    """
    각 피처 결과를 종합하여 진입 점수 산출.

    스코어링 규칙:
    - 현재가가 미해소 강세 OB 내/근처(2%): +1점
    - 현재가가 미해소 강세 FVG 내/근처(2%): +1점
    - 현재가가 스윙 저점 근처(2% 이내): +1점
    - R:R >= 3.0: +1점 (필수 조건, 미충족 시 총점 0)
    - HTF 추세 정렬 (BEARISH 아님): +1점
    """
    details: List[str] = []
    score = 0

    # R:R 필수 조건 체크 먼저
    if not rr_result.get("rr_valid", False):
        return {
            "total_score": 0,
            "details": ["FAIL: R:R < 3.0 (필수 조건 미충족)"],
            "entry_eligible": False,
            "structural_sl": rr_result.get("sl_price"),
            "structural_tp": rr_result.get("tp_price"),
            "rr_ratio": rr_result.get("rr_ratio", 0),
        }

    score += 1
    details.append(f"R:R {rr_result['rr_ratio']}:1 (≥ 3.0)")

    # OB 점수
    if ob_result.get("price_in_ob") or ob_result.get("has_bullish_ob_nearby"):
        score += 1
        details.append("강세 OB 근처/내부")

    # FVG 점수
    if fvg_result.get("price_in_fvg") or fvg_result.get("has_bullish_fvg_nearby"):
        score += 1
        details.append("강세 FVG 근처/내부")

    # 프렉탈 점수
    if fractal_result.get("near_swing_support"):
        score += 1
        details.append("스윙 저점 근처 (지지)")

    # HTF 점수
    if htf_result.get("htf_trend") != "BEARISH":
        score += 1
        details.append(f"HTF 추세 정렬 ({htf_result.get('htf_trend')})")

    return {
        "total_score": score,
        "details": details,
        "entry_eligible": score >= 2,  # 최소 2개 근거 필수
        "structural_sl": rr_result.get("sl_price"),
        "structural_tp": rr_result.get("tp_price"),
        "rr_ratio": rr_result.get("rr_ratio", 0),
    }


# ──────────────────────────────────────────────
# 7. ATR 계산 (R:R 필터용)
# ──────────────────────────────────────────────
def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range 계산 (1시간봉 기준)."""
    high = df["high"]
    low = df["low"]
    close = df["close"].shift(1)

    tr = pd.concat([
        high - low,
        (high - close).abs(),
        (low - close).abs(),
    ], axis=1).max(axis=1)

    return tr.rolling(window=period).mean()


# ──────────────────────────────────────────────
# 내부 유틸리티 함수
# ──────────────────────────────────────────────
def _filter_unmitigated(
    obs: List[Dict], df: pd.DataFrame, direction: str,
) -> List[Dict]:
    """OB가 이후 캔들에 의해 해소되었는지 필터."""
    result = []
    for ob in obs:
        idx = ob["candle_idx"]
        mitigated = False
        for j in range(idx + 1, len(df)):
            if direction == "bullish":
                # 강세 OB: 종가가 OB 하단 아래로 떨어지면 해소
                if df.iloc[j]["close"] < ob["price_low"]:
                    mitigated = True
                    break
            else:
                # 약세 OB: 종가가 OB 상단 위로 올라가면 해소
                if df.iloc[j]["close"] > ob["price_high"]:
                    mitigated = True
                    break
        if not mitigated:
            result.append(ob)
    return result


def _filter_unmitigated_fvg(
    fvgs: List[Dict], df: pd.DataFrame, direction: str,
) -> List[Dict]:
    """FVG가 이후 캔들에 의해 50% 이상 침범되었는지 필터."""
    result = []
    for fvg in fvgs:
        idx = fvg["candle_idx"]
        gap_mid = (fvg["gap_low"] + fvg["gap_high"]) / 2
        mitigated = False
        for j in range(idx + 2, len(df)):  # FVG는 3캔들이므로 idx+2부터
            if direction == "bullish":
                # 강세 FVG: 종가가 갭 중간 아래로 들어오면 해소
                if df.iloc[j]["low"] <= gap_mid:
                    mitigated = True
                    break
            else:
                # 약세 FVG: 종가가 갭 중간 위로 올라오면 해소
                if df.iloc[j]["high"] >= gap_mid:
                    mitigated = True
                    break
        if not mitigated:
            result.append(fvg)
    return result


def _nearest_below(obs: List[Dict], price: float) -> Optional[Dict]:
    """현재가 아래에서 가장 가까운 OB."""
    candidates = [ob for ob in obs if ob["price_high"] <= price]
    if not candidates:
        return None
    return max(candidates, key=lambda x: x["price_high"])


def _nearest_above(obs: List[Dict], price: float) -> Optional[Dict]:
    """현재가 위에서 가장 가까운 OB."""
    candidates = [ob for ob in obs if ob["price_low"] >= price]
    if not candidates:
        return None
    return min(candidates, key=lambda x: x["price_low"])


def _nearest_fvg_below(fvgs: List[Dict], price: float) -> Optional[Dict]:
    """현재가 아래에서 가장 가까운 FVG."""
    candidates = [fvg for fvg in fvgs if fvg["gap_high"] <= price]
    if not candidates:
        return None
    return max(candidates, key=lambda x: x["gap_high"])


def _distance_to_nearest_pct(
    nearest_bullish: Optional[Dict],
    nearest_bearish: Optional[Dict],
    current_price: float,
) -> float:
    """현재가와 가장 가까운 OB까지 거리(%)."""
    distances = []
    if nearest_bullish:
        distances.append(abs(current_price - nearest_bullish["price_high"]) / current_price * 100)
    if nearest_bearish:
        distances.append(abs(nearest_bearish["price_low"] - current_price) / current_price * 100)
    return min(distances) if distances else 999.0


def _empty_ob_result() -> Dict:
    return {
        "unmitigated_bullish_obs": [], "unmitigated_bearish_obs": [],
        "nearest_bullish_ob": None, "nearest_bearish_ob": None,
        "distance_to_ob_pct": 999.0, "price_in_ob": False,
        "has_bullish_ob_nearby": False,
    }


def _empty_fvg_result() -> Dict:
    return {
        "unmitigated_bullish_fvgs": [], "unmitigated_bearish_fvgs": [],
        "nearest_bullish_fvg": None, "price_in_fvg": False,
        "has_bullish_fvg_nearby": False,
    }


def _empty_fractal_result() -> Dict:
    return {
        "swing_highs": [], "swing_lows": [],
        "nearest_swing_low": None, "nearest_swing_high": None,
        "near_swing_support": False,
    }
