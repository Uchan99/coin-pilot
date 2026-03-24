# 23. Next.js 기반 대시보드 점진 이관 결과

작성일: 2026-03-15
작성자: Codex
관련 계획서: `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`
상태: Phase 2 구현 완료 (빌드 검증 통과, OCI 배포 대기)
완료 범위: Phase 1 read-only MVP + Phase 2 Stitch 디자인 전체 UI 재구축
선반영/추가 구현: 있음(초기 MVP + 데이터 계약 정합 + 보안 조치)
관련 트러블슈팅(있다면): 없음 (인증 헤더 불일치 / 데이터 계약 불일치는 구현 과정에서 즉시 해소)

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
  - Phase 1 read-only MVP **연동 완료** + OCI 운영 검증 통과.
  - Overview: 총 평가액(₩992,998), 현금, 당일 PnL, 거래 수, 리스크 레벨(SAFE) 정상 표시.
  - System: bot/db/redis/n8n 전체 UP, Overall UP, Risk Level SAFE 정상 표시.
  - Freshness: 두 페이지 모두 Fresh(0s) 정상 판정.
- 다음 단계:
  1) UI/UX 개선 (색상, 레이아웃, 차트 등 — 선택적)
  2) Market/Risk/History 탭 점진 이관 (Phase 2)
  3) Dashboard 전용 BFF 또는 API 정리 검토

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

## 8. Phase 1 데이터 연동 완료 (2026-03-18~19)

### 8.1 해결한 문제
1. **인증 헤더 불일치 (HTTP 401)**
   - Before: Next.js가 `x-coinpilot-api-shared-secret` 헤더로 전송, 백엔드는 `X-Api-Secret`만 수용
   - After: `lib/bot-api.js:4`를 `X-Api-Secret`으로 통일 → 401 해소
   - 커밋: `5441197`

2. **API 응답 구조 불일치 (값 전부 0)**
   - Before: 프론트엔드가 `positionsRes.positions`, `pnlRes.cash_krw` 등 최상위에서 직접 접근
   - After: `positionsRes.data.holdings`, `posData.cash_krw`, `pnlData.daily_total_pnl_krw` 등 `data` 래퍼 반영
   - 커밋: `90e85e8`, `435927f`

### 8.2 보안 강화 (2026-03-19)
1. **Dockerfile non-root 실행**: `app` 사용자(uid 1001) + `COPY --chown` + `USER app`
2. **보안 헤더 추가**: X-Frame-Options(DENY), X-Content-Type-Options(nosniff), Referrer-Policy, X-DNS-Prefetch-Control, Permissions-Policy
3. **헬스체크 에러 sanitize**: DB/Redis/n8n 실패 시 `str(exc)` → 일반 메시지 + 서버 로그에만 기록
- 커밋: `d57eabf`

### 8.3 코드 품질 개선 (2026-03-20)
1. `query_api.py`: 인라인 `import logging` 3개 → 모듈 레벨 `logger` 인스턴스로 통합
2. `bot-api.js`: `getSystemSnapshot()`의 변수 `d` → `statusData`로 명확화

### 8.4 OCI 운영 검증 결과

| 항목 | 검증 결과 |
|------|-----------|
| 내부 API 인증 | `docker exec coinpilot-dashboard-next node -e "fetch(...)"` → HTTP 200 |
| Overview 데이터 | Total Valuation ₩992,998 / Cash ₩992,998 / PnL -₩5,113 / Trades 2 / BUY 1 / Risk SAFE |
| System 데이터 | Overall UP / bot·db·redis·n8n 전부 UP / Risk SAFE |
| Freshness | 두 페이지 모두 Fresh (age 0s / threshold 60s) |
| 컨테이너 실행 사용자 | non-root (app, uid 1001) |
| 보안 헤더 | next.config.mjs headers() 5종 적용 |

### 8.5 보안 감사
- 전체 코드베이스 보안 감사 수행 (2026-03-18)
- 즉시 조치 3건 완료 (H-2 에러 sanitize, M-2 Dockerfile non-root, L-2 보안 헤더)
- 브랜치 전체 security review: **실제 악용 가능한 취약점 0건** (4건 후보 모두 false positive 판정)
- 상세: `docs/security/security_audit_2026-03-18.md` (gitignore 대상, 로컬 전용)

## 9. Phase 2: Stitch 디자인 기반 전체 UI 재구축 (2026-03-24)

### 9.1 개요
- Google Stitch로 생성한 8개 페이지 디자인(`stitch_frontend/`)을 Next.js App Router 컴포넌트로 변환
- 기존 Phase 1의 기본 CSS를 Tailwind CSS + Stitch "Deep Sea" 디자인 시스템으로 전면 교체
- 차트 라이브러리: Plotly React 채택 (Recharts는 캔들스틱/게이지/히트맵/박스플롯 미지원으로 탈락)

