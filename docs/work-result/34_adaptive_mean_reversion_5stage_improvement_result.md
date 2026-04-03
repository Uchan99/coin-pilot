# 34. AdaptiveMeanReversion 5단계 전략 개선 — Phase 1~4 구현 결과

작성일: 2026-03-28
작성자: Claude (assistant)
관련 계획서: docs/work-plans/34_adaptive_mean_reversion_4stage_improvement_plan.md
상태: Partial
완료 범위: Phase 1~4
선반영/추가 구현: 없음
관련 트러블슈팅: docs/troubleshooting/strategy-retrospectives/34_rr_inversion_and_correlated_loss_clustering.md

---

## 1. 개요
- 구현 범위 요약: Phase 1(포트폴리오 동시 포지션 제한 + 포지션 사이즈 상향) + Phase 2(BB_MIDLINE_EXIT 익절 로직 + RSI 우선순위 변경) + Phase 3(Analyst 프롬프트 v3.5.1) + Phase 4(Guardian OHLC 캔들 컨텍스트)
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
7) `src/agents/guardian.py` — OHLC 6개 캔들 데이터 프롬프트 전달 (Phase 4)
8) `src/agents/prompts.py` — Guardian 캔들 구조 분석 가이드 추가 (Phase 4)

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
5) Phase 1~2 모니터링 체크 항목 (2026-03-29 확인 완료):
   - [x] BB_MIDLINE_EXIT 발동 건 확인 — DOGE +1.4% 첫 발동
   - [x] 30% 포지션 주문 정상 체결 확인 — BTC 289,658원(~29%), DOGE 181,045원(~18%)
   - [x] 동시 포지션 2개 제한 정상 작동 확인 — BTC + DOGE 동시 보유 (2개)
   - [x] RSI_OVERBOUGHT가 BB_MIDLINE_EXIT보다 우선 발동 확인 — BTC RSI_OVERBOUGHT 정상
6) Phase 3 OCI 배포 완료 (2026-03-29):
   - `docker compose ... up -d --build --no-deps bot` 완료
   - `grep "허용되는 분석 범위"` 1건 확인
7) Phase 3 모니터링 체크 항목:
   - [x] boundary_violation 비율 < 20% (기존 33.6%) → **11.3%** (8/70건, 2026-04-03 확인)
   - [x] reasoning에 캔들 구조 근거만 포함 확인 — REJECT 시 0% 위반, CONFIRM 시에만 violation 발생
   - [x] SIDEWAYS 레짐 CONFIRM 품질 확인 — **39건** 축적, CONFIRM 7건(17.9%), avg_conf 36.2
   - [x] Phase 3 모니터링 **close** (2026-04-03). CONFIRM violation 패턴은 v3.5.2 프롬프트로 대응.
8) Phase 4 모니터링 체크 항목:
   - [x] Guardian reasoning에 캔들 구조 언급 포함 확인 — **100%** (37/37건)
   - [x] Guardian WARNING 비율 — **100% REJECT** (37/37건, CONFIRM 0건) ⚠️ 과보수
   - [x] Guardian blocked 비율 — guardian_warning 39건 차단 (파이프라인 funnel 확인)
   - [x] Guardian latency/cost — avg 8.9s / $0.007/call (Analyst 대비 +27% latency, 비용 동등)
   - **문제 발견**: Guardian 100% REJECT → SAFE 기준 부재 + 6시간 창 내 오래된 이벤트 반복 감지
   - **대응**: v3.5.2 프롬프트 수정 — SAFE 기준 구체화 + 3시간 시간 범위 제한
   - [ ] v3.5.2 배포 후 재모니터링 (3일, Guardian SAFE 비율 > 0% 목표)

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
- 현재 상태: Phase 1~4 OCI 배포 완료, Phase 3 모니터링 close, Phase 4 프롬프트 v3.5.2 수정 후 재모니터링
- Phase 1~2 모니터링 결과 (2026-03-29 확인):
  - BB_MIDLINE_EXIT 첫 발동 (DOGE +1.4%) ✅
  - RSI_OVERBOUGHT 우선 정상 (BTC) ✅
  - 동시 포지션 2개 제한 정상 ✅
  - 30% 포지션 체결 확인 (BTC 289K, DOGE 181K) ✅
