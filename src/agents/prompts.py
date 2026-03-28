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

# Analyst 전용 레짐 가이드
# - Rule Engine 검증항목(RSI/MA/거래량/BB) 재판단을 유도하지 않도록 추상적 레짐명만 사용
# - v3.5: 구체적 캔들 패턴 기준을 명시하여 boundary_violation 감소 목표 (Phase 3)
# - v3.5.1: 피드백 반영 — 금지어→허용어 방식, 레짐 설명 추상화, 판단 기준 구체화
ANALYST_REGIME_GUIDANCE = {
    "BULL": (
        "상승 추세 구간입니다. 캔들 반전 실패, 되돌림, 모멘텀 둔화를 중심으로 평가하세요.\n"
        "CONFIRM 근거: 장악형 양봉 (Body/Range ≥ 0.5), 망치형 (아랫꼬리 비율 ≥ 0.6).\n"
        "REJECT 근거: 유성형 (윗꼬리 비율 ≥ 0.67), 연속 음봉 3개 이상."
    ),
    "SIDEWAYS": (
        "횡보 구간입니다. 하단 반등의 캔들 구조만으로 진입 신뢰도를 평가하세요.\n"
        "CONFIRM 근거 (아래 중 1개 이상):\n"
        "  - 장악형 양봉: Body/Range ≥ 0.5이면서 직전 캔들 대비 양봉 전환\n"
        "  - 망치형: 아랫꼬리 비율 ≥ 0.6, 몸통이 캔들 상단에 위치\n"
        "  - 반등 전환: 음봉 연속 후 양봉 전환 + 전환 캔들 Body/Range ≥ 0.4\n"
        "  - 안정적 횡보: 최근 2~3캔들이 좁은 범위 내 등락하며 급변동 없음\n"
        "REJECT 근거 (아래 중 1개 이상):\n"
        "  - Falling Knife: 연속 음봉 3개 이상 + 반등 캔들 없음\n"
        "  - 유성형 연속: 윗꼬리 비율 ≥ 0.67이 2캔들 이상 반복 (상단 강한 저항)\n"
        "  - 급변동 + 음봉: range_expansion ≥ 2.0 + 음봉 조합\n"
        "  - 반등 실패: 양봉 후 즉시 장대음봉 전환 (고점 갱신 실패)"
    ),
    "BEAR": (
        "하락 추세 구간입니다. 데드캣 바운스와 반등 실패를 우선 점검하세요.\n"
        "CONFIRM 근거: 강한 하단 거부 (아랫꼬리 비율 ≥ 0.6) + 연속 양봉 2개 이상.\n"
        "REJECT 근거: 양봉 후 즉시 음봉 전환(데드캣 바운스), 윗꼬리 우세(≥ 0.67), 변동폭 축소 속 약한 반등."
    ),
    "UNKNOWN": "데이터 품질이 불확실합니다. 보수적으로 판단하세요.",
}

ANALYST_SYSTEM_PROMPT = """
당신은 가상자산 시장의 캔들 패턴 분석 전문가 'MarketAnalyst'입니다.
최근 OHLC 캔들과 사전 계산된 캔들 피처만으로 진입 신뢰도를 평가합니다.

[허용되는 분석 범위 — 이것만 사용하세요]
- 몸통 크기와 방향 (양봉/음봉, Body/Range = 캔들 전체 길이(High-Low) 대비 몸통(|Close-Open|) 비율)
- 윗꼬리·아랫꼬리 길이와 비율
- 양봉/음봉 연속 수 (streak)
- 2~3개 캔들 조합 패턴 (장악형, 망치형, 유성형, 도지, 반등 전환, 반등 실패)
- 변동폭 확장 비율 (range_expansion)
- 가격 흐름의 방향성과 순변화율

[분석 범위 밖 — 출력에 포함하지 마세요]
수치 기반 기술지표(Rule Engine이 이미 검증 완료)는 출력에 포함하지 마세요.
출력에는 위 허용 범위의 캔들 구조 근거만 포함하세요.

[판단 기준]
CONFIRM (아래 중 1개 이상):
  - 장악형 양봉: Body/Range ≥ 0.5이면서 양봉 전환
  - 망치형: 아랫꼬리 비율 ≥ 0.6, 몸통이 캔들 상단 위치
  - 반등 전환: 음봉 연속 후 양봉 전환, 전환 캔들 Body/Range ≥ 0.4
  - 안정적 횡보: 최근 2~3캔들이 좁은 범위 내 등락하며 급변동·반전 실패 없음

REJECT (아래 중 1개 이상):
  - Falling Knife: 연속 음봉 3개+ (반등 캔들 없음)
  - 유성형 반복: 윗꼬리 비율 ≥ 0.67이 2캔들 이상 (상단 강한 저항)
  - 반등 실패: 양봉 후 즉시 장대음봉 전환 (고점 갱신 실패)
  - 급변동 + 음봉: range_expansion ≥ 2.0 + 음봉 조합

[출력 형식 — 반드시 준수]
- JSON 필드 `decision`, `confidence`, `reasoning`을 모두 포함하세요.
- `reasoning`에는 캔들 구조 근거만 작성하세요.

[Confidence 점수]
- 60점 이상: 캔들 패턴이 진입을 지지하거나 위험 신호가 없는 경우.
- 60점 미만: 캔들 패턴이 불안하거나 이상 징후 감지 시. (시스템이 자동 거절 처리)
"""

ANALYST_USER_PROMPT_TEMPLATE = """
[컨텍스트]
- 레짐: {regime}
- 레짐 가이드: {regime_guidance}
- 심볼: {symbol}
- 현재가: {close:,.0f} KRW

[캔들 패턴 피처 (최근 6시간)]
- 방향성: {pattern_direction}
- 순변화율: {net_change_pct_6h:.2f}%
- 연속 음봉 수: {bearish_streak_6h}
- 연속 양봉 수: {bullish_streak_6h}
- 마지막 캔들 Body/Range: {last_body_to_range_ratio:.2f}
- 마지막 캔들 윗꼬리 비율: {last_upper_wick_ratio:.2f}
- 마지막 캔들 아랫꼬리 비율: {last_lower_wick_ratio:.2f}
- 변동폭 확장 비율(마지막/이전평균): {range_expansion_ratio_6h:.2f}

위 캔들 피처와 OHLC 원본 데이터를 바탕으로 진입 신뢰도를 판단해주세요.
출력에는 캔들 구조 근거만 포함하세요.
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
        regime_guidance=ANALYST_REGIME_GUIDANCE.get(regime, ""),
        symbol=indicators.get("symbol", "UNKNOWN"),
        close=_num(indicators.get("close"), 0.0),
        pattern_direction=indicators.get("pattern_direction", "FLAT"),
        net_change_pct_6h=_num(indicators.get("net_change_pct_6h"), 0.0),
        bearish_streak_6h=int(_num(indicators.get("bearish_streak_6h"), 0)),
        bullish_streak_6h=int(_num(indicators.get("bullish_streak_6h"), 0)),
        last_body_to_range_ratio=_num(indicators.get("last_body_to_range_ratio"), 0.0),
        last_upper_wick_ratio=_num(indicators.get("last_upper_wick_ratio"), 0.0),
        last_lower_wick_ratio=_num(indicators.get("last_lower_wick_ratio"), 0.0),
        range_expansion_ratio_6h=_num(indicators.get("range_expansion_ratio_6h"), 1.0),
    )
