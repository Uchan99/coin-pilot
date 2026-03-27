# 34. AdaptiveMeanReversion 5단계 전략 개선 — Phase 1~2 구현 결과

작성일: 2026-03-28
작성자: Claude (assistant)
관련 계획서: docs/work-plans/34_adaptive_mean_reversion_4stage_improvement_plan.md
상태: Partial
완료 범위: Phase 1~2
선반영/추가 구현: 없음
관련 트러블슈팅: docs/troubleshooting/strategy-retrospectives/34_rr_inversion_and_correlated_loss_clustering.md

---

## 1. 개요
- 구현 범위 요약: Phase 1(포트폴리오 동시 포지션 제한 + 포지션 사이즈 상향) + Phase 2(BB_MIDLINE_EXIT 익절 로직 + RSI 우선순위 변경)
- 목표: R:R 역전(avg win +1.28% vs avg loss -3.86%) 구조 개선 — 상관 손실 집중 완화 + 수익 확보 빈도 증가
- 이번 구현이 해결한 문제: 동시 다심볼 STOP_LOSS 클러스터링 + SIDEWAYS 수익 구간 TIME_LIMIT 전환 손실
- 해결한 문제의 구체 정의:
  - 증상: 38건 거래 중 STOP_LOSS 9건의 7건이 2~3심볼 동시 발생 (2/27, 2/28, 3/22), 합계 -27.94%
  - 영향: 전체 누적 -18,700원 손실의 대부분이 3개 클러스터 이벤트에서 발생
  - 재현 조건: 시장 전체 급락 시 MAX_CONCURRENT_POSITIONS=5로 3심볼 이상 동시 보유 상태
- 기존 방식(Before) 기준선:
  - MAX_CONCURRENT_POSITIONS: 5, max_position_size: 20%
  - BB_MIDLINE_EXIT: 없음 (TIME_LIMIT 3건 avg -2.24%)
  - Exit 우선순위: SL → TS → TP → RSI_OB → TIME_LIMIT

---

## 2. 구현 내용

### 2.1 Phase 1: 동시 포지션 제한 축소 (5→2) + 포지션 사이즈 상향 (20%→30%)
- 파일/모듈: `src/config/strategy.py`, `config/strategy_v3.yaml`, `config/strategy_v3_tuned.yaml`
- 변경 내용:
  - `MAX_CONCURRENT_POSITIONS`: 5 → **2** (YAML override 포함)
  - `max_position_size`: 0.20 → **0.30** (자본 활용률 40% → 60% 개선)
- 효과/의미:
  - 2/28 사례(3건 동시 SL, -12.32%) → 2개 제한 시 최소 1건 차단, -8.03%로 축소
  - worst case: 동시 2건 SL(-4% × 2 × 30% = -2.4% 계좌 손실) — 기존(-4% × 3 × 20% = -2.4%)과 계좌 레벨 동일하나 3심볼 동시 이벤트 구조적 차단

### 2.2 Phase 2: BB_MIDLINE_EXIT 1.0% 가드 + RSI_OVERBOUGHT 우선순위 변경
- 파일/모듈: `src/engine/strategy.py`, `scripts/backtest_v3.py`
- 변경 내용:
  - SIDEWAYS 전용 exit 조건 추가: `close >= bb_mid` + `pnl_ratio >= 0.01`
  - Exit 우선순위 변경: SL → TS → TP → **RSI_OVERBOUGHT** → **BB_MIDLINE_EXIT** → TIME_LIMIT
  - 가드 수치 백테스트 비교 후 1.0% 최적 확인
- 효과/의미:
  - TIME_LIMIT 비율 감소 (OFF 16건 → 1.0% 가드 7건)
  - avg_win +1.29% 보존 (0.3% 가드에서는 +0.63%로 급감했음)
  - RSI_OVERBOUGHT가 BB보다 우선 → RSI 과매수 시 추가 상승 기회 보존

---

