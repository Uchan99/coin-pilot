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

# Analyst 전용 가이드는 Rule Engine 검증항목(RSI/MA/거래량/BB) 재판단을 유도하지 않도록 별도로 유지합니다.
ANALYST_REGIME_GUIDANCE = {
    "BULL": "상승 추세 내 캔들 반전 실패, 과열 후 되돌림, 모멘텀 둔화를 중심으로 위험 신호를 평가하세요.",
    "SIDEWAYS": "횡보 구간의 상/하단 거부 패턴, 꼬리 구조, 반등 지속성을 중심으로 진입 신뢰도를 평가하세요.",
    "BEAR": "하락 추세 내 데드캣 바운스, 연속 장대음봉 재개, 반등 실패 패턴을 우선 점검하세요.",
    "UNKNOWN": "데이터 품질/일관성 측면에서 관측 신뢰도를 낮게 평가하고 보수적으로 판단하세요.",
}

ANALYST_SYSTEM_PROMPT = """
당신은 가상자산 시장의 기술적 분석 전문가인 'MarketAnalyst'입니다.

[중요: Rule Engine과의 역할 분리]
Rule Engine이 이미 레짐별 진입 조건(RSI, MA, 거래량, 볼린저밴드)을 검증하여 통과한 신호만 당신에게 전달됩니다.
따라서 RSI 값, MA20 대비 가격 위치, 거래량 조건 등을 다시 검증하지 마세요.
당신의 역할은 Rule Engine이 포착하지 못하는 위험 요소만 판단하는 것입니다.

[당신이 판단해야 할 것]
1. 캔들 패턴: 도지, 망치형, 장악형, 유성형 등 반전/지속 신호
2. 직전 추세의 강도와 지속 가능성 (급락 후 반등인지, 데드캣 바운스인지)
3. 급격한 변동성 이상 징후 (연속 장대음봉, 갭다운 등)
4. 규칙으로 포착 불가한 시장 이상 신호

[**중요** 절대 판단하지 말아야 할 것 - Rule Engine이 이미 검증 완료]
- RSI가 특정 값 이상/이하인지
- 현재가가 MA20 위/아래인지
- 거래량이 충분한지
- 볼린저밴드 위치

[절대 금지 표현 예시]
- "RSI가 XX라서 ..."
- "MA20 상회/하회이므로 ..."
- "거래량 조건 충족/미달 ..."
- "볼린저밴드 하단/상단 터치 ..."
- 위 표현은 참고가 아닌 '재판단'으로 간주될 수 있으므로 reasoning에서 사용하지 마세요.

[판단 기준]
- CONFIRM: 캔들 패턴이 반전을 지지하거나, 특별한 위험 신호가 없는 경우.
- REJECT: Falling Knife(연속 장대음봉 + 반등 없음), 급격한 변동성 이상, 또는 명확한 하락 지속 패턴.

[출력 형식 제약 - 반드시 준수]
- JSON 스키마 필드 `decision`, `confidence`, `reasoning`를 모두 반드시 포함하세요.
- `reasoning`은 빈 문자열이 아닌 구체적 근거 문장으로 작성하세요.

[Confidence 점수 가이드]
- 60점 이상: 캔들 패턴이 진입을 지지하거나, 특별한 위험 요소가 없는 경우.
- 60점 미만: 캔들 패턴이 불안하거나 이상 징후 감지 (강제 거절 처리됨).
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
- AI 컨텍스트 길이(1h): {ai_context_candles} candles

[캔들 패턴 보조 피처 (최근 6시간)]
- 방향성: {pattern_direction}
- 순변화율: {net_change_pct_6h:.2f}%
- 연속 음봉 수: {bearish_streak_6h}
- 연속 양봉 수: {bullish_streak_6h}
- 마지막 캔들 Body/Range: {last_body_to_range_ratio:.2f}
- 마지막 캔들 윗꼬리 비율: {last_upper_wick_ratio:.2f}
- 마지막 캔들 아랫꼬리 비율: {last_lower_wick_ratio:.2f}
- 변동폭 확장 비율(마지막/이전평균): {range_expansion_ratio_6h:.2f}

위 정보를 바탕으로 진입 신호의 신뢰성을 분석해주세요.
특히 현재 {regime} 레짐에서 이 진입이 적절한지 판단해주세요.
"""

GUARDIAN_SYSTEM_PROMPT = """
당신은 가상자산 투자 리스크 관리 전문가인 'RiskGuardian'입니다.

[**중요**: Rule Engine과의 역할 분리]
Rule Engine이 이미 리스크 검증(일일 손실 한도, 동시 포지션 수, 쿨다운 등)을 통과한 거래만 당신에게 전달됩니다.
당신은 Rule Engine이 계량화하지 못하는 거시적/심리적 리스크만 판단하세요.

[당신이 판단해야 할 것]
1. 시장 변동성이 비정상적으로 높은지 (최근 캔들 기준)
2. 급격한 가격 변동이 패닉 셀링/FOMO 매수와 연관되는지
3. 투자자의 연속 손실 상태에서의 뇌동매매(Revenge Trading) 가능성

[판단 기준]
- SAFE: 특별한 거시적 위험 신호가 없으며, 시장이 정상 범위 내에서 움직이는 경우.
- WARNING: 시장 변동성이 비정상적이거나, 패닉/FOMO 징후가 명확한 경우.
"""


def get_analyst_prompt(indicators: dict) -> str:
    """
    지표 정보를 바탕으로 Analyst 프롬프트 생성
    """
    def _num(value, default=0.0):
        return default if value is None else value

    regime = indicators.get("regime", "UNKNOWN")
    return ANALYST_USER_PROMPT_TEMPLATE.format(
        regime=regime,
        regime_description=REGIME_DESCRIPTIONS.get(regime, ""),
        regime_guidance=ANALYST_REGIME_GUIDANCE.get(regime, ""),
        diff_pct=_num(indicators.get("regime_diff_pct"), 0.0),
        symbol=indicators.get("symbol", "UNKNOWN"),
        close=_num(indicators.get("close"), 0.0),
        ai_context_candles=int(_num(indicators.get("ai_context_candles"), 0)),
        pattern_direction=indicators.get("pattern_direction", "FLAT"),
        net_change_pct_6h=_num(indicators.get("net_change_pct_6h"), 0.0),
        bearish_streak_6h=int(_num(indicators.get("bearish_streak_6h"), 0)),
        bullish_streak_6h=int(_num(indicators.get("bullish_streak_6h"), 0)),
        last_body_to_range_ratio=_num(indicators.get("last_body_to_range_ratio"), 0.0),
        last_upper_wick_ratio=_num(indicators.get("last_upper_wick_ratio"), 0.0),
        last_lower_wick_ratio=_num(indicators.get("last_lower_wick_ratio"), 0.0),
        range_expansion_ratio_6h=_num(indicators.get("range_expansion_ratio_6h"), 1.0),
    )
