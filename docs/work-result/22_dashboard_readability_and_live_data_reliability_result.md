# 22. 대시보드 가독성/실시간성 표준화(Spec-First) 결과

작성일: 2026-03-12
작성자: Codex
관련 계획서: `docs/work-plans/22_dashboard_readability_and_live_data_reliability_plan.md`
상태: Done
완료 범위: Spec 산출물 4종 전체
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - 현재 Streamlit 대시보드 8개 화면 inventory 작성
  - 운영 UI 정보 우선순위 매트릭스 정의
  - 데이터 freshness 계약서 정의
  - stale/manual 상태표와 `23` acceptance checklist 확정
  - `23` 계획, 체크리스트, README, Charter 동기화
- 목표(요약):
  - 프론트 기술 스택과 무관하게 재사용 가능한 dashboard 운영 표준을 먼저 고정해 `23`의 수용 기준을 명확히 한다.
- 이번 구현이 해결한 문제(한 줄):
  - 현재 대시보드의 가독성/실시간성 규칙이 페이지별 ad-hoc 구현에 머물러 있던 상태를 운영 표준 문서로 정리했다.
- 해결한 문제의 구체 정의(필수: 증상/영향/재현 조건):
  - 증상:
    - `src/dashboard/utils/db_connector.py`는 `@st.cache_data(ttl=30)`를 사용하지만 페이지별 freshness 표기가 통일되지 않았다.
    - `src/dashboard/components/autorefresh.py`는 10~300초 자동 새로고침을 제공하지만, 데이터셋별 stale 기준과 사용자 액션 규칙이 없었다.
    - `src/dashboard/pages/2_market.py`만 `Last Update`와 `age > 120` stale 판정을 가지고 있고, 다른 화면은 동일 의미의 freshness를 드러내지 않았다.
  - 영향:
    - 운영자가 지금 보는 값이 실시간 판단용인지, 지연/오류/수동 확인용인지 즉시 구분하기 어려웠다.
    - `23` Next.js 이관 시 무엇을 그대로 유지하고 무엇을 보완해야 하는지 acceptance 기준이 비어 있었다.
  - 재현 조건:
    - 자동 새로고침을 켠 상태에서 `Overview/Risk/History/System`을 오가거나, monitoring-only/수동 확인 성격의 운영 데이터를 UI에 붙이려 할 때
- 기존 방식/상태(Before) 기준선 요약(필수):
  - 화면별 우선순위 매트릭스: 없음
  - 표준 freshness 계약서: 없음
  - 표준 stale/manual 상태표: 없음
  - `23` acceptance checklist: 없음

---

## 2. 구현 내용(핵심 위주)
### 2.1 화면별 정보 우선순위 매트릭스
- 파일/모듈:
  - `src/dashboard/app.py`
  - `src/dashboard/pages/1_overview.py`
  - `src/dashboard/pages/2_market.py`
  - `src/dashboard/pages/3_risk.py`
  - `src/dashboard/pages/4_history.py`
  - `src/dashboard/pages/5_system.py`
  - `src/dashboard/pages/06_chatbot.py`
  - `src/dashboard/pages/07_exit_analysis.py`
  - `docs/PROJECT_CHARTER.md`
- 변경 내용:
  - 현재 화면 8개를 대상으로 Primary / Secondary / Diagnostic 정보를 문서화했다.
  - monitoring-only(`21-03`, `28`)와 manual-only(`21-10`) 데이터를 어느 계층에 배치해야 하는지 원칙을 추가했다.
- 효과/의미:
  - `23`에서 화면을 재구성할 때 "무엇이 위로 올라와야 하는지"를 감으로 결정하지 않게 됐다.

