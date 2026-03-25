# 33. 전략 청산 파라미터 튜닝 (Stop Loss 축소 + TIME_LIMIT 조정) 작업 계획

**작성일**: 2026-03-25
**작성자**: Codex
**상태**: Approval Pending
**관련 계획 문서**: `docs/work-plans/30_strategy_feedback_automation_spec_first_plan.md`
**승인 정보**: 승인 대기

---

## 0. 트리거(Why started)
- 약 1개월 운영 데이터(35 SELL 거래) 분석 결과, R:R 비율 역전으로 지속적 손실 발생 확인
- 진입 조건(승률 65.7%)은 정상 동작 중이나, 청산 파라미터 설정 오류로 손실 구조 고착

## 1. 문제 요약

### 증상
- 전략(AdaptiveMeanReversion)이 1개월 운영 중 누적 손실 상태
- 거래당 기대값: **-0.22%** (총 -7.8% / 35거래)

### 실측 데이터 (2026-02-26 ~ 2026-03-25, 35 SELL)

| 청산 사유 | 건수 | 평균 손익 | 최소 | 최대 |
|---|---:|---:|---:|---:|
| RSI_OVERBOUGHT | 21 | **+1.28%** | +1.00% | +2.17% |
| STOP_LOSS | 9 | **-3.86%** | -4.33% | -3.09% |
| TIME_LIMIT | 3 | **-2.24%** | -3.13% | -1.39% |
| TAKE_PROFIT | 2 | **+3.39%** | +3.05% | +3.73% |

### 영향 범위
- 전략 손익 직접 영향
- 현재 운영 레짐: SIDEWAYS 위주 (35거래 전부 SIDEWAYS 진입)

### 재현 조건
- SIDEWAYS 레짐에서 RSI 과매도 반등 진입 후 Mean Reversion 미발생 시 STOP_LOSS 도달

## 2. 원인 분석

### Root cause: SIDEWAYS stop_loss_pct 과대 설정 (0.04 = 4%)
- 현재 구조: RSI_OVERBOUGHT 청산 평균 +1.28% vs STOP_LOSS 평균 -3.86%
- **R:R = 1.28 / 3.86 = 0.33** (손익비 역전 — 1.0 이상이어야 수익 가능)
- 승률이 65.7%임에도 손실인 이유: 손실 1건이 이익 3건을 지운다

### 보조 원인: TIME_LIMIT 48시간으로 손실 포지션 장기 보유
- 48시간 보유 후 평균 -2.24% 청산 → 오래 들고 있어도 회복 안 됨

### 진입 조건은 문제 없음
- 승률 65.7% (23/35) — RSI_OVERBOUGHT + TAKE_PROFIT 정상 도달

## 3. 대응 전략

### 근본 해결 (주요 변경)

**변경 1 — SIDEWAYS stop_loss_pct: 0.04 → 0.02**
- 현재 -4% 손절이 +1.28% 이익 3건을 한 번에 지우는 구조 해소
- 기대 효과: 거래당 기대값 -0.22% → +0.26% (흑자 전환 시뮬레이션)
  ```
  (21 × +1.28%) + (9 × -2.0%) + (3 × -2.24%) + (2 × +3.39%) / 35 = +0.26%
  ```
- 리스크: SIDEWAYS 변동성에서 -2% 이내 일시 하락 후 반등 시 불필요한 손절 증가 가능
  → 완화: 진입 조건(BB touch + RSI 반등 확인)이 충분히 타이트해 진입 정확도 유지 중

**변경 2 — SIDEWAYS time_limit_hours: 48 → 24**
- 48시간 보유 후 평균 -2.24% — 오래 들고 있어도 회복 없음
- 24시간으로 단축해 손실 포지션 빠르게 정리

**변경 3 — BEAR stop_loss_pct: 0.05 → 0.03 (예방적 조정)**
- BEAR 레짐은 현재 거래 없으나 -5% 손절은 Mean Reversion 전략에 과대
- SIDEWAYS 동일 원칙 적용
- BEAR time_limit_hours: 24 → 12 (하락장에서 장기 보유 위험)

### 안전장치
- 변경은 `src/config/strategy.py` 상수 수정만으로 즉시 롤백 가능
- 스키마 변경 없음
- 2주 후 동일 분석 쿼리로 before/after 비교

### 보류 항목
- Analyst/Guardian 프롬프트 튜닝: 현재 진입 승률 65.7%로 양호, CONFIRM 이후 거래 결과 추가 분석 후 재검토
- RSI_OVERBOUGHT 임계값 조정: 현재 +1.28% 안정적으로 수익 중, 건드리지 않음

