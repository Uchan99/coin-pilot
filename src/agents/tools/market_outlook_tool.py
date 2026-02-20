from typing import Any, Dict

import numpy as np
import pandas as pd

from src.agents.tools._db import fetch_all, fetch_one

DRIVER_LABEL_MAP = {
    "hack": "보안 사고",
    "exploit": "보안 사고",
    "breach": "보안 사고",
    "해킹": "보안 사고",
    "lawsuit": "규제/법률 이슈",
    "sec": "규제/법률 이슈",
    "규제": "규제/법률 이슈",
    "소송": "규제/법률 이슈",
    "liquidation": "급락/청산 압력",
    "crash": "급락/청산 압력",
    "dump": "급락/청산 압력",
    "파산": "급락/청산 압력",
    "outage": "거래소 운영 이슈",
    "suspend": "거래소 운영 이슈",
    "중단": "거래소 운영 이슈",
    "approval": "제도권 수용/승인",
    "adoption": "제도권 수용/채택",
    "etf": "기관/ETF 이슈",
}


def _risk_level_ko(level: str | None) -> str:
    mapping = {"HIGH": "높음", "MEDIUM": "보통", "LOW": "낮음"}
    return mapping.get(level or "", "알 수 없음")


def _to_driver_labels(drivers: Any) -> list[str]:
    if not isinstance(drivers, (list, tuple)):
        return []
    labels = []
    for raw in drivers:
        token = str(raw).lower()
        labels.append(DRIVER_LABEL_MAP.get(token, str(raw)))
    return sorted(set(labels))


def _build_news_readable_summary(
    *,
    risk_level: str | None,
    risk_score: float | None,
    drivers: Any,
    raw_summary: str | None,
) -> str | None:
    labels = _to_driver_labels(drivers)
    level_ko = _risk_level_ko(risk_level)

    if risk_score is not None and labels:
        return (
            f"최근 뉴스 흐름은 {', '.join(labels[:3])} 이슈가 중심이며 "
            f"종합 리스크는 {level_ko}({risk_score:.1f}) 수준입니다."
        )

    if risk_score is not None:
        return f"최근 뉴스 종합 리스크는 {level_ko}({risk_score:.1f}) 수준입니다."

    if raw_summary:
        # 기존 저장 데이터가 영어 헤드라인 나열인 경우라도 앞 문장(요약 헤더)만 사용합니다.
        return str(raw_summary).split("주요 이슈")[0].strip()

    return None


def _compute_rsi(prices: pd.Series, window: int = 14) -> float | None:
    if len(prices) < window + 1:
        return None

    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()

    if avg_loss.iloc[-1] == 0:
        return 100.0

    rs = avg_gain.iloc[-1] / avg_loss.iloc[-1]
    return float(100 - (100 / (1 + rs)))


def run_market_outlook_tool(symbol: str = "KRW-BTC") -> Dict[str, Any]:
    """
    심볼별 시장 상태(추세/모멘텀/변동성/레짐)를 요약합니다.
    뉴스 리스크 점수는 Phase 4에서 추가될 수 있어 현재는 None으로 반환합니다.
    """
    rows = fetch_all(
        """
        SELECT timestamp, close_price
        FROM market_data
        WHERE symbol = :symbol
        ORDER BY timestamp DESC
        LIMIT 240
        """,
        {"symbol": symbol},
    )

    if not rows:
        return {
            "symbol": symbol,
            "status": "NO_DATA",
            "message": "시장 데이터가 부족해 분석할 수 없습니다.",
            "news_risk_score": None,
        }

    df = pd.DataFrame(rows)
    df["close_price"] = pd.to_numeric(df["close_price"], errors="coerce")
    df = df.dropna(subset=["close_price"]).sort_values("timestamp")

    if df.empty:
        return {
            "symbol": symbol,
            "status": "NO_DATA",
            "message": "가격 데이터가 비어 있습니다.",
            "news_risk_score": None,
        }

    close = df["close_price"].astype(float)
    current_price = float(close.iloc[-1])

    ma20 = float(close.tail(20).mean()) if len(close) >= 20 else None
    ma50 = float(close.tail(50).mean()) if len(close) >= 50 else None
    ma200 = float(close.tail(200).mean()) if len(close) >= 200 else None

    rsi14 = _compute_rsi(close, window=14)

    returns = close.pct_change().dropna()
    volatility_pct = float(returns.tail(60).std() * np.sqrt(60) * 100.0) if len(returns) >= 30 else None
    momentum_1h_pct = (
        float((close.iloc[-1] - close.iloc[-60]) / close.iloc[-60] * 100.0)
        if len(close) >= 60 and close.iloc[-60] > 0
        else None
    )

    coin_symbol = symbol.split("-")[-1] if "-" in symbol else symbol
    regime_row = fetch_one(
        """
        SELECT regime, diff_pct, detected_at
        FROM regime_history
        WHERE coin_symbol = :coin_symbol
        ORDER BY detected_at DESC
        LIMIT 1
        """,
        {"coin_symbol": coin_symbol},
    )

    regime = regime_row.get("regime") if regime_row else "UNKNOWN"
    diff_pct = float(regime_row.get("diff_pct") or 0.0) if regime_row else 0.0

    # 마이그레이션 미적용 환경에서도 시장 브리핑 자체는 계속 동작해야 하므로
    # 뉴스 관련 테이블 조회 실패 시 None으로 안전 폴백합니다.
    news_risk_row = None
    news_summary_row = None
    try:
        news_risk_row = fetch_one(
            """
            SELECT risk_score, risk_level, drivers, window_end
            FROM news_risk_scores
            WHERE symbol = :symbol
            ORDER BY window_end DESC
            LIMIT 1
            """,
            {"symbol": symbol},
        )
        news_summary_row = fetch_one(
            """
            SELECT summary_text, window_end
            FROM news_summaries
            WHERE symbol = :symbol
            ORDER BY window_end DESC
            LIMIT 1
            """,
            {"symbol": symbol},
        )
    except Exception:
        news_risk_row = None
        news_summary_row = None

    if ma20 is not None and current_price > ma20:
        trend_signal = "MA20 상단 유지"
    elif ma20 is not None:
        trend_signal = "MA20 하단 위치"
    else:
        trend_signal = "단기 추세 판단 데이터 부족"

    return {
        "symbol": symbol,
        "status": "OK",
        "current_price": current_price,
        "rsi14": rsi14,
        "ma20": ma20,
        "ma50": ma50,
        "ma200": ma200,
        "momentum_1h_pct": momentum_1h_pct,
        "volatility_pct": volatility_pct,
        "regime": regime,
        "regime_diff_pct": diff_pct,
        "trend_signal": trend_signal,
        "news_risk_score": float(news_risk_row["risk_score"]) if news_risk_row and news_risk_row.get("risk_score") is not None else None,
        "news_risk_level": news_risk_row.get("risk_level") if news_risk_row else None,
        "news_risk_drivers": news_risk_row.get("drivers") if news_risk_row else None,
        "news_summary": _build_news_readable_summary(
            risk_level=news_risk_row.get("risk_level") if news_risk_row else None,
            risk_score=float(news_risk_row["risk_score"]) if news_risk_row and news_risk_row.get("risk_score") is not None else None,
            drivers=news_risk_row.get("drivers") if news_risk_row else None,
            raw_summary=news_summary_row.get("summary_text") if news_summary_row else None,
        ),
        "news_window_end": str(news_summary_row.get("window_end")) if news_summary_row and news_summary_row.get("window_end") else None,
    }
