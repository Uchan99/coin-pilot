# 23. Next.js 기반 대시보드 점진 이관(React 포트폴리오 강화) 계획

**작성일**: 2026-02-27  
**작성자**: Codex  
**상태**: Approval Pending  
**관련 계획 문서**: `docs/work-plans/22_dashboard_readability_and_live_data_reliability_plan.md`, `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md`, `docs/work-plans/23-01_frontend_backend_repository_split_timing_plan.md`  
**승인 정보**: 승인자 / 승인 시각 / 승인 코멘트

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 기존 Streamlit 대시보드는 빠른 구현에는 유리하지만, UI 확장성/제품형 프론트엔드 포트폴리오 측면에서 한계가 있음.
- 왜 즉시 대응이 필요했는지:
  - 사용자가 React/Next.js 학습 및 포트폴리오 강화를 목표로 전환 가능성을 검토함.

## 1. 문제 요약
- 증상:
  - 프론트엔드 기술 스택이 Streamlit 중심이라 제품형 FE 역량(React/Next) 증명이 약함.
  - 대시보드의 정보 구조/상태관리 고도화 요구가 증가할 가능성이 큼.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 대시보드 프론트 전면 재구성 필요 가능성
  - 리스크: 전면 교체 시 운영 중단/회귀 위험
  - 데이터: 기존 API/DB 질의 경로를 안정적으로 재사용해야 함
  - 비용: 신규 프론트 빌드/운영 비용 증가 가능
  - 조직/레포: 프론트/백엔드 분리 시 배포/버전 동기화 비용 증가 가능
- 재현 조건:
  - 포트폴리오/제품화 요구가 커지고 UI 복잡도가 증가할 때

## 2. 목표 / 비목표
### 2.1 목표
1. Next.js 기반 대시보드로 점진 이관 가능한 기술/운영 경로 확정
2. 기존 Streamlit과 병행 운영 가능한 무중단 마이그레이션 설계
3. 현재 OCI 인스턴스 자원 내에서 안전하게 운영 가능 여부를 사전 검증

### 2.2 비목표
1. 본 계획 단계에서 즉시 전면 교체 수행하지 않음
2. 백엔드 도메인 로직(매매/리스크) 변경은 범위 밖
3. 디자인 리브랜딩 전체 개편은 범위 밖

## 3. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **Next.js 점진 이관 + Streamlit 병행 운영 + 초기 모노레포 유지**

- 고려 대안:
  1) Streamlit 유지 + 부분 개선만 수행
  2) Next.js 전면 교체(빅뱅)
  3) Next.js 점진 이관(모노레포 시작 후 분리) (채택)

- 대안 비교:
  1) 유지:
    - 장점: 리스크 낮음
    - 단점: 포트폴리오/확장성 측면 한계 지속
  2) 빅뱅:
    - 장점: 단기 완료 시 구조 단순
    - 단점: 회귀/중단 리스크 높음
  3) 점진 이관(채택):
    - 장점: 운영 안정성 유지 + 학습/포트폴리오 효과 확보 + API 계약 안정화 전 중복 관리 최소화
    - 단점: 일정 기간 이중 운영 복잡도 발생, 분리 시점 판단 필요

## 3.1 AI/Backend 경계 원칙
- 원칙:
  1) 프론트(Next.js)는 읽기/조회 중심 BFF 또는 기존 API를 소비한다.
  2) 백엔드 도메인(매매/리스크/주문)은 기존 서비스가 소유한다.
  3) AI 기능(Analyst/Guardian/LLM usage)은 백엔드 내부 책임으로 유지한다.
- 의미:
  - 프론트 이관(23)과 AI 로직 변경(21-03/21-04/28)을 분리해 리스크를 낮춘다.

## 3.2 23 착수 선행 과업(이관보다 우선)
1. 21-03 카나리 관측 마감
   - 기준: 최근 24h 기준 표본 30건 이상에서 primary/canary 분포 및 오류율 보고 가능
   - 검증: `scripts/ops/ai_decision_canary_report.sh 24`
2. 21-04 관측성 안정화(현상 유지 모드 포함)
   - 기준: usage 집계 정상 + 오류 이벤트 24h 0건
   - 검증: `scripts/ops/llm_usage_cost_report.sh 24` + `SELECT ... FROM llm_usage_events WHERE status='error' ...`
3. 28 전략문서/과거사례 RAG 보강 설계 승인
   - 기준: 실험 범위/측정 지표/중단 조건 정의 완료
4. 22 spec 산출물 확정
   - 기준: 6.1의 4개 산출물 승인 완료
5. 29 전략 평가/핫픽스 의사결정 완료
   - 기준: 레짐 전환 백테스트 결과 및 핫픽스 적용/보류 결론 문서화 완료