### 9.2 기술 스택 추가
| 패키지 | 버전 | 용도 |
|--------|------|------|
| tailwindcss | 3.x | Stitch 디자인 토큰 기반 유틸리티 스타일링 |
| postcss + autoprefixer | latest | Tailwind 빌드 파이프라인 |
| react-plotly.js + plotly.js | latest | 캔들스틱, 게이지, 히트맵, 박스플롯, 도넛, 라인 차트 |
| Material Symbols | CDN | 아이콘 (Google Fonts) |
| Inter | CDN | 폰트 (Google Fonts) |

### 9.3 구현된 페이지 (8개)

| 페이지 | 경로 | 렌더링 | 데이터 소스 | 주요 기능 |
|--------|------|--------|-------------|-----------|
| Control Center | `/` | Static | - | Hero + 6개 Quick Nav + Quick Start Guide + PnL 카드 |
| Overview | `/overview` | Server (SSR) | `getOverviewSnapshot()` | KPI 4카드 + 보유 포지션 테이블 + Freshness 배지 |
| Market | `/market` | Client | Mock (Phase 3에서 API 연동) | 심볼/인터벌 선택 + Bot Brain + Plotly 캔들스틱 |
| Risk Monitor | `/risk` | Server (SSR) | `getRiskSnapshot()` | Daily Loss 게이지 + Buy Count + 연패 + Trading Status |
| Trade History | `/history` | Client | Mock (Phase 3에서 API 연동) | 필터 + 거래 테이블 + Buy/Sell 도넛 + Status 바 |
| System Health | `/system` | Server (SSR) | `getSystemSnapshot()` | 3개 연결 카드 + AI Decisions + Risk Audit |
| AI Chatbot | `/chatbot` | Client | UI 프레임 (Phase 3 AI 연동) | 퀵 제안 4종 + 메시지 버블 + 입력 영역 |
| Exit Analysis | `/exit-analysis` | Client | Mock (Phase 3에서 API 연동) | KPI + 박스플롯 + 히트맵 + 튜닝 제안 |

### 9.4 공통 컴포넌트

| 컴포넌트 | 파일 | 설명 |
|----------|------|------|
| Sidebar | `components/sidebar.js` | 8개 내비게이션 + Auto-refresh + DB 상태 |
| Topbar | `components/topbar.js` | 현재 페이지 제목 + 알림/설정 아이콘 |
| FloatingChat | `components/floating-chat.js` | 전 페이지 우하단 플로팅 AI 채팅 |
| PlotlyChart | `components/plotly-chart.js` | Plotly 래퍼 (SSR 비활성 dynamic import) |

### 9.5 Stitch 디자인 호환 수정 사항
| Stitch 원본 | 프로젝트 호환 변경 |
|-------------|-------------------|
| USD 표기 ($) | KRW 표기 (원) + `formatKrw()` 포맷터 |
| BTCUSDT/ETHUSDT | KRW-BTC/KRW-ETH (업비트 심볼) |
| Launch Terminal / View API Docs 버튼 | 제거 (읽기 전용 원칙) |
| Emergency Stop 버튼 | 제거 (읽기 전용 원칙) |
| 바이낸스 API 안내 | Upbit API 연동 안내 |
| 외부 프로필 이미지 URL | Material Symbols person 아이콘 |

### 9.6 빌드 검증 결과

```
Route (app)                    Size  First Load JS
┌ ○ /                         162 B         106 kB
├ ○ /chatbot                1.78 kB         104 kB
├ ○ /exit-analysis          3.66 kB         106 kB
├ ○ /history                 3.2 kB         105 kB
├ ○ /market                 3.25 kB         105 kB
├ ƒ /overview                126 B          102 kB
├ ƒ /risk                    126 B          102 kB
└ ƒ /system                  126 B          102 kB

○ Static    ƒ Dynamic (server-rendered)
```
- `npm run build` 성공, 11개 라우트 전체 생성 확인
- Server Component(ƒ): overview, risk, system — 실제 API 데이터 사용
- Static(○): 나머지 — Mock/클라이언트 렌더링

### 9.7 정리 사항
- Phase 1 미사용 컴포넌트 3개 삭제: `metric-card.js`, `section-frame.js`, `status-pill.js`
- Phase 1 `globals.css`를 Tailwind 기반으로 전면 교체
- `lib/bot-api.js`에 `getRiskSnapshot()` 함수 추가

### 9.8 다음 단계 (Phase 3 범위)
1. Market/History/Exit Analysis 페이지의 Mock 데이터 → 실제 API 연동
2. AI Chatbot 백엔드 연동 (`process_chat_sync`)
3. OCI 배포 및 운영 검증
4. 기존 Streamlit 대시보드와 병행 비교 운영
