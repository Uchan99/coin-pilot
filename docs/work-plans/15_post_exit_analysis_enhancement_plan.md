# 15. 매도 후 사후 분석 강화 계획

**작성일**: 2026-02-19
**상태**: Draft
**선행 의존**: 13번 전략 레짐 신뢰성 작업 완료 + 14번 Trade Count 분리 핫픽스 적용 후 권장

---

## 1. 배경

현재 매도(Exit) 로직은 5가지 룰 기반 조건(STOP_LOSS, TRAILING_STOP, TAKE_PROFIT, RSI_OVERBOUGHT, TIME_LIMIT)이 트리거되면 AI 판단 없이 즉시 실행된다. 이 설계는 리스크 관리 관점에서 올바르나, **"그 매도가 최선이었는가?"를 사후에 평가할 데이터가 없다**는 문제가 있다.

### 현재 한계

| 구성요소 | 현재 수준 | 한계 |
|---|---|---|
| `TradingHistory` | exit_reason, regime, HWM 저장 | 매도 후 가격 추적 없음 |
| `DailyReporter` | 일간 PnL, 거래 횟수만 LLM에 전달 | win_rate=0.0 하드코딩, 개별 거래 분석 없음 |
| `PerformanceAnalytics` | MDD, Sharpe, Win Rate 계산기 존재 | DailyReporter에서 실제 미사용 |

### 해결하려는 질문

- TRAILING_STOP 후 가격이 평균적으로 얼마나 더 올랐는가? (조기 청산 여부)
- STOP_LOSS 발동 후 반등했는가? (SL 너무 타이트한지)
- TIME_LIMIT 청산 건의 이후 추이는? (보유 기간 적절성)
- 레짐별로 exit 파라미터가 최적인가?

---

## 2. 목표

### 2.1 기능 목표

1. 매도 후 1h/4h/12h/24h 시점의 가격 변동을 자동 수집.
2. exit_reason별 사후 성과 통계를 일간 리포트에 포함.
3. 주간/월간 단위로 exit 파라미터 조정 제안을 자동 생성.

### 2.2 정량 목표

1. 매도 후 가격 추적 데이터 수집률 95% 이상 (24h 시점 기준).
2. DailyReporter에 exit_reason별 통계 및 win_rate 실데이터 포함.
3. 월간 리포트에서 최소 1건 이상의 파라미터 튜닝 제안 생성.

---

## 3. 구현 범위

### Phase 1. 매도 후 가격 추적 (Post-Exit Price Tracker) — P0

매도 후 시장이 어떻게 움직였는지를 정량적으로 기록하는 인프라 구축.
Phase 2, 3의 전제 조건이므로 최우선 구현.

#### 3.1 TradingHistory 모델 확장

**변경 내용**
- `TradingHistory`에 `post_exit_prices` JSONB 컬럼 추가.
- 저장 포맷:
```json
{
  "1h":  {"price": 95000000, "change_pct": -0.5, "tracked_at": "2026-02-19T10:00:00Z"},
  "4h":  {"price": 96000000, "change_pct": 0.5,  "tracked_at": "2026-02-19T13:00:00Z"},
  "12h": {"price": 93500000, "change_pct": -2.1, "tracked_at": "2026-02-19T21:00:00Z"},
  "24h": {"price": 94200000, "change_pct": -1.3, "tracked_at": "2026-02-20T09:00:00Z"}
}
```

**수정 파일**
- `src/common/models.py` (컬럼 추가)
- SQL 마이그레이션 스크립트 신규 생성 (`migrations/v3_2_2_post_exit_tracking.sql`)

**완료 기준**
- SELL 거래 레코드에 `post_exit_prices` 컬럼이 존재하고, 초기값은 `NULL`.

#### 3.2 Post-Exit Tracker Scheduler Job

**변경 내용**
- 새로운 Scheduler job `track_post_exit_prices_job()` 구현.
- 실행 주기: **10분마다** (1h/4h/12h/24h 각 시점의 도래 여부를 체크).
- 로직:
  1. `TradingHistory`에서 `side='SELL'` AND `executed_at IS NOT NULL` AND `post_exit_prices`가 미완성인 레코드 조회.
  2. 각 레코드의 `executed_at` 기준으로 1h/4h/12h/24h 경과 여부 확인.
  3. 경과한 시점에 대해 `MarketData`에서 해당 시점의 close price 조회.
  4. `change_pct = (post_price - exit_price) / exit_price * 100` 계산.
  5. `post_exit_prices` JSONB 업데이트 (부분 업데이트, 기존 시점 데이터 보존).
  6. 4개 시점 모두 채워진 레코드는 이후 조회에서 제외.

