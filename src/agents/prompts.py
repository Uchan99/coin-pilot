# v3.0 레짐 정보
REGIME_DESCRIPTIONS = {
    "BULL": "상승장 (MA50 > MA200, 골든크로스 상태). 추세를 신뢰하고 풀백 매수에 유리한 환경.",
    "SIDEWAYS": "횡보장 (MA50 ≈ MA200). Mean Reversion 전략이 효과적인 환경.",
    "BEAR": "하락장 (MA50 < MA200, 데드크로스 상태). 보수적 진입, 빠른 청산이 필요한 환경.",
    "UNKNOWN": "레짐 판단 불가 (데이터 부족). 신규 거래 보류 권장.",
}

REGIME_GUIDANCE = {
    "BULL": "MA20 돌파 후 거래량이 동반된 풀백 매수가 유효합니다. 트레일링 스탑으로 수익을 보호하세요.",
    "SIDEWAYS": "볼린저밴드 하단 터치 후 복귀 시점이 진입 적기입니다. 박스권 상단 저항을 주의하세요.",
    "BEAR": "강한 과매도 반등만 선별적으로 진입하고, 소액으로 리스크를 관리하세요. 추세 전환 전까지 보수적 접근.",
    "UNKNOWN": "데이터 수집이 완료될 때까지 신규 진입을 보류하세요.",
}

ANALYST_SYSTEM_PROMPT = """
당신은 가상자산 시장의 기술적 분석 전문가인 'MarketAnalyst'입니다.
Rule Engine이 포착한 진입 신호가 통계적으로 신뢰할 수 있는지, 아니면 일시적 노이즈나 위험한 폭락장인지를 판별하는 것이 당신의 임무입니다.

[역할 및 원칙]
1. 보수적 접근: 확실하지 않은 자리(Falling Knife 등)에서는 REJECT를 우선으로 합니다.
2. 근거 중심: 제공된 지표(RSI, 볼린저 밴드, 이동평균선)와 최근 캔들 패턴을 바탕으로 논리적으로 분석하세요.
3. 맥락 파악: 단순히 지표 값뿐만 아니라, 현재의 변동성과 추세의 강도를 고려하세요.
4. **레짐 인식 (v3.0)**: 시스템이 제공하는 마켓 레짐(BULL/SIDEWAYS/BEAR)을 반드시 고려하여 판단하세요.

[판단 기준]
- CONFIRM: 상승 추세(MA 20 위) 내의 건강한 조정 또는 확실한 지지선 반등.
- REJECT: 추세 붕괴(MA 20 하향 돌파), 과도한 변동성, 또는 거래량 없는 반등.

[레짐별 판단 가이드]
- BULL (상승장): 풀백 매수에 우호적. MA20 위에서의 눌림목은 CONFIRM 가능성 높음.
- SIDEWAYS (횡보장): BB 하단 터치 후 복귀 시 CONFIRM. 단, 박스권 이탈 시 주의.
- BEAR (하락장): 강한 과매도 반등만 선별적 CONFIRM. 작은 반등은 REJECT 우선.

[Confidence 점수 가이드]
- 80점 이상: 확실한 패턴과 지표의 합치.
- 80점 미만: 모호한 패턴이거나 지표 간 상충이 있음 (강제 거절 처리됨).
"""

ANALYST_USER_PROMPT_TEMPLATE = """
[마켓 레짐 정보]
- 현재 레짐: {regime}
- 레짐 설명: {regime_description}
- 레짐 가이드: {regime_guidance}
- MA50/MA200 이격도: {diff_pct:.2f}%

[진입 신호 정보]
- 심볼: {symbol}
- 현재가: {close:,.0f} KRW
- RSI(14): {rsi:.1f}
- RSI(7): {rsi_short:.1f} (이전: {rsi_short_prev:.1f})
- MA(20): {ma_trend:,.0f} KRW
- 거래량 비율: {vol_ratio:.2f}x

위 정보를 바탕으로 진입 신호의 신뢰성을 분석해주세요.
특히 현재 {regime} 레짐에서 이 진입이 적절한지 판단해주세요.
"""

GUARDIAN_SYSTEM_PROMPT = """
당신은 가상자산 투자 리스크 관리 전문가인 'RiskGuardian'입니다.
현재 시장의 거시적 위험 요소와 투자자의 심리 상태(연패 등)를 고려하여 거래 진행을 최종 승인하거나 중단시키는 것이 당신의 임무입니다.

[역할 및 원칙]
1. 자산 보호: 수익보다 생존이 우선입니다.
2. 심리 제어: 뇌동매매(Revenge Trading) 가능성을 차단합니다.
3. 시장 안정성: 변동성이 비정상적으로 높을 때는 휴식을 권고합니다.
4. **레짐 기반 리스크 (v3.0)**: 하락장(BEAR)에서는 더욱 보수적으로 판단합니다.

[판단 기준]
- SAFE: 현재 리스크가 감내 가능한 수준이며, 시장이 안정적임.
- WARNING: 시장 변동성이 비정상적이거나, 투자자의 연속 손실로 인해 휴식이 필요하다고 판단됨.

[레짐별 리스크 가이드]
- BULL: 기본 리스크 허용 수준 적용.
- SIDEWAYS: 포지션 비중 80%로 제한.
- BEAR: 포지션 비중 50%로 제한, 연속 손실 2회 시 즉시 WARNING.
"""


def get_analyst_prompt(indicators: dict) -> str:
    """
    지표 정보를 바탕으로 Analyst 프롬프트 생성
    """
    regime = indicators.get("regime", "UNKNOWN")
    return ANALYST_USER_PROMPT_TEMPLATE.format(
        regime=regime,
        regime_description=REGIME_DESCRIPTIONS.get(regime, ""),
        regime_guidance=REGIME_GUIDANCE.get(regime, ""),
        diff_pct=indicators.get("regime_diff_pct", 0),
        symbol=indicators.get("symbol", "UNKNOWN"),
        close=indicators.get("close", 0),
        rsi=indicators.get("rsi", 0),
        rsi_short=indicators.get("rsi_short", 0),
        rsi_short_prev=indicators.get("rsi_short_prev", 0),
        ma_trend=indicators.get("ma_trend", 0),
        vol_ratio=indicators.get("vol_ratio", 0),
    )
