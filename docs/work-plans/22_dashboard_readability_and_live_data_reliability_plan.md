# 22. 대시보드 가독성/실시간성 표준화(Spec-First) 계획

**작성일**: 2026-02-27  
**최종 수정일**: 2026-03-12  
**작성자**: Codex  
**상태**: Approved  
**관련 계획 문서**: `docs/work-plans/18-03_dashboard_db_connection_pool_resilience_plan.md`, `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`, `docs/work-plans/23-01_frontend_backend_repository_split_timing_plan.md`  
**관련 운영 결과 문서**: `docs/work-result/21-03_ai_decision_model_canary_experiment_result.md`, `docs/work-result/28_ai_decision_strategy_case_rag_result.md`, `docs/work-result/21-10_position_sizing_and_risk_cap_alignment_result.md`  
**승인 정보**: 사용자 승인 / 2026-03-12 / "우선 그렇게 진행해줘."

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 현재 대시보드 가독성이 낮고, 이모지/장식 요소가 과도해 정보 전달 집중도가 떨어짐.
  - 일부 탭이 최신 상태를 즉시 반영하지 못해 기존 데이터가 남아 보이는(stale) 현상이 있음.
  - 현재 구현 기준으로 `src/dashboard/utils/db_connector.py`는 전역 `@st.cache_data(ttl=30)`를 사용하고, `src/dashboard/components/autorefresh.py`는 세션별 10~300초 자동 새로고침을 제공하지만, 페이지별 freshness/stale 기준이 계약으로 통일되어 있지 않음.
  - `src/dashboard/pages/2_market.py`는 bot status에만 ad-hoc `120s` stale 판정을 두고 있고, `Overview/Risk/History/System`은 동일 의미의 freshness 표시가 부재함.
- 왜 즉시 대응이 필요했는지:
  - 실거래 전환 전 운영 판단은 대시보드 신뢰도에 의존하므로, UI 품질과 데이터 신선도 보장이 필요함.

## 0.1 현재 운영 기준선 (2026-03-12)
1. `21-03`은 canary 표본 부족으로 **monitoring-only** 상태다.
2. `28`은 `28-03` env passthrough fix까지 완료했고 post-redeploy `canary-rag` 표본 대기로 **monitoring-only** 상태다.
3. `21-10`은 post-deploy 수동 재확인 단계이며 cron 자동화 대상이 아니다.
4. `21-04`는 개인 계정 capability 제약으로 **blocked** 상태다.
5. 따라서 이번 `22`는 위 작업들의 완료를 기다리는 코드 구현이 아니라, 현재 운영 입력을 반영한 **Spec/Acceptance 기준 확정 작업**으로 착수 가능 여부를 판단해야 한다.

## 1. 문제 요약
- 증상:
  - 정보 우선순위가 불명확(핵심 숫자 대비 시각 요소 과다)
  - 탭별 갱신 타이밍 불일치 및 오래된 데이터 표시
  - 운영자가 “현재 상태”인지 “과거 캐시”인지 즉시 구분하기 어려움
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 대시보드 운영 가독성 저하
  - 리스크: 잘못된 시점 데이터 기반 운영 판단 가능성
  - 데이터: 탭/컴포넌트별 freshness 불일치
  - 비용: 오판으로 인한 대응 시간/운영 비용 증가
- 재현 조건:
  - 앱 탭 이동 반복, 백엔드 갱신 직후, 장시간 실행 세션에서 stale 노출

## 2. 목표 / 비목표
### 2.1 목표
1. 프론트엔드 기술 스택과 무관하게 재사용 가능한 **운영 UI 표준(spec)** 을 확정
2. 모든 탭에 데이터 freshness 표시 계약(마지막 갱신 시각, 지연 상태, stale 기준)을 정의
3. stale 데이터 탐지/표시/재조회 UX 규칙을 계약 형태로 고정
4. 23번 Next.js 이관 시 22번 표준을 그대로 수용 기준(acceptance)으로 사용
5. 현재 Streamlit 구현(`src/dashboard/app.py`, `src/dashboard/pages/*.py`)에 존재하는 가독성/실시간성 불일치를 페이지별 inventory로 문서화

### 2.2 비목표
1. Streamlit UI 코드 대규모 리팩터/재작성은 본 계획 범위 밖
2. Next.js 화면 구현 자체는 23번 계획 범위
3. 신규 백엔드 도메인 기능 추가는 범위 밖