**수정 파일**
- `src/analytics/post_exit_tracker.py` (신규)
- `src/bot/main.py` (Scheduler job 등록)
- `migrations/v3_2_2_post_exit_tracking.sql` (컬럼/인덱스)

**완료 기준**
- SELL 실행 후 1h 경과 시점에 `post_exit_prices.1h`가 자동 기록됨.
- 24h 경과 후 4개 시점 모두 채워짐.
- DB에 MarketData가 없는 경우(데이터 gap) graceful skip 처리.

#### 3.3 Post-Exit 메트릭 노출

**변경 내용**
- Prometheus 메트릭 추가:
  - `coinpilot_post_exit_tracked_total` (Counter): 추적 완료 건수
  - `coinpilot_post_exit_missed_total` (Counter): 데이터 부재로 추적 실패 건수

**수정 파일**
- `src/utils/metrics.py`

---

### Phase 2. DailyReporter 강화 — P1

기존 DailyReporter의 빈약한 데이터를 실질적인 분석 리포트로 개선.

#### 3.4 거래별 PnL 및 Win Rate 실데이터 연동

**변경 내용**
- `_fetch_daily_data()`에서 SELL 거래의 실제 PnL 계산:
  - 매칭 로직: 동일 symbol의 직전 BUY 거래 `price`와 SELL `price` 비교.
  - 또는 SELL 체결 이력에 `entry_avg_price`를 명시 저장하여 직접 계산(권장).
- `win_rate` 하드코딩(0.0) 제거 → 실제 계산 값 사용.
- `PerformanceAnalytics.calculate_win_rate()` 연동.

**수정 파일**
- `src/agents/daily_reporter.py`
- `src/engine/executor.py` (SELL 시 `entry_avg_price` 저장 시)

**완료 기준**
- DailyReporter 출력의 win_rate가 실제 당일 거래 기반 값.

#### 3.5 Exit Reason별 통계 집계

**변경 내용**
- `_fetch_daily_data()` 반환값에 exit_reason별 집계 추가:
```python
{
  "exit_breakdown": {
    "STOP_LOSS": {"count": 2, "avg_pnl_pct": -3.2, "avg_post_1h_pct": 0.8},
    "TRAILING_STOP": {"count": 1, "avg_pnl_pct": 2.1, "avg_post_1h_pct": 1.5},
    ...
  }
}
```
- Phase 1의 `post_exit_prices` 데이터가 있으면 `avg_post_1h_pct` 등 포함.
- 없으면 해당 필드 생략 (Phase 1 미완료 시에도 exit_breakdown 자체는 동작).

**수정 파일**
- `src/agents/daily_reporter.py`

**완료 기준**
- 일간 리포트에 exit_reason별 건수 및 평균 PnL이 포함됨.

#### 3.6 LLM 프롬프트 강화

**변경 내용**
- `_generate_llm_summary()` 프롬프트에 exit_breakdown 데이터 전달.
- LLM 역할 확장: 단순 브리핑 → **"오늘의 매매 판단 평가"** 포함.
- 프롬프트 예시:
```
[매도 후 추적 데이터]
- TRAILING_STOP 1건: 청산가 대비 1h 후 +1.5%, 24h 후 -0.3% → 적절한 청산
- STOP_LOSS 2건: 청산가 대비 1h 후 +0.8% → 조기 손절 가능성

위 데이터를 분석하여:
1. 오늘의 매매 요약 (3줄)
2. exit 파라미터 개선 제안 (있다면)
```

**수정 파일**
- `src/agents/daily_reporter.py`

**완료 기준**
- Discord 리포트에 exit 판단 평가 코멘트가 포함됨.

---

### Phase 3. 전략 파라미터 튜닝 제안 시스템 — P2

충분한 데이터 축적(최소 2~4주) 후 의미 있는 제안 생성.

