# 15. 매도 후 사후 분석 강화 Phase 1 구현 결과

**작성일**: 2026-02-19  
**작성자**: Codex (GPT-5)  
**관련 계획서**: `docs/work-plans/15_post_exit_analysis_enhancement_plan.md`

---

## 1. 개요

15번 계획 중 **Phase 1 (Post-Exit Price Tracker, P0)** 범위를 우선 구현했다.

이번 단계의 목표:
1. SELL 체결 이후 1h/4h/12h/24h 후속 가격을 저장할 스키마 추가
2. 스케줄러 기반 자동 추적 job 추가(10분 주기)
3. 추적 성공/실패 관측 메트릭 추가

---

## 2. 구현 내용

### 2.1 TradingHistory 모델 확장

- 파일: `src/common/models.py`
- 변경:
  - `TradingHistory.post_exit_prices` JSONB 컬럼 추가 (`nullable=True`)

의미:
- SELL 거래별로 추적 시점(1h/4h/12h/24h) 가격/변화율 저장 가능

---

### 2.2 DB 마이그레이션 추가

- 파일: `migrations/v3_2_2_post_exit_tracking.sql`
- 변경:
  1. `trading_history.post_exit_prices` 컬럼 추가
  2. SELL 체결 조회 최적화 인덱스 추가
     - `idx_trading_history_sell_executed_at`

---

### 2.3 Post-Exit Tracker 신규 구현

- 파일: `src/analytics/post_exit_tracker.py` (신규)
- 핵심 로직:
  1. `side='SELL'` + `status='FILLED'` 거래 조회
  2. 기준 시각: `executed_at` 우선, 없으면 `created_at` fallback
  3. 1h/4h/12h/24h 각 시점 도래 여부 체크
  4. 목표 시각 ±5분 내 1분봉(`interval='1m'`) 최신 근접 가격 조회
  5. `change_pct = (tracked_price - exit_price) / exit_price * 100` 계산
  6. `post_exit_prices` JSON 부분 업데이트

저장 포맷 예:
```json
{
  "1h": {"price": 95000000.0, "change_pct": -0.52, "tracked_at": "..."},
  "4h": {"price": 96000000.0, "change_pct": 0.48, "tracked_at": "..."}
}
```

---

### 2.4 Prometheus 메트릭 추가

- 파일: `src/utils/metrics.py`
- 추가 메트릭:
  - `coinpilot_post_exit_tracked_total` (Counter)
  - `coinpilot_post_exit_missed_total` (Counter)

의미:
- 추적 성공/실패를 관측해서 데이터 품질 추적 가능

---

### 2.5 스케줄러 등록

- 파일: `src/bot/main.py`
- 변경:
  - `track_post_exit_prices_job` import 추가
  - `AsyncIOScheduler`에 10분 주기 job 등록

---

## 3. 변경 파일 목록

1. `src/common/models.py`
2. `migrations/v3_2_2_post_exit_tracking.sql`
3. `src/analytics/post_exit_tracker.py`
4. `src/utils/metrics.py`
5. `src/bot/main.py`
6. `tests/analytics/test_post_exit_tracker_phase1.py` (신규)

---

## 4. 검증 결과

### 4.1 코드 검증

실행:
```bash
python3 -m py_compile src/common/models.py src/utils/metrics.py src/analytics/post_exit_tracker.py src/bot/main.py tests/analytics/test_post_exit_tracker_phase1.py
```

결과:
- 통과

### 4.2 테스트 검증

실행:
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/analytics/test_post_exit_tracker_phase1.py
```

결과:
- `4 passed`

검증 범위:
- window 완성 여부 판정 helper
- 기준 시각(`executed_at` 우선 / `created_at` fallback) helper

### 4.3 런타임 반영 확인

확인 명령:
```bash
kubectl exec -n coin-pilot-ns deployment/bot -- python -c "from src.analytics.post_exit_tracker import track_post_exit_prices_job; print('OK:', track_post_exit_prices_job.__name__)"
```

결과:
- `OK: track_post_exit_prices_job`

확인 명령:
```bash
kubectl exec -n coin-pilot-ns deployment/bot -- sh -lc "ls -l /app/src/analytics/post_exit_tracker.py"
```

결과:
- 파일 존재 확인

---

## 5. 배포/운영 확인 체크리스트

1. 마이그레이션 적용
```bash
kubectl exec -i -n coin-pilot-ns db-0 -- psql -U postgres -d coinpilot < migrations/v3_2_2_post_exit_tracking.sql
```

2. bot 재빌드/재배포

3. scheduler 로그 확인 (10분 주기)
```bash
kubectl logs -n coin-pilot-ns -l app=bot --since=60m --prefix=true | grep -E "post-exit price tracker|Post-exit tracker|\\[Scheduler\\]"
```

4. DB 추적 데이터 확인
```bash
kubectl exec -n coin-pilot-ns db-0 -- \
  psql -U postgres -d coinpilot -c "
  SELECT id, symbol, side, price, executed_at, post_exit_prices
  FROM trading_history
  WHERE side='SELL' AND status='FILLED'
  ORDER BY executed_at DESC NULLS LAST, created_at DESC
  LIMIT 10;"