## 3. 실행 게이트 (착수 시점 조건)
- 본 계획은 **배포/마이그레이션이 아닌 문서 기반 Spec 확정 단계**를 전제로 한다.
- 현재 판단:
  - `21-03`, `28`이 monitoring-only이고 `21-10`이 수동 검증 상태여도 `22`의 문서 구현은 진행 가능하다.
  - 다만 AGENTS 규칙상 main 계획은 승인 전 구현할 수 없으므로, 현재 필요한 즉시 액션은 **최신 상태를 반영한 계획 보강 후 승인 획득**이다.
- 승인 후 착수 조건:
  1) 본 계획서에 기재된 운영 입력(`21-03/28 monitoring-only`, `21-04 blocked`, `21-10 manual verification`)을 전제 조건으로 승인할 것
  2) 범위를 Spec/Acceptance 산출물 작성으로 한정하고, Streamlit/Next.js 코드 변경은 제외할 것
  3) `23`의 선행 게이트 문구를 갱신할 수 있도록 `22` 산출물을 source of truth로 사용할 것

## 4. 대응 전략
- 단기 핫픽스:
  - 운영 판단 방해 요소(장식/중복 문구/과도한 강조) 제거 기준을 spec으로 고정
- 근본 해결:
  - 프론트 공통 요구사항(정보 우선순위, stale 계약, 경고 레벨)을 먼저 문서화하고, 구현은 23에서 적용
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 데이터 age 임계치 초과 시 “stale 경고 배지 + 자동 재조회”
  - 조회 실패 시 마지막 정상 스냅샷 + 오류 사유 분리 표기
  - monitoring-only 작업(`21-03`, `28`)의 지표는 "실시간 거래 판단용 핵심", `21-10`은 "수동 확인 전용 진단"으로 분리해 화면 우선순위를 다르게 정의

## 5. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **프론트 무관 Spec-First + 현재 Streamlit inventory 반영 + 구현은 23(Next.js 점진 이관)에서 수행**

- 고려 대안:
  1) 기존 페이지별 개별 수정(빠른 패치)
  2) Streamlit 유지 + 공통 데이터 계층/컴포넌트 정리(채택)
  3) 프레임워크 교체(React/Next 등)

- 대안 비교:
  1) Streamlit 직접 리팩터:
    - 장점: 단기 체감 개선
    - 단점: 23 이관 시 중복 작업 가능성 큼
  2) Spec-First(채택):
    - 장점: 23에서 재사용 가능, 중복 최소화, monitoring-only 상태인 상위 운영 작업과 독립적으로 진행 가능
    - 단점: 즉시 UI 변화는 제한적
  3) Next.js 즉시 구현:
    - 장점: 빠른 전환
    - 단점: 운영 기준 미고정 상태로 재작업 위험 증가

## 5.1 현재 선택의 구체적 근거
1. `21-03`, `28`은 이번 세션에서 구현 대상이 아니라 관측 대상이므로, `22`가 이들과 경쟁하지 않고 병렬로 진전될 수 있다.
2. `21-04`가 blocked 상태라 비용/usage freshness를 대시보드 정식 데이터 계약으로 고정하기 어렵기 때문에, `22`는 "현재 운영 가능 범위"와 "blocked 해제 후 확장 범위"를 분리 정의해야 한다.
3. `23`은 `22` 승인 산출물을 선행 게이트로 요구하고 있으므로, 지금 가장 가치가 큰 작업은 UI 코드 수정이 아니라 acceptance source of truth 확정이다.

## 6. 구현/수정 내용 (예정)
- 변경 파일(예상, 문서 중심):
  1) `docs/work-plans/22_dashboard_readability_and_live_data_reliability_plan.md` (본 문서)
  2) `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md` (수용 기준 연계 필요 시)
  3) `docs/checklists/remaining_work_master_checklist.md` (상태/완료조건 동기화)
  4) `docs/work-result/22_dashboard_readability_and_live_data_reliability_result.md` (spec 산출물 결과)

- 작업 스트림:
  - Stream A: 현재 Streamlit inventory 작성(`src/dashboard/app.py`, `src/dashboard/pages/*.py`, `src/dashboard/components/autorefresh.py`, `src/dashboard/utils/db_connector.py`)
  - Stream B: 정보 구조 우선순위 표준(카드/탭/경고) 정의
  - Stream C: 탭별 freshness 계약(갱신 시각/age/오류/재조회) 정의
  - Stream D: stale 상태 정의(임계치, 경고 레벨, 사용자 액션) 정의
  - Stream E: 23에서 검증 가능한 acceptance checklist 생성