#### 3.7 주간/월간 Exit 성과 집계기

**변경 내용**
- `src/analytics/exit_performance.py` (신규) 구현.
- 집계 항목:
  - 레짐별 × exit_reason별 건수, 평균 PnL, 평균 보유 시간
  - Post-exit 가격 추이 통계 (평균, 중앙값, 최대/최소)
  - "조기 청산율": post_exit_24h_change > +2% 인 건의 비율 (TP/TS 대상)
  - "과도 보유율": post_exit_24h_change < -3% 인 건의 비율 (TIME_LIMIT 대상)

**수정 파일**
- `src/analytics/exit_performance.py` (신규)

**완료 기준**
- 레짐 × exit_reason 피벗 테이블 형태의 성과 요약 딕셔너리 반환.

#### 3.8 파라미터 튜닝 제안 생성기

**변경 내용**
- `src/analytics/exit_performance.py`에 `generate_tuning_suggestions()` 메서드 추가.
- 룰 기반 제안 로직:

| 조건 | 제안 |
|---|---|
| TRAILING_STOP 후 avg_post_24h > +3% | `trailing_stop_pct` 완화 제안 (현재값 → +0.5%p) |
| STOP_LOSS 후 avg_post_4h > +1% | `stop_loss_pct` 완화 제안 |
| TIME_LIMIT 후 avg_post_24h < -2% | 현행 유지 (적절) |
| TAKE_PROFIT 후 avg_post_4h > +2% | `take_profit_pct` 상향 제안 |
| 특정 레짐에서 조기 청산율 > 40% | 해당 레짐 exit config 전반 재검토 알림 |

- 제안은 **텍스트 형태로만 생성** (자동 적용 없음).

**수정 파일**
- `src/analytics/exit_performance.py`

**완료 기준**
- 최소 20건 이상의 SELL 데이터가 쌓이면 제안 생성 가능.
- 데이터 부족 시 "데이터 부족으로 제안 보류" 메시지 반환.

#### 3.9 주간 리포트 Scheduler Job

**변경 내용**
- `weekly_exit_report_job()` 신규 Scheduler job 등록.
- 실행 주기: 매주 일요일 22:00 KST (13:00 UTC).
- 흐름:
  1. `ExitPerformanceAnalyzer`로 주간 집계 실행.
  2. `generate_tuning_suggestions()`으로 제안 생성.
  3. LLM으로 요약 정리.
  4. n8n 웹훅으로 Discord 전송 (`/webhook/weekly-exit-report`).

**수정 파일**
- `src/bot/main.py` (Scheduler job 등록)
- `src/agents/daily_reporter.py` 또는 별도 `src/agents/weekly_reporter.py`

**완료 기준**
- 매주 일요일 Discord에 주간 exit 성과 리포트 및 파라미터 제안이 전송됨.

#### 3.10 대시보드 Exit 분석 페이지

**변경 내용**
- Streamlit 대시보드에 Exit 분석 탭 추가.
- 시각화 항목:
  - exit_reason별 PnL 분포 (박스플롯)
  - Post-exit 가격 추이 (시점별 평균 change_pct 라인차트)
  - 레짐별 exit 성과 히트맵
  - 파라미터 튜닝 제안 텍스트 표시

**수정 파일**
- `src/dashboard/pages/7_exit_analysis.py` (신규, 기존 `5_system.py`/`06_chatbot.py`와 번호 충돌 회피)

**완료 기준**
- 대시보드에서 exit 성과를 시각적으로 확인 가능.

---

## 4. 작업 순서

```
Phase 1 (P0)
  ├── 3.1 모델 확장 + migration
  ├── 3.2 Tracker job 구현
  └── 3.3 메트릭 추가
  → 배포 후 24h 데이터 수집 확인

Phase 2 (P1) — Phase 1 배포 후 1주일 뒤 착수 권장
  ├── 3.4 PnL/Win Rate 실데이터 연동
  ├── 3.5 Exit Reason별 통계
  └── 3.6 LLM 프롬프트 강화
  → 배포 후 일간 리포트 품질 확인

Phase 3 (P2) — 최소 2~4주 데이터 축적 후 착수
  ├── 3.7 주간/월간 집계기
  ├── 3.8 튜닝 제안 생성기
  ├── 3.9 주간 리포트 job
  └── 3.10 대시보드 페이지
  → 첫 주간 리포트 발송 확인
```