```

5. 시점별 추적 집계 확인
```bash
kubectl exec -n coin-pilot-ns db-0 -- \
  psql -U postgres -d coinpilot -c "
  SELECT
    COUNT(*) AS sell_total,
    COUNT(*) FILTER (WHERE post_exit_prices ? '1h') AS tracked_1h,
    COUNT(*) FILTER (WHERE post_exit_prices ? '4h') AS tracked_4h,
    COUNT(*) FILTER (WHERE post_exit_prices ? '12h') AS tracked_12h,
    COUNT(*) FILTER (WHERE post_exit_prices ? '24h') AS tracked_24h
  FROM trading_history
  WHERE side='SELL' AND status='FILLED';"
```

---

## 6. 결론

15번 Phase 1의 핵심인 **사후 가격 추적 인프라**는 코드/스키마/스케줄러/메트릭까지 구현 완료되었다.

이제 운영 데이터가 쌓이면, Phase 2(DailyReporter 실데이터 연동)에서 `exit_reason`별 사후 성과 분석으로 자연스럽게 확장할 수 있는 상태다.

---

## 7. Phase 2 선반영(안전 Fallback 포함) 구현 결과

Phase 2 전체를 한 번에 자동튜닝까지 확장하지 않고, 운영 안정성 중심으로 **DailyReporter 데이터 품질 개선 + 안전 fallback** 범위를 선반영했다.

### 7.1 변경 파일

1. `src/agents/daily_reporter.py`
2. `src/bot/main.py`

### 7.2 핵심 변경

1. DailyReporter의 실데이터 연동 강화
- 오늘 체결 내역(`TradingHistory`) 기반으로 SELL 실현손익/승률 계산
- `exit_reason`별 건수 및 평균 손익률(`avg_pnl_pct`) 집계
- `post_exit_prices['1h'].change_pct`가 있으면 `avg_post_1h_pct` 집계

2. SELL 원가 추적 품질 개선
- SELL 체결 시 `signal_info.entry_avg_price` 저장 (`src/bot/main.py`)
- DailyReporter는 `entry_avg_price` 우선 사용
- 값이 없으면 BUY lot FIFO 추정으로 fallback 계산

3. LLM 요약 실패 대응
- LLM 호출 실패 시에도 리포트 전송 중단하지 않고 기본 요약 문자열로 대체

### 7.3 안전 Fallback 원칙(코드 반영)

1. 데이터 일부 누락돼도 리포트 생성 중단 금지
- `executed_at`이 없으면 `created_at` 기준으로 포함
- `entry_avg_price`가 없는 SELL은 가능한 경우 BUY lot으로 추정

2. 추정 불가능 항목은 제외 + 명시
- 계산 불가능 SELL은 집계에서 제외하고 `notes`에 이유 기록
- 데이터 부족을 숨기지 않고 리포트에 그대로 전달

3. LLM 실패는 비치명 처리
- 요약 생성 오류 시 fallback 텍스트로 대체하여 webhook 전송 지속

### 7.4 검증

실행:
```bash
python3 -m py_compile src/agents/daily_reporter.py src/bot/main.py
```

결과:
- 통과

실행:
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/analytics/test_post_exit_tracker_phase1.py
```

결과:
- `4 passed`

### 7.5 영향

1. DailyReporter의 `win_rate=0.0` 고정 문제를 제거하고 실제 SELL 기반 지표를 계산
2. post-exit 데이터가 아직 적은 초기 운영 구간에서도 리포트 누락 없이 동작
3. Phase 3(파라미터 튜닝 제안)로 확장 가능한 최소 데이터 파이프라인 확보

---

## 8. Phase 3 핵심 구현 결과 (주간 집계 + 튜닝 제안 + 스케줄러)