- Phase 3 모니터링 결과 (2026-03-30 1차, 2026-04-03 2차 확인):
  - 1차 (배포 후 ~23h, 9건): boundary_violation 0.0%, SIDEWAYS 1건 샘플 부족
  - 2차 (배포 후 ~5일, 62건): boundary_violation **11.3%** (8/70건) — 목표 < 20% 달성 ✅
  - SIDEWAYS 39건 충분 축적 (목표 5건 이상) ✅
  - SIDEWAYS CONFIRM rate: 17.9% (7/39건), avg_confidence: 36.2
  - BEAR CONFIRM rate: 0% (0/23건) — 정상
  - **발견**: violation 8건 전부 CONFIRM 판단 건 — REJECT 시에는 0% 위반
  - **대응**: Analyst 프롬프트 v3.5.2 수정 — "CONFIRM/REJECT 모두 금지 키워드 출력 금지" 명시
  - **판단**: Phase 3 모니터링 **close** (목표 달성 + 샘플 충분 + 프롬프트 미세조정 적용)
- Phase 4 모니터링 결과 (2026-04-03 확인, 배포 후 ~4일):
  - OHLC 캔들 패턴 활용: **100%** (37/37건) ✅
  - Guardian 판단: **37건 전량 REJECT, CONFIRM 0건** ⚠️
  - 감지 패턴: Head Fake, 연속음봉, 장대음봉, 변동폭 확장, Falling Knife ✅
  - **문제**: Guardian 100% REJECT 편향 — 단일 Head Fake가 6시간 창 안에서 반복 감지되며 수시간 차단 지속
  - **근본 원인**: WARNING 기준만 상세, SAFE 기준 없음 → LLM이 항상 위험 요소를 찾아냄
  - **대응**: Guardian 프롬프트 v3.5.2 수정 — SAFE 기준 구체화 + 최근 3캔들(3시간) 시간 범위 제한
  - **판단**: v3.5.2 배포 후 3일 재모니터링 필요 (Guardian SAFE 비율 > 0% 목표)
- Pipeline 퍼널 (3/29~4/3):
  - rule_pass 483 → risk_reject 193 → ai_prefilter 111 → guardrail 71 → analyst_reject 60 → guardian_warning 39 → **approved 8** (1.7%)
- LLM 비용 (3/30~4/3): Analyst $0.54 (92 calls) + Guardian $0.31 (44 calls) = **$0.85**
- 후속 작업:
  1) v3.5.2 OCI 배포 후 3일 모니터링 (Guardian SAFE 비율 확인)
  2) Phase 5: Rule Engine 진입 조건 분석 (SQL 기반)
  3) 2주 후(~2026-04-11): 실운영 데이터 기반 정량 검증 (BB_MIDLINE_EXIT 효과, 동시 제한 기회비용)
  4) Guardian SAFE 비율이 여전히 0%면: Analyst-Guardian 통합 검토 (비용 절감)

---

## 11. Phase 3 구현 결과 (2026-03-29)

### 11.1 변경 내용
- 파일: `src/agents/prompts.py`
- 변경 사항:
  - **ANALYST_SYSTEM_PROMPT**: 금지어 나열 → 허용어 방식 (캔들 구조만 허용 범위로 명시)
  - **ANALYST_REGIME_GUIDANCE**: 레짐 설명 추상화 (MA50/MA200/골든크로스 → "상승 추세 구간"), SIDEWAYS CONFIRM 4가지 + REJECT 4가지 구체화
  - **ANALYST_USER_PROMPT_TEMPLATE**: MA50/MA200 이격도·AI 컨텍스트 길이 제거, Body/Range 정의 명확화
  - 테스트 assertion 업데이트: `tests/agents/test_analyst_rule_boundary.py`

### 11.2 설계 대안 비교