## 3. 변경 파일 목록

### 3.1 수정
1) `src/config/strategy.py` — MAX_CONCURRENT_POSITIONS: 2, 주석 업데이트
2) `config/strategy_v3.yaml` — max_concurrent_positions: 2, max_position_size: 0.30
3) `config/strategy_v3_tuned.yaml` — 동일 변경
4) `src/engine/strategy.py` — BB_MIDLINE_EXIT 로직 추가, RSI_OVERBOUGHT 우선순위 변경
5) `scripts/backtest_v3.py` — bb_min_profit/rsi_ob_override 파라미터, --compare-bb-guards/--compare-rsi CLI
6) `docs/work-plans/34_adaptive_mean_reversion_4stage_improvement_plan.md` — 변경 이력 반영

### 3.2 신규
- 없음

---

## 4. DB/스키마 변경
- 없음 (전략 파라미터 변경만)

---

## 5. 검증 결과

### 5.1 코드/정적 검증
- 실행 명령: `docker exec coinpilot-bot grep max_position_size /app/config/strategy_v3.yaml`
- 결과: `max_position_size: 0.30` 확인

### 5.2 백테스트 검증 (Phase 2)
- 실행 명령: `docker exec coinpilot-bot python scripts/backtest_v3.py --compare-bb-guards`
- 결과: BB 가드 수치 비교

| 가드 | SW 건수 | SW 승률 | SW PnL | avg_win | BB발동 | RSI_OB | TIME_LIMIT | SL |
|------|---------|---------|--------|---------|--------|--------|-----------|-----|
| OFF | 49 | 40.8% | -58.48% | +2.38% | 0 | 3 | 16 | 18 |
| 0.3% | 59 | 64.4% | -57.80% | +0.63% | 38 | 0 | 3 | 15 |
| **1.0%** | **55** | **54.5%** | **-52.83%** | **+1.29%** | **29** | **0** | **7** | **16** |
| 2.0% | 49 | 40.8% | -66.30% | +1.92% | 15 | 1 | 12 | 18 |

- RSI 임계값 비교: `docker exec coinpilot-bot python scripts/backtest_v3.py --compare-rsi`
- 결과: RSI 55~75 범위에서 SIDEWAYS 성과 동일 → 현행 RSI 70 유지

### 5.3 런타임/운영 반영 확인
- OCI 배포 완료: `docker restart coinpilot-bot` (2026-03-28)
- YAML docker cp 적용 확인: `max_position_size: 0.30`, `max_concurrent_positions: 2`
- 모니터링 대기: 2026-03-29까지 실거래 관찰 후 Phase 3 진행 예정

### 5.4 정량 개선 증빙
- 정량 측정 불가 시(예외):
  - 불가 사유: Phase 1~2 배포 직후로 실거래 데이터 미축적
  - 대체 지표: 백테스트 비교 (위 5.2 참조)
  - 추후 측정 계획: 2주 후 실운영 SQL로 아래 검증 예정

```sql
-- BB_MIDLINE_EXIT 발동 건수 및 평균 PnL
SELECT exit_reason, COUNT(*), AVG(pnl_pct)
FROM trades
WHERE regime = 'SIDEWAYS' AND closed_at >= '2026-03-28'
GROUP BY 1;

-- 동시 3심볼 SL 이벤트 재발 여부
SELECT DATE(closed_at), COUNT(*)
FROM trades WHERE exit_reason = 'STOP_LOSS'
GROUP BY 1 HAVING COUNT(*) >= 3;
```

---

## 6. 배포/운영 확인 체크리스트
1) `config/strategy_v3.yaml` docker cp 완료 ✅
2) `config/strategy_v3_tuned.yaml` docker cp 완료 ✅
3) `docker restart coinpilot-bot` 완료 ✅
4) `max_position_size: 0.30` 적용 확인 ✅
5) 모니터링 체크 항목 (2026-03-29):
   - [ ] BB_MIDLINE_EXIT 발동 건 확인
   - [ ] 30% 포지션 주문 정상 체결 확인
   - [ ] 동시 포지션 2개 제한 정상 작동 확인
   - [ ] RSI_OVERBOUGHT가 BB_MIDLINE_EXIT보다 우선 발동 확인