| 화면 | Primary | Secondary | Diagnostic | 비고 |
|---|---|---|---|---|
| Landing | 없음 | 네비게이션/사용 가이드 | 수동 DB 연결 확인 | 운영 허브, `manual-only` 허용 |
| Overview | 총 평가액, 현재 잔고, 활성 포지션 | 누적 손익, 총 체결 | 없음 | 실시간 운영 판단 최상위 |
| Market | 현재 심볼 bot regime/action, bot status freshness | 캔들 차트, 현재가 | reasoning/raw bot state | Redis status는 DB 차트보다 더 엄격한 freshness 적용 |
| Risk | Trading status, 일일 손익/BUY count | Fill counts | risk audit log | limit breach는 stale보다 우선 경고 |
| History | 최신 FILLED 체결 요약 | side/status 차트 | regime/exit_reason/detail mode | 탐색형 조회 화면 |
| System | DB/Redis/n8n 연결성 | 최근 agent_decisions | risk audit, 운영 상태 설명 | Diagnostic 중심 |
| Chatbot | 없음 | 대화 세션 | 캐시/세션 상태 | 자동 freshness 핵심 화면 아님 |
| Exit Analysis | SELL 성과 요약, 룰 기반 제안 | regime/exit reason 시각화 | post-exit sample 부족 경고 | 분석형 화면, 실시간 핵심 아님 |

### 2.2 Freshness 계약서
- 파일/모듈:
  - `docs/PROJECT_CHARTER.md`
  - `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`
- 변경 내용:
  - 데이터셋/화면별 `freshness_status`, `last_updated_at`, `data_age_sec`, `stale_threshold_sec`, 사용자 액션 규칙을 정의했다.
  - `21-03`, `28`은 Diagnostic + monitoring-only, `21-10`은 manual-only로 분리했다.
- 효과/의미:
  - 자동 새로고침이 켜져 있어도 데이터 의미가 혼재되지 않고, `23` 구현 시 공통 컴포넌트 요구사항으로 바로 연결할 수 있다.

| 계약 대상 | 주 데이터 소스 | freshness_status 대상 | stale_threshold_sec | 상태 분류 | 사용자 액션 |
|---|---|---|---:|---|---|
| Overview KPI/포지션 | PostgreSQL (`account_state`, `daily_risk_state`, `positions`, `market_data`) | 필수 | 60 | `fresh/delayed/stale/failed` | 자동 재조회 + 수동 재조회 |
| Market 캔들 | PostgreSQL `market_data` | 필수 | 90 | `fresh/delayed/stale/failed` | 자동 재조회 유지 |
| Market bot status | Redis `bot:status:*` | 필수 | 120 | `fresh/delayed/stale/failed` | stale 시 경고 배지 + reasoning 축소 가능 |
| Risk KPI | PostgreSQL `daily_risk_state` | 필수 | 60 | `fresh/delayed/stale/failed` | stale 시 limit 판정 카드에 경고 |
| Risk audit log | PostgreSQL `risk_audit` | 선택 | 300 | `fresh/delayed/stale/failed` | 로그 자체는 Diagnostic로 유지 |
| History | PostgreSQL `trading_history` | 필수 | 60 | `fresh/delayed/stale/failed` | 필터 상태 유지 + 수동 재조회 |
| System connectivity | DB/Redis/n8n 헬스체크 | 선택 | 120 | `fresh/delayed/stale/failed` | 실패 사유 직접 표기 |
| System decision/audit tables | PostgreSQL `agent_decisions`, `risk_audit` | 선택 | 300 | `fresh/delayed/stale/failed` | Diagnostic 영역에만 노출 |
| Chatbot session | Streamlit session state | 제외 | 0 | `manual-only` | 사용자 입력 시만 갱신 |
| Exit Analysis | PostgreSQL `trading_history`, post-exit analytics | 필수 | 300 | `fresh/delayed/stale/failed` | sample 부족 시 `failed`가 아니라 explanatory empty-state |

### 2.3 Stale UX 상태표
- 파일/모듈:
  - `docs/PROJECT_CHARTER.md`
  - `docs/work-result/22_dashboard_readability_and_live_data_reliability_result.md`
- 변경 내용:
  - `fresh / delayed / stale / failed / manual-only` 5개 상태와 각 상태의 UI/행동 규칙을 정의했다.
- 효과/의미:
  - `23`에서 화면별로 다른 문구를 임의로 만드는 대신, 상태 기계(state machine)처럼 일관된 badge/empty-state/action을 적용할 수 있다.