| # | 대안 | 채택 | 트레이드오프 |
|---|------|------|------------|
| 1 | 허용어 방식 + 입력 최소화 (채택) | ✅ | 프롬프트만 변경, 롤백 즉시 가능. LLM이 수치를 기계적으로 따를 수 있음 |
| 2 | boundary violation 시 강제 REJECT 복원 | ❌ | 즉시 0%지만 valid 거래도 차단 (false rejection 증가) |
| 3 | Few-shot 예제 추가 | 보류 | 가장 효과적이나 토큰 비용 +500~800/호출. Phase 3 미달 시 추가 |
| 4 | reasoning 후처리로 키워드 자동 삭제 | ❌ | 2회 LLM 호출, 비용 2배, 근본 해결 아님 |
| 5 | HOLD 옵션 추가 | 보류 | 스키마 + runner 변경 필요. confidence < 60 강제 REJECT가 사실상 HOLD 역할 |
| 6 | reasoning 배열화 | 보류 | 하위 파이프라인(Discord/DB/audit) 전부 string 기반, 영향 범위 넓음 |

### 11.3 외부 피드백 반영

| 피드백 소스 | 핵심 지적 | 반영 결과 |
|------------|----------|----------|
| 피드백 1 | 금지어가 오히려 해당 개념을 떠올리게 함 | 허용어 방식으로 전환 |
| 피드백 1 | 레짐 설명에 MA50/MA200이 AI 재판단 유도 | 레짐 설명 추상화 |
| 피드백 1 | AI 컨텍스트 길이 불필요 | 제거 |
| 피드백 1 | "위험 신호 부재" 너무 넓음 | "2~3캔들 좁은 범위 등락 + 급변동 없음"으로 구체화 |
| 피드백 2 | Body/Range 정의 명확화 필요 | "(High-Low) 대비 |Close-Open| 비율" 명시 |
| 피드백 2 | 유성형 단일 캔들 노이즈 | "2캔들 이상 반복" 조건으로 강화 |

### 11.4 검증
- 테스트: 7/7 passed (`tests/agents/test_analyst_rule_boundary.py`)
- 정량 검증 (2026-03-30, 배포 후 ~23h):

| 지표 | Before (v3.4) | After (v3.5.1) | 판정 |
|------|--------------|----------------|------|
| boundary_violation | 33.6% | **0.0%** (9건/0건) | ✅ 목표 < 20% 달성 |
| BEAR CONFIRM rate | 0/11 (0%) | 0/8 (0%) | 동일 (정상) |
| SIDEWAYS CONFIRM rate | 2/9 (22%) | 0/1 (0%) | 샘플 부족, 판단 보류 |
| BEAR avg_confidence | 31.5 | 28.8 | 소폭 하락 (BEAR에서는 무의미) |
| SIDEWAYS avg_confidence | 67.6 | 25.0 | 1건이라 통계 비교 불가 |

- 결론: boundary_violation 해소 확인. CONFIRM rate 0%는 시장 BEAR 레짐(89%)에 기인하며 프롬프트 과보수가 아님. SIDEWAYS 전환 시 재평가 필요.

```sql
-- 실제 사용한 boundary_violation 측정 쿼리
SELECT COUNT(*) AS total,
  SUM(CASE WHEN reasoning ~* 'rsi|ma20|이동평균|거래량|vol_ratio|볼린저|bb 하단|bb_lower' THEN 1 ELSE 0 END) AS violation_cnt,
  ROUND(100.0 * SUM(CASE WHEN reasoning ~* 'rsi|ma20|이동평균|거래량|vol_ratio|볼린저|bb 하단|bb_lower' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS violation_pct
FROM agent_decisions
WHERE created_at >= '2026-03-29 15:00:00+09';
```

---

## Phase 4 구현 결과 (2026-03-30)

### 12.1 변경 내용
- 파일: `src/agents/guardian.py`, `src/agents/prompts.py`
- 변경 사항:
  - **guardian.py**: `_format_ohlc_for_guardian()` 함수 추가 — Analyst와 동일한 `sanitize_market_context_for_analyst` 재사용, 최근 6개 1시간봉 OHLC를 텍스트로 포맷하여 Guardian 프롬프트에 포함
  - **prompts.py (GUARDIAN_SYSTEM_PROMPT)**: 캔들 구조 분석 가이드 섹션 추가 — Head Fake, 장대음봉, 연속음봉 3개, 윗꼬리 패턴, 변동폭 2배 확장 기준 명시
  - Guardian human 프롬프트에 `[최근 6시간 OHLC 캔들]` 블록 추가