---

## 7. 설계/아키텍처 결정 리뷰
- 최종 선택한 구조: 5단계 순차 개선 (리스크→exit→AI 프롬프트→Guardian→진입 조건)
- 고려했던 대안:
  1) 전략 전환 (트렌드팔로잉/BB스퀴즈) → 기각: 1개월 데이터로 판단 이르다
  2) 파라미터 추가 튜닝 → 기각: 33번에서 3가지 시도 모두 개선 미미
  3) volume_surge 진입 필터 → 폐기: 진입 시 vol_ratio 0.81x, 차단 효과 없음
- 대안 대비 실제 이점:
  1) 각 단계 데이터 근거 명확 → 효과 귀인 가능
  2) Phase 1(동시 제한)은 코드 1줄로 가장 큰 구조적 리스크 제거
  3) Phase 2(BB_MIDLINE_EXIT)는 백테스트로 최적 가드 수치(1.0%) 검증 완료
- 트레이드오프:
  1) 동시 2개 제한 → 상승장에서 3번째 심볼 기회 손실 — 완화: 2주 후 기회비용 SQL 검증
  2) BB_MIDLINE_EXIT → avg_win 감소 (+2.38%→+1.29%) — 완화: TIME_LIMIT 감소로 상쇄

---

## 8. 한국어 주석 반영 결과
- 주석을 추가/강화한 주요 지점:
  1) `src/engine/strategy.py:313-322` — BB_MIDLINE_EXIT 로직의 의도/전략/가드 수치 선택 근거
  2) `src/engine/strategy.py:312-314` — RSI_OVERBOUGHT 우선순위 논리 (RSI 과매수 → 추가 상승 가능)
  3) `config/strategy_v3.yaml:145` — 30% 상향 근거 (동시 2개 제한 연계)
- 핵심 요소: 의도(why), 백테스트 비교 결과, 대안C 선택 이유

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분: Phase 1(동시 제한), Phase 2(BB_MIDLINE_EXIT) 방향 일치
- 변경/추가된 부분:
  - BB 가드: 0.3% → 1.0% (백테스트 결과 0.3%에서 avg_win 급감 확인)
  - RSI 우선순위 변경(대안C) 추가 (계획에 없던 개선)
  - 포지션 사이즈 20%→30% 상향 (동시 제한과 연계한 자본 활용률 개선)
  - MAX_CONCURRENT_POSITIONS 실제값이 3이 아닌 5(YAML override)였음을 발견하여 수정
- 비효율적/오류: 초기 계획에서 Python 기본값(3)을 실제 운영값으로 오인 — YAML override 확인 부족

---

## 10. 결론 및 다음 단계
- 현재 상태: Phase 1~2 OCI 배포 완료, 모니터링 대기 중 (2026-03-29까지)
- 후속 작업:
  1) 2026-03-29: 모니터링 결과 확인 후 Phase 3(Analyst 프롬프트) 진행
  2) Phase 4: Guardian OHLC 컨텍스트 전달
  3) Phase 5: Rule Engine 진입 조건 분석 (SQL 기반)
  4) 2주 후: 실운영 데이터 기반 정량 검증 (BB_MIDLINE_EXIT 효과, 동시 제한 기회비용)

---

## 12. References
- Plan: docs/work-plans/34_adaptive_mean_reversion_4stage_improvement_plan.md
- 실거래 데이터: docs/operating_data.md
- 전략 전회고: docs/troubleshooting/strategy-retrospectives/34_rr_inversion_and_correlated_loss_clustering.md
- 이전 튜닝 작업: docs/work-plans/33_strategy_exit_parameter_tuning_plan.md