| 상태 | 조건 | UI 규칙 | 운영 해석 |
|---|---|---|---|
| `fresh` | `data_age_sec <= stale_threshold_sec` | 기본 색상, 경고 배지 없음 | 정상 |
| `delayed` | 임계치 초과이지만 `2 x stale_threshold_sec` 이내 | 노란 배지, 자동 재조회 유지 | 지연 시작 |
| `stale` | `2 x stale_threshold_sec` 초과 | 빨간/회색 경고, 수동 재조회 노출 | 현재 값 신뢰 낮음 |
| `failed` | 최신 조회 실패 또는 정상 스냅샷 부재 | 오류 이유 + fallback/empty-state 분리 표기 | 데이터 경로 확인 필요 |
| `manual-only` | 자동 freshness 대상이 아닌 수동 검증/세션 데이터 | 자동 경고 제외, 수동 명령/설명 연결 | `21-10` 같은 수동 검증용 |

### 2.4 `23` acceptance checklist 확정
- 파일/모듈:
  - `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`
  - `README.md`
  - `docs/checklists/remaining_work_master_checklist.md`
- 변경 내용:
  - `23`이 `22` 완료 결과 문서를 source of truth로 참조하도록 수정했다.
  - main task `22` 완료에 맞춰 체크리스트/README/Charter를 동기화했다.
- 효과/의미:
  - `23`은 이제 추상적 "가독성 개선"이 아니라 구체적인 PASS/FAIL 체크리스트를 가진 이관 작업이 됐다.

`23` acceptance checklist:
1. 화면 8개(Landing/Overview/Market/Risk/History/System/Chatbot/Exit Analysis)의 정보 계층이 본 문서 표와 의미상 동일할 것
2. Primary 지표는 각 화면 첫 뷰포트에서 확인 가능할 것
3. DB/Redis 기반 데이터 블록은 `last_updated_at`과 freshness badge를 함께 노출할 것
4. `freshness_status`는 `fresh/delayed/stale/failed/manual-only`만 사용할 것
5. `Overview`는 총 평가액/현재 잔고/활성 포지션을 Primary로 유지할 것
6. `Market`은 bot status와 차트의 freshness 기준을 분리해서 보여줄 것
7. `Risk`는 일일 한도 위반 경고가 stale 경고보다 우선 노출될 것
8. `History`는 필터 상태를 유지한 채 수동 재조회가 가능할 것
9. `System`은 연결 상태와 Diagnostic 로그를 같은 계층으로 섞지 않을 것
10. `Chatbot`은 자동 freshness 핵심 화면으로 취급하지 않을 것
11. `Exit Analysis`는 sample 부족을 오류와 구분된 explanatory empty-state로 표시할 것
12. monitoring-only 지표(`21-03`, `28`)는 Diagnostic 영역에만 배치할 것
13. `21-10` 수동 검증 데이터는 `manual-only`로 분리할 것
14. `21-04 blocked` 상태의 비용/토큰 freshness는 기본 필수 지표에서 제외하고 추후 확장 항목으로 둘 것
15. 장식성 이모지/문구가 Primary KPI label을 덮지 않을 것
16. README/체크리스트/Charter 참조 링크가 `22` 완료 상태와 일치할 것

---

## 3. 변경 파일 목록
### 3.1 수정
1) `docs/work-plans/22_dashboard_readability_and_live_data_reliability_plan.md`
2) `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`
3) `docs/checklists/remaining_work_master_checklist.md`
4) `docs/PROJECT_CHARTER.md`
5) `README.md`

### 3.2 신규
1) `docs/work-result/22_dashboard_readability_and_live_data_reliability_result.md`

---

## 4. DB/스키마 변경
- 변경 사항:
  - 없음
- 마이그레이션:
  - 없음