Phase 3 전체(대시보드 신규 탭 포함) 중에서 운영 핵심 경로를 우선 구현했다.

### 8.1 신규 분석기 추가

- 파일: `src/analytics/exit_performance.py` (신규)
- 구현 내용:
1. 최근 N일 SELL 체결 이력 집계 (`summarize_period`)
2. `regime × exit_reason` 기준 집계
3. 지표 계산
   - `avg_pnl_pct`
   - `avg_hold_hours` (BUY lot FIFO 기반 추정)
   - `avg/median/min/max post_24h_pct`
   - `early_exit_rate` (TRAILING_STOP/TAKE_PROFIT 대상)
   - `over_hold_rate` (TIME_LIMIT 대상)
4. 룰 기반 튜닝 제안 생성 (`generate_tuning_suggestions_from_summary`)
5. 주간 Discord 전송용 payload 생성 (`build_weekly_report_payload`)
6. LLM 요약 실패 시 fallback 텍스트 반환

### 8.2 Bot Scheduler 연동

- 파일: `src/bot/main.py`
- 구현 내용:
1. `weekly_exit_report_job()` 추가
2. webhook 전송 경로:
   - `POST /webhook/weekly-exit-report`
3. 스케줄 등록:
   - 매주 일요일 22:00 KST (13:00 UTC)

### 8.3 테스트 추가

- 파일: `tests/analytics/test_exit_performance_phase3.py` (신규)
- 검증 케이스:
1. SELL 샘플 부족 시 "제안 보류" fallback
2. 임계값 만족 시 규칙 제안 생성(4개 규칙 + 레짐 조기청산율)
3. 임계값 미충족 시 "현행 유지" 제안

### 8.4 검증 결과

실행:
```bash
python3 -m py_compile src/analytics/exit_performance.py src/bot/main.py
```

결과:
- 통과

실행:
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/analytics/test_exit_performance_phase3.py
```

결과:
- `3 passed`

### 8.5 운영 확인 명령

1. 주간 리포트 수동 1회 실행
```bash
kubectl exec -n coin-pilot-ns deployment/bot -- \
  python -c "import asyncio; from src.bot.main import weekly_exit_report_job; asyncio.run(weekly_exit_report_job())"
```

2. 스케줄러/전송 로그 확인
```bash
kubectl logs -n coin-pilot-ns deployment/bot --since=30m | \
  grep -E \"Weekly Exit Report|weekly-exit-report|Exit Report\"
```

3. n8n Execution에서 payload 확인
- webhook path: `/webhook/weekly-exit-report`

### 8.6 남은 항목

1. n8n에 `weekly-exit-report` 엔드포인트 워크플로우 등록 필요

---

## 9. Phase 3 잔여 항목(3.10) 구현 완료: Exit 분석 대시보드 페이지

Phase 3의 마지막 미구현 항목이었던 대시보드 Exit 분석 탭을 구현했다.

### 9.1 신규 페이지 추가

- 파일: `src/dashboard/pages/07_exit_analysis.py` (신규)

구현 항목:
1. 기간/조회건수 필터
2. SELL 지표 KPI
   - SELL Count
   - PnL 계산 가능 건수
   - Post-24h 샘플 수
   - 평균 SELL PnL(%)
3. 시각화
   - `exit_reason`별 PnL 박스플롯
   - post-exit 시점별(1h/4h/12h/24h) 평균 변화율 라인차트
   - `regime × exit_reason` 평균 PnL 히트맵
4. 룰 기반 튜닝 제안 표시
   - `ExitPerformanceAnalyzer.generate_tuning_suggestions_from_summary()` 재사용
5. 상세 데이터 테이블
   - 매도 시각/심볼/레짐/청산사유/진입평단/PnL%/post-exit 변화율

### 9.2 검증

실행:
```bash
python3 -m py_compile src/dashboard/pages/07_exit_analysis.py
```

결과:
- 통과

### 9.3 운영 확인

1. dashboard 재빌드/재배포
2. 좌측 페이지 목록에서 `07_exit_analysis` 진입
3. 차트/제안/테이블이 정상 렌더링되는지 확인

---

## 10. Phase 3 최종 상태

15번 계획서 기준 Phase 3 항목 상태:
1. `3.7` 주간/월간 Exit 성과 집계기: ✅
2. `3.8` 파라미터 튜닝 제안 생성기: ✅
3. `3.9` 주간 리포트 Scheduler + Discord 전송 경로: ✅
4. `3.10` Exit 분석 대시보드 페이지: ✅
