# 23. Next.js 기반 대시보드 점진 이관 결과

작성일: 2026-03-15
작성자: Codex
관련 계획서: `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`
상태: Partial
완료 범위: Phase 1 초기 골격 + Overview/System read-only MVP
선반영/추가 구현: 있음(초기 MVP)
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - `frontend/next-dashboard/` 초기 골격 생성
  - Next.js App Router 기반 Overview/System read-only MVP 추가
  - 기존 bot/mobile API를 재사용하는 서버 fetch 계층 구성
  - `deploy/docker/dashboard-next.Dockerfile` 추가
- 목표(요약):
  - 운영 전환 이전에, `22` spec을 수용하는 제품형 프론트 구조를 먼저 확보한다.
- 이번 구현이 해결한 문제(한 줄):
  - Streamlit만 존재하던 상태에서 Next.js 기반 read-only 대시보드의 실제 시작점을 만들었다.

## 2. 구현 내용
### 2.1 Next.js 모노레포 골격
- 파일/모듈:
  - `frontend/next-dashboard/package.json`
  - `frontend/next-dashboard/next.config.mjs`
  - `frontend/next-dashboard/jsconfig.json`
- 변경 내용:
  - App Router 기준의 최소 앱 구조와 npm 스크립트를 추가했다.
  - alias(`@/*`)와 standalone 빌드 출력을 설정했다.

### 2.2 기존 운영 API 재사용 계층
- 파일/모듈:
  - `frontend/next-dashboard/lib/bot-api.js`
- 변경 내용:
  - `BOT_API_BASE_URL`, `COINPILOT_API_SHARED_SECRET`를 이용해 기존 `/api/mobile/*`를 읽는 서버 fetch 계층을 추가했다.
  - Overview/System 데이터 스냅샷을 조합하고, freshness 상태(`fresh/delayed/stale/failed`)를 계산하도록 했다.
- 의미:
  - `23` Phase 1이 백엔드 스키마를 다시 정의하지 않고도 기존 운영 조회 경로를 재사용할 수 있게 됐다.

### 2.3 Overview / System read-only MVP
- 파일/모듈:
  - `frontend/next-dashboard/app/page.js`
  - `frontend/next-dashboard/app/system/page.js`
  - `frontend/next-dashboard/components/*`
  - `frontend/next-dashboard/app/globals.css`
- 변경 내용:
  - Overview:
    - 총 평가액, 현금, 당일 손익, 거래 수, 리스크 레벨, 보유 포지션 테이블
  - System:
    - overall/component 상태, risk flags
  - `22` spec에 맞춰 freshness badge, Diagnostic 구역 구분, explanatory fallback 문구를 넣었다.
- 의미:
  - 초기부터 “예쁜 껍데기”가 아니라 운영 정보 계층과 freshness 규약을 반영한 프론트 구조로 시작했다.

### 2.4 배포 준비
- 파일/모듈:
  - `deploy/docker/dashboard-next.Dockerfile`
- 변경 내용:
  - standalone Next.js 빌드를 가정한 멀티스테이지 Dockerfile을 추가했다.

## 3. 변경 파일 목록
### 3.1 신규
1) `frontend/next-dashboard/package.json`
2) `frontend/next-dashboard/next.config.mjs`
3) `frontend/next-dashboard/jsconfig.json`
4) `frontend/next-dashboard/lib/bot-api.js`
5) `frontend/next-dashboard/components/status-pill.js`
6) `frontend/next-dashboard/components/metric-card.js`
7) `frontend/next-dashboard/components/section-frame.js`
8) `frontend/next-dashboard/app/layout.js`
9) `frontend/next-dashboard/app/page.js`
10) `frontend/next-dashboard/app/system/page.js`
11) `frontend/next-dashboard/app/globals.css`
12) `deploy/docker/dashboard-next.Dockerfile`
13) `deploy/cloud/oci/docker-compose.prod.yml` (`next-dashboard` 서비스, 포트 `127.0.0.1:3001`)
14) `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md` (next-dashboard 원샷/포트 고정 가이드 보강)
15) `docs/portfolio/study/32_deployment_operations_monitoring_runbook.md` (`next-dashboard` 서비스/포트 반영)
16) `docs/work-result/23_nextjs_dashboard_gradual_migration_result.md`

### 3.2 수정
1) `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`
2) `docs/checklists/remaining_work_master_checklist.md`
3) `deploy/cloud/oci/docker-compose.prod.yml`

## 4. 검증 결과
### 4.1 정적 검증
- 확인 내용:
  - Next.js 앱 기본 파일 존재
  - Overview/System 페이지 존재
  - 기존 mobile API 재사용 경로 존재
- 결과:
  - 확인 완료

### 4.2 테스트 검증
- 자동 테스트:
  - 미실행
- 사유:
  - 현재 세션에서는 네트워크 제한으로 `create-next-app` 및 의존성 설치를 수행하지 못해 `npm install`/`next build` 검증은 아직 못 했다.
- 대체 검증:
  - 파일 구조, import 경로, read-only fetch 흐름, Dockerfile 경로 정합성 점검

## 5. 설계/아키텍처 결정 리뷰
- 최종 선택한 구조 요약:
  - 기존 bot/mobile 조회 API를 재사용하는 Next.js App Router 기반 read-only MVP
- 고려했던 대안:
  1) Streamlit 페이지를 먼저 더 리팩터링한다.
  2) Next.js 화면을 mock만으로 먼저 만든다.
  3) 기존 운영 API를 재사용하는 read-only MVP부터 시작한다. (채택)
- 대안 대비 이점:
  1) 기존 운영 데이터 계약을 바로 재활용할 수 있다.
  2) Phase 1에서 백엔드 로직 수정 없이 프론트 가치가 생긴다.
  3) `22` spec을 실제 화면 구조에 바로 반영할 수 있다.
- 트레이드오프:
  1) mobile API가 dashboard 전용이 아니라 일부 필드가 간접적이다.
  2) 이후 Phase 2에서 dashboard 전용 BFF 또는 API 정리가 필요할 수 있다.

## 6. 현재 상태와 다음 단계
- 현재 상태:
  - `23`은 이제 `blocked`가 아니라 Phase 1 기준 `in_progress`다.
  - Next.js 앱 골격과 read-only MVP는 시작됐다.
- 다음 단계:
  1) 의존성 설치 및 `npm run lint` / `npm run build` 검증
  2) compose에 `next-dashboard` 서비스 연결 및 원샷 재기동 검증
  3) Overview/System 수치와 Streamlit 화면 비교
  4) 이후 Market/Risk/History 탭 점진 이관

## 7. 23-1 운영 기동(OCI) 반영

- 적용 커맨드:
  - `docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml up -d --build --no-deps next-dashboard`
  - `docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml ps`
  - `docker logs --tail 80 coinpilot-dashboard-next`
  - `curl -I http://127.0.0.1:3001`

- 결과:
  - 포트 충돌 없이 `next-dashboard`는 `127.0.0.1:3001`에 바인딩.
  - 기존 `dashboard`(`127.0.0.1:8501`), `grafana`(`127.0.0.1:3000`), `n8n`(`127.0.0.1:5678`) 매핑은 유지.
  - 로그/헬스 응답에서 Next.js 기동 성공(메인 페이지 200/ready) 상태를 확인.