- 롤백 전략/주의점:
  - 문서 작업이므로 관련 문서 revert 시 원복 가능

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `rg --files src/dashboard/pages | rg -v '__init__' | wc -l`
  - `rg -n "cache_data|auto_refresh|Last Update|Refresh Status|age > 120" src/dashboard`
  - `rg -n "화면별 정보 우선순위 매트릭스|Freshness 계약서|Stale UX 상태표|23 acceptance checklist" docs/work-result/22_dashboard_readability_and_live_data_reliability_result.md`
- 결과:
  - Streamlit page 파일 7개 + `src/dashboard/app.py` 1개로 총 화면 8개를 inventory 대상으로 확정했다.
  - 현재 구현의 freshness 관련 포인트가 `ttl=30`, auto-refresh, `Market Last Update`, `System Refresh Status`에 흩어져 있음을 확인했다.
  - 결과 문서에 산출물 4종이 모두 존재함을 확인했다.

### 5.2 테스트 검증
- 실행 명령:
  - 없음(문서 작업)
- 결과:
  - 자동 테스트는 수행하지 않았다.
  - 사유: 이번 task는 코드/런타임 변경이 없는 spec 문서화 작업이다.

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법:
  - `rg -n "22.*done|대시보드 UI/freshness/stale 운영 표준" README.md docs/checklists/remaining_work_master_checklist.md docs/PROJECT_CHARTER.md docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`
- 결과:
  - README, 체크리스트, Charter, `23` 계획이 `22` 완료 결과를 기준으로 동기화됐다.

### 5.4 정량 개선 증빙(필수)
- 측정 기간/표본:
  - 2026-03-12
  - 화면 표본 8개, freshness 계약 10개, 상태 분류 5개, acceptance 항목 16개
- 측정 기준(성공/실패 정의):
  - 성공:
    1) 현재 화면 inventory가 누락 없이 문서화될 것
    2) freshness/stale/manual 상태가 단일 표준으로 정의될 것
    3) `23`이 직접 참조할 acceptance checklist가 명시될 것
  - 실패:
    1) 화면 누락
    2) monitoring-only/manual-only 정책 미반영
    3) `23` 참조 경로 불명확
- 데이터 출처(SQL/로그/대시보드/스크립트):
  - `src/dashboard/*.py`
  - `docs/work-result/22_dashboard_readability_and_live_data_reliability_result.md`
  - `README.md`
  - `docs/PROJECT_CHARTER.md`
- 재현 명령:
  - `rg --files src/dashboard/pages | rg -v '__init__' | wc -l`
  - `rg -n "cache_data|auto_refresh|Last Update|Refresh Status|age > 120" src/dashboard`
  - `rg -n "화면별 정보 우선순위 매트릭스|Freshness 계약서|Stale UX 상태표|23 acceptance checklist" docs/work-result/22_dashboard_readability_and_live_data_reliability_result.md`
  - `rg -n "22.*done|대시보드 UI/freshness/stale 운영 표준" README.md docs/checklists/remaining_work_master_checklist.md docs/PROJECT_CHARTER.md docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`
- Before/After 비교표:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 문서화된 화면 inventory 수 | 0 | 8 | +8 | 측정 불가(분모 0) |
| 표준 freshness 계약 수 | 0 | 10 | +10 | 측정 불가(분모 0) |
| 표준 stale/manual 상태 수 | 0 | 5 | +5 | 측정 불가(분모 0) |
| `23` acceptance checklist 항목 수 | 0 | 16 | +16 | 측정 불가(분모 0) |
| `23` 선행 게이트의 `22` 결과 문서 직접 참조 수 | 0 | 1 | +1 | 측정 불가(분모 0) |
| README/체크리스트/Charter 동기화 문서 수 | 0 | 3 | +3 | 측정 불가(분모 0) |

---