### 6.1 Spec 산출물 정의(필수)
1. 정보 우선순위 매트릭스
   - 화면별 핵심 지표(Primary), 보조 지표(Secondary), 진단 지표(Diagnostic) 분류
   - 허용 시각 강조 규칙(색상/배지/경고 문구) 표준화
2. Freshness 계약서
   - 데이터셋별 `last_updated_at`, `data_age_sec`, `stale_threshold_sec` 정의
   - 정상/지연/실패 상태 전이 규칙 정의
3. Stale UX 상태표
   - 경고 레벨(Info/Warning/Critical) 기준
   - 사용자 액션(자동 재조회/수동 재조회/읽기 전용 fallback) 규칙
4. API/조회 계약 체크리스트
   - 23에서 화면 이관 시 동일 의미값을 보장해야 하는 필드 목록
   - 동등성 판정 기준(필수 필드 누락 0건, 시간 지연 기준 충족) 명시

### 6.2 이번 승인 범위에서 바로 만들 산출물
1. 화면별 정보 우선순위 표
   - Landing / Overview / Market / Risk / History / System / Chatbot / Exit Analysis 기준
2. 데이터셋별 freshness 계약 표
   - DB 조회, Redis bot status, 운영 수동 검증 데이터(예: `21-10`)를 분리
3. stale UX 상태표
   - `fresh / delayed / stale / failed / manual-only` 5상태 정의
4. 23 수용 기준 체크리스트
   - Next.js 이관 시 페이지별 PASS/FAIL 판정 항목
5. 미연결/추후 확장 목록
   - `21-04 blocked` 해제 후 비용/토큰 freshness를 어떻게 편입할지 별도 backlog로 표기

## 7. 검증 기준
- 재현 케이스에서 해결 확인:
  1) 22 산출물(spec/checklist)을 기준으로 23 구현 결과 pass/fail 판정 가능
  2) 탭별 stale 기준과 freshness 표기 규칙이 모호하지 않게 문서화됨
  3) 현재 Streamlit 페이지별 가독성/실시간성 차이가 inventory로 남아, 어떤 항목이 23에서 반드시 유지/개선돼야 하는지 추적 가능
- 회귀 테스트:
  - (본 단계는 문서 작업) 기존 서비스 동작 영향 없음
- 운영 체크:
  - 운영자/개발자 공통으로 이해 가능한 용어/기준으로 정리됨
  - monitoring-only 지표와 수동 검증 지표가 같은 실시간 카드로 혼재되지 않도록 우선순위 원칙이 정의됨

## 8. 롤백
- 코드 롤백:
  - 문서 변경 revert
- 운영 롤백:
  - 해당 없음
- 데이터/스키마 롤백:
  - 없음(조회 경로 개선 중심)

## 9. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서 + 구현 후 결과 문서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 대시보드 운영 정책(가독성/신선도 표준)을 “운영 규칙”으로 확정 시 Charter changelog 반영

## 10. 후속 조치
1. 23 구현 계획에 22 acceptance checklist를 gate로 반영  
2. 23-01(레포 분리 시점/절차) 계획과 연동해 분리 타이밍 고정  
3. 23 결과에서 22 기준 충족 여부를 정량으로 검증

## 11. 계획 변경 이력
- 2026-03-05: 22를 Streamlit 코드 리팩터 중심에서 Spec-First(프론트 무관 표준 정의) 중심으로 재정의. 23(Next.js)와 중복 구현을 줄이기 위해 요구사항/수용 기준을 먼저 확정하는 방향으로 변경.
- 2026-03-05: Spec 산출물을 4개(정보 우선순위 매트릭스, Freshness 계약서, Stale UX 상태표, API/조회 계약 체크리스트)로 고정해 23 수용 기준의 모호성을 제거.
- 2026-03-12: 현재 운영 상태(`21-03/28 monitoring-only`, `21-04 blocked`, `21-10 manual verification`)를 반영해 `22`를 "즉시 코드 변경"이 아닌 "Spec/Acceptance 확정 작업"으로 다시 명시했다.
- 2026-03-12: 현재 Streamlit 구현의 실제 관측 포인트(`cache ttl=30s`, `auto-refresh 10~300s`, `Market 페이지 bot status stale=120s`, 다른 페이지의 freshness 부재)를 계획서 입력으로 고정했다.
- 2026-03-12: 사용자 승인 후 범위를 문서 산출물 4종 확정 + `23`/체크리스트/README/Charter 동기화로 확정했다. Streamlit/Next.js 코드 변경은 이번 plan 범위에서 제외한다.