---

## 5. 검증 계획

### 5.1 코드/테스트

- `tests/analytics/test_post_exit_tracker.py` (신규)
  - 1h/4h/12h/24h 각 시점 tracking 정상 동작
  - MarketData gap 시 graceful skip
  - 이미 완료된 레코드 재처리 방지
- `tests/analytics/test_exit_performance.py` (신규)
  - 레짐별 × exit_reason별 집계 정확성
  - 튜닝 제안 로직 경계값 테스트
- `tests/agents/test_daily_reporter.py` (보강)
  - win_rate 실데이터 연동 검증
  - exit_breakdown 포맷 검증

### 5.2 운영 검증

- Phase 1 배포 후:
  - `SELECT id, exit_reason, post_exit_prices FROM trading_history WHERE side='SELL' ORDER BY executed_at DESC LIMIT 10;`
  - 24h 경과 레코드의 4개 시점 채워짐 확인
- Phase 2 배포 후:
  - Discord 일간 리포트에 exit_breakdown 포함 여부 확인
  - win_rate 값이 0.0이 아닌 실제 값인지 확인
- Phase 3 배포 후:
  - 첫 주간 리포트 Discord 수신 확인
  - 대시보드 Exit 분석 페이지 렌더링 확인

### 5.3 관측 지표

- `coinpilot_post_exit_tracked_total` 증가 추이
- `coinpilot_post_exit_missed_total` 비율 (목표: 5% 미만)
- 일간 리포트의 exit_breakdown 정확성 (수동 spot check)

---

## 6. 롤백 계획

1. **Phase 1**: `post_exit_prices` 컬럼은 nullable이므로 기존 동작에 영향 없음. Scheduler job 비활성화만으로 롤백.
2. **Phase 2**: DailyReporter 변경은 리포트 포맷만 영향. 이전 프롬프트로 복원 가능.
3. **Phase 3**: 주간 리포트 job 비활성화 + 대시보드 페이지 제거로 즉시 롤백.
4. DB migration rollback: `migrations/v3_2_2_post_exit_tracking.sql`의 역방향 SQL 실행(컬럼/인덱스 제거)

---

## 7. 리스크 및 대응

### 7.1 MarketData gap으로 post-exit 추적 실패

- **대응**: 정확한 시점 데이터가 없으면 ±5분 범위 내 가장 가까운 캔들 사용. 그래도 없으면 skip 후 `missed` 메트릭 증가.

### 7.2 Scheduler job 부하

- **대응**: 10분 주기이며, 미완성 SELL 건만 조회하므로 쿼리 부하 미미.
- 인덱스 권장:
  - `CREATE INDEX ... ON trading_history (executed_at DESC) WHERE side='SELL' AND executed_at IS NOT NULL;`
  - JSONB 조건 조회가 많아지면 `GIN(post_exit_prices)` 인덱스 추가 검토.

### 7.3 LLM 비용 증가 (Phase 2~3)

- **대응**: DailyReporter는 기존 1일 1회 호출 유지. 주간 리포트도 1주 1회. 추가 비용 미미 (gpt-4o-mini 기준 건당 < $0.01).

### 7.4 튜닝 제안의 과신

- **대응**: 자동 적용 절대 불가. 텍스트 제안만 생성하며, 적용은 반드시 운영자 수동 판단. 제안 메시지에 "참고용이며 자동 적용되지 않습니다" 명시.

### 7.5 데이터 부족 시 통계 왜곡

- **대응**: Phase 3 집계기에 최소 샘플 수 조건 적용 (exit_reason별 최소 5건). 미달 시 "데이터 부족" 표기.

---

## 8. 산출물

1. Phase 1: SQL migration(`migrations/v3_2_2_post_exit_tracking.sql`) + `post_exit_tracker.py` + Scheduler job
2. Phase 2: DailyReporter 강화 PR
3. Phase 3: `exit_performance.py` + 주간 리포트 job + 대시보드 페이지
4. 각 Phase별 테스트 코드
5. `docs/work-result/15_post_exit_analysis_result.md` 결과 문서