## 6. 배포/운영 확인 체크리스트(필수)
1. `23` 구현 전 본 문서의 acceptance checklist를 source of truth로 사용할 것
2. `21-03`, `28`은 이번 이후에도 monitoring-only Diagnostic 취급을 유지할 것
3. `21-10`은 자동 freshness 대상이 아니라 `manual-only` 배지/영역으로 분리할 것

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 현재 Streamlit inventory를 먼저 정리하고, 프론트 무관 dashboard spec을 Charter + Result에 고정한 뒤 `23`에서 구현한다.
- 고려했던 대안:
  1) Streamlit 화면을 즉시 리팩터한다.
  2) `23` Next.js 구현을 먼저 시작하면서 요구사항을 구현 중에 확정한다.
  3) 문서 산출물 4종을 먼저 확정하고 `23`은 그 결과를 acceptance 기준으로 사용한다. (채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1) 현재 대시보드의 실제 입력(`ttl=30`, auto-refresh, `Market`만 stale 표시)을 기준으로 spec을 만들 수 있어 추상 문서가 되지 않는다.
  2) `21-03/28 monitoring-only`, `21-04 blocked`, `21-10 manual verification`처럼 지금 당장 변동성이 큰 운영 상태를 구현 코드와 분리해 정리할 수 있다.
  3) `23`이 "가독성 개선" 같은 포괄 문장이 아니라 16개 acceptance 항목으로 PASS/FAIL 가능해진다.
- 트레이드오프(단점)와 보완/완화:
  1) 즉시 UI 체감 개선은 없다.
  2) 보완으로 Charter/README/체크리스트까지 함께 고정해 다음 구현자가 우회하기 어렵게 만들었다.

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) 없음
  2) 없음
- 주석에 포함한 핵심 요소:
  - 이번 작업은 문서 산출물 중심이라 코드 주석 변경이 없다.
  - 대신 Charter/Plan/Result에 의도, 불변조건, manual-only 예외, monitoring-only 배치 원칙을 명시했다.

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - 정보 우선순위 매트릭스, Freshness 계약서, Stale UX 상태표, `23` acceptance checklist를 모두 작성했다.
- 변경/추가된 부분(왜 바뀌었는지):
  - 초기 계획은 spec만 상정했지만, 실제 운영 규칙으로 쓰려면 Charter/README/체크리스트까지 함께 동기화해야 해서 범위를 문서 동기화까지 확장했다.
  - `21-03/28 monitoring-only`, `21-04 blocked`, `21-10 manual verification` 상태를 spec에 직접 반영했다. 현재 운영 입력을 반영하지 않으면 곧바로 stale 문서가 되기 때문이다.
- 계획에서 비효율적/오류였던 점(있다면):
  - 초기 `22` plan에는 현재 Streamlit 구현의 실제 freshness 포인트 inventory가 없어 spec이 추상화될 위험이 있었다. 이번 구현에서 이를 보강했다.

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - `22`는 완료(`done`)됐다.
  - `23`은 이제 `22` 결과를 acceptance source of truth로 참조할 수 있지만, 여전히 `21-03/21-04/28` 선행 게이트 때문에 `blocked`가 맞다.
- 후속 작업(다음 plan 번호로 넘길 것):
  1) `23`: `21-03/28` monitoring-only 관측과 `21-04 blocked` 해제 여부를 본 뒤 착수 판단
  2) `21-04` 해제 시 비용/토큰 freshness를 본 spec의 확장 계약으로 편입

---

## 11. README 동기화 여부
- 본 작업은 main task `done` 기준을 충족해 `README.md`를 같은 변경 세트에서 동기화했다.
- 반영 내용:
  - 최근 운영 변경 요약에 `22` dashboard spec 완료를 추가
  - 우선순위 백로그에서 `22` 상태를 `done`으로 변경
- 검증 명령:
  - `rg -n "대시보드 UI/freshness/stale 운영 표준|22.*done" README.md`

---

## 12. References
- `docs/work-plans/22_dashboard_readability_and_live_data_reliability_plan.md`
- `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`
- `docs/checklists/remaining_work_master_checklist.md`
- `docs/PROJECT_CHARTER.md`
- `src/dashboard/app.py`
- `src/dashboard/pages/1_overview.py`
- `src/dashboard/pages/2_market.py`
- `src/dashboard/pages/3_risk.py`
- `src/dashboard/pages/4_history.py`
- `src/dashboard/pages/5_system.py`
- `src/dashboard/pages/06_chatbot.py`
- `src/dashboard/pages/07_exit_analysis.py`