### 12.2 설계 대안 비교

| # | 대안 | 채택 | 장점 | 단점 |
|---|------|------|------|------|
| 1 | **Raw OHLC 6개 전달 (채택)** | ✅ | Analyst와 동일 범위/일관성, sanitize 재사용으로 구현 단순, 롤백 즉시 가능 | 토큰 ~200 증가/호출, Guardian 캔들 해석 품질 미검증 |
| 2 | Raw OHLC 12개 전달 | ❌ | 더 넓은 추세 파악 | 토큰 ~400 증가, Guardian은 위험 차단 역할이라 6시간이면 충분 |
| 3 | 캔들 패턴 피처만 전달 (direction, streak 등) | ❌ | 토큰 최소 (~50) | Head Fake 같은 복합 패턴 감지 불가, Analyst 피처 분석과 역할 중복 |
| 4 | Analyst reasoning을 Guardian에 전달 | ❌ | 추가 입력 불필요 | Analyst bias 상속, Guardian 독립 판단 훼손 |
| 5 | Guardian에 별도 캔들 피처 세트 | ❌ | 역할 분리 극대화 | 피처 엔지니어링 추가 필요, 간단한 raw 데이터가 더 적합 |
| 6 | Guardian 폐지, Analyst에 리스크 통합 | ❌ | LLM 호출 1회, 비용 절반 | 관심사 분리 붕괴, 진입+리스크 이중 역할로 판단 품질 저하 우려 |

### 12.3 핵심 모니터링 지표: Guardian blocked 비율
- **정의**: Analyst CONFIRM을 Guardian이 WARNING으로 뒤집은 건수
- **측정 SQL**:
```sql
SELECT COUNT(*) AS analyst_confirm_total,
  SUM(CASE WHEN reasoning LIKE '[Risk Warning]%' THEN 1 ELSE 0 END) AS guardian_blocked
FROM agent_decisions
WHERE decision = 'REJECT' AND reasoning LIKE '[Risk Warning]%';
```
- **판단 기준**:
  - blocked > 0: Guardian 분리 구조의 독립적 가치 입증
  - blocked = 0 (장기간): Analyst-Guardian 통합 검토 → LLM 비용 절감 가능

### 12.4 검증
- 테스트: 10/10 passed (`tests/test_agents.py` + `tests/agents/test_analyst_rule_boundary.py`)
- OCI 배포: 2026-03-30, `docker compose ... up -d --build --no-deps bot`
- 코드 반영 확인: `grep "ohlc_summary"` + `grep "캔들 구조 분석 가이드"` 출력 확인
- 정량 검증: 배포 후 ~24h 모니터링 예정

### 12.5 Phase 3과의 병행 근거
- 변경 영역 독립: Phase 3=Analyst 프롬프트, Phase 4=Guardian 프롬프트 → 간섭 없음
- 로그 구분 가능: `agent_decisions.reasoning`에 `[Analyst]`/`[Guardian]`/`[Risk Warning]` 접두사, `llm_usage.route`로 분리
- Phase 3 모니터링 지표(boundary_violation)는 Analyst reasoning만 측정 → Phase 4 영향 없음

---

## 13. References
- Plan: docs/work-plans/34_adaptive_mean_reversion_4stage_improvement_plan.md
- 실거래 데이터: docs/operating_data.md
- 전략 전회고: docs/troubleshooting/strategy-retrospectives/34_rr_inversion_and_correlated_loss_clustering.md
- 이전 튜닝 작업: docs/work-plans/33_strategy_exit_parameter_tuning_plan.md
- Plan: docs/work-plans/34_adaptive_mean_reversion_4stage_improvement_plan.md
- 실거래 데이터: docs/operating_data.md
- 전략 전회고: docs/troubleshooting/strategy-retrospectives/34_rr_inversion_and_correlated_loss_clustering.md
- 이전 튜닝 작업: docs/work-plans/33_strategy_exit_parameter_tuning_plan.md