## 4. OCI 용량/운영 가능성 검토(사전 판단)
- 현재 관측값(사용자 제공):
  - 메모리 여유 약 10Gi
  - load average 매우 낮음
  - 디스크 여유 약 23Gi
- 판단:
  - Next.js 서비스 1개(런타임 수백 MB 수준) 추가는 현재 자원에서 감당 가능
  - 단, 빌드 시 일시 메모리 증가가 있으므로 CI 빌드 산출물 또는 단계적 배포 전략 고려

## 5. 단계별 실행 계획 (예정)
### Phase 0: 선행 과업 완료(비이관 트랙)
1. 21-03/21-04/28/22/29 선행 기준 충족 여부 점검
2. 미충족 항목은 23 착수 보류(`blocked`) 유지

### Phase 1: 기반 구축 (Read-only MVP)
1. Next.js 앱 골격 생성(App Router 기준)
2. 인증/접근 정책(기존 대시보드와 동일 레벨) 정렬
3. Overview/Health 읽기 전용 페이지 우선 이관
4. 22번 spec(가독성/freshness/stale 규약) 수용 기준 반영

### Phase 2: 핵심 탭 점진 이관
1. Market/Risk/History 탭 이관
2. freshness(마지막 갱신 시각/지연 경고) 공통 컴포넌트 적용
3. 기존 Streamlit 탭과 병행 비교 운영

### Phase 3: 운영 전환
1. 사용자/운영 체크리스트 통과 후 기본 엔트리포인트 전환
2. Streamlit 은퇴 또는 최소 관리 모드 전환

### Phase 4: 레포지토리 분리(조건부)
1. 전제조건:
   - Next.js 핵심 탭 이관 완료(Overview/Market/Risk/History)
   - API 계약 2주 이상 무중단
   - 병행 운영 중 P1 이슈 0건
2. 수행:
   - FE 코드를 별도 repository로 분리
   - 배포는 이미지 태그 기반으로 코어 레포 Compose에서 참조
3. 추적:
   - 세부 절차는 `docs/work-plans/23-01_frontend_backend_repository_split_timing_plan.md`에서 관리

## 6. 구현/수정 내용 (예정)
- 신규(예상):
  1) `frontend/next-dashboard/` (Next.js 앱, 초기 모노레포)
  2) `deploy/docker/dashboard-next.Dockerfile`
  3) `deploy/cloud/oci/docker-compose.prod.yml` (next-dashboard 서비스 추가)
  4) `docs/work-result/23_nextjs_dashboard_gradual_migration_result.md`

- 수정(예상):
  1) `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md` (접속/운영 절차 추가)
  2) 기존 dashboard 라우팅/접속 포트 정책 문서

## 7. 검증 기준
- 재현 케이스에서 해결 확인:
  1) Next.js 대시보드가 기존 핵심 지표(overview/health)를 정확히 표시
  2) Streamlit과 동일 시점 비교 시 주요 수치 편차 허용 범위 내
- 회귀 테스트:
  - 기존 Streamlit 서비스 정상 유지(병행 기간)
- 운영 체크:
  - 컨테이너 자원 사용량/응답 지연/에러율 기준 충족

## 8. 롤백
- 코드 롤백:
  - Next.js 서비스 관련 커밋 revert
- 운영 롤백:
  - compose에서 next-dashboard 비활성화, Streamlit 단독으로 즉시 복귀
- 데이터/스키마 롤백:
  - 없음(조회 중심)

## 9. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서 작성
  - 구현 후 `docs/work-result/23_nextjs_dashboard_gradual_migration_result.md` 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 대시보드 아키텍처 공식 변경 시 Charter changelog 반영

## 10. 후속 조치
1. React/Next 학습 체크리스트(라우팅/상태관리/데이터패칭) 문서화  
2. 포트폴리오용 아키텍처 다이어그램(기존/전환 후) 작성  
3. 성능 기준(Web Vitals + API latency) 수립

## 11. 계획 변경 이력
- 2026-03-05: 22번을 spec-first로 재정의한 결정을 반영해, 23번의 수용 기준을 22 spec 기반으로 고정.
- 2026-03-05: 프론트 분리는 즉시 분리가 아니라 “모노레포 시작 → 안정화 후 분리(Phase 4)” 전략으로 변경.
- 2026-03-05: AI 기능과 Backend 도메인 책임 경계를 명시해 프론트 이관과 AI 로직 변경 트랙을 분리.
- 2026-03-05: 23 착수 선행 과업(21-03/21-04/28/22/29)을 명시하고, 선행 기준 미충족 시 23 상태를 `blocked`로 유지하는 게이트를 추가.