## 4. 아키텍처 선택 / 대안 / 트레이드오프

### 최종 선택: stop_loss_pct 직접 축소

**고려 대안:**

1. **stop_loss_pct 축소 (채택)**
   - 장점: 가장 직접적, 즉시 효과, 롤백 단순
   - 단점: 변동성 큰 구간에서 불필요한 손절 증가 가능
   - 완화: BB touch + RSI 반등이 진입 조건이므로 변동성 급등 구간은 이미 필터됨

2. **RSI_OVERBOUGHT 임계값 상향 (예: 70 → 80)**
   - 장점: 이익 구간 확대
   - 단점: 현재 +1.28% 이익이 안정적인데 변경 시 오히려 역전 위험, 데이터 부족
   - 보류

3. **take_profit_pct 하향 (예: 3% → 1.5%)**
   - 장점: TAKE_PROFIT 달성 빈도 증가
   - 단점: 이미 RSI_OVERBOUGHT가 +1.28%에서 먼저 청산 중, 효과 미미
   - 보류

4. **트레일링 스탑 파라미터 조정**
   - 현재 trailing_stop_activation_pct 0.01(1%) 이후 trailing_stop_pct 0.025(2.5%) 작동
   - STOP_LOSS 발동 시 trailing stop이 이미 선행되었을 가능성 있으나, 데이터상 STOP_LOSS avg -3.86%는 trailing 없이 직접 -4%에 도달한 것으로 추정
   - 이번 범위 밖, 후속 관찰 대상

## 5. 구현/수정 내용

### 변경 파일
- `src/config/strategy.py`

### 변경 상세

```python
# SIDEWAYS exit (현재 → 변경)
"exit": {
    "take_profit_pct": 0.03,          # 유지
    "stop_loss_pct": 0.04,            # → 0.02
    "trailing_stop_pct": 0.025,       # 유지
    "trailing_stop_activation_pct": 0.01,  # 유지
    "rsi_overbought": 70,             # 유지
    "rsi_exit_min_profit_pct": 0.01,  # 유지
    "time_limit_hours": 48            # → 24
}

# BEAR exit (현재 → 변경)
"exit": {
    "take_profit_pct": 0.03,          # 유지
    "stop_loss_pct": 0.05,            # → 0.03
    "trailing_stop_pct": 0.02,        # 유지
    "trailing_stop_activation_pct": 0.01,  # 유지
    "rsi_overbought": 70,             # 유지
    "rsi_exit_min_profit_pct": 0.005, # 유지
    "time_limit_hours": 24            # → 12
}
```

### DB 변경
- 없음

## 6. 검증 기준

### 코드 검증
- `PYTHONPATH=. .venv/bin/python -m pytest tests/` 기존 테스트 전체 통과

### 운영 검증 (2주 후 동일 쿼리 재실행)
```sql
SELECT
  exit_reason, COUNT(*) AS count,
  ROUND(AVG(pnl_pct), 2) AS avg_pnl_pct,
  ROUND(MIN(pnl_pct), 2) AS min_pnl_pct,
  ROUND(MAX(pnl_pct), 2) AS max_pnl_pct
FROM (
  SELECT
    (signal_info->>'exit_reason') AS exit_reason,
    ((signal_info->>'close')::numeric - (signal_info->>'entry_avg_price')::numeric)
    / (signal_info->>'entry_avg_price')::numeric * 100 AS pnl_pct
  FROM trading_history
  WHERE side='SELL' AND signal_info->>'entry_avg_price' IS NOT NULL
    AND created_at >= NOW() - INTERVAL '14 days'
) sub
GROUP BY exit_reason ORDER BY count DESC;
```

### 성공 기준
- STOP_LOSS 평균 손실: -3.86% → -2.5% 이내
- 거래당 기대값: -0.22% → 0% 이상
- STOP_LOSS 건수 비율: 26% 이하 유지 (불필요한 조기 손절 없음 확인)

## 7. 롤백
- `src/config/strategy.py`의 수치를 원복 후 bot 재기동
- 스키마/데이터 변경 없으므로 즉시 롤백 가능

## 8. 문서 반영
- 구현 완료 후 `docs/work-result/33_strategy_exit_parameter_tuning_result.md` 작성
- 체크리스트 상태 갱신

## 9. 계획 변경 이력
- 2026-03-25: 최초 작성, Approval Pending
