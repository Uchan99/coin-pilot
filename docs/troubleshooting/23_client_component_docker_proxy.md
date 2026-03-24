# 23. Client Component에서 Docker 내부 주소 직접 호출 불가 트러블슈팅

작성일: 2026-03-25
상태: Fixed
우선순위: P1
관련 문서:
- Plan: docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md
- Result: docs/work-result/23_nextjs_dashboard_gradual_migration_result.md
- Charter update 필요: NO

---

## 1. 트리거(왜 시작했나)
- 모니터링/로그/사용자 리포트로 관측된 내용:
  - Phase 3 실데이터 연동 후 OCI 배포 시, Market/History/Exit Analysis/Chatbot 페이지에서 데이터 조회 실패
  - 브라우저 콘솔에 `GET http://localhost:13001/api/exit-analysis/data?days=30&limit=800 404 (Not Found)` 에러 다수 발생
- 긴급도/영향:
  - Client Component 기반 4개 페이지가 모두 동작 불가 (P1)

---

## 2. 증상/영향
- 증상:
  - Market: Bot Brain "UNKNOWN", 캔들 차트 빈 화면
  - History: 거래 내역 없음 ("조회 실패" 메시지)
  - Exit Analysis: 데이터 없음
  - Chatbot: AI 응답 실패
  - 브라우저 Network 탭: `404 Not Found` (Next.js 서버에서 반환)
- 영향(리스크/데이터/비용/운영):
  - 기능: 8개 중 4개 페이지 완전 불능 (Server Component 기반 3개는 정상)
  - 리스크: 데이터 유실 없음 (읽기 전용)
  - 비용: 백엔드 API는 정상 → 프론트엔드 라우팅 문제로 한정
- 발생 조건/재현 조건:
  - Client Component(`"use client"`)에서 `fetch("http://bot:8000/api/mobile/...")` 호출 시 발생
  - Server Component에서 동일 URL 호출 시에는 정상 (Docker 네트워크 내부 통신)
- 기존 상태(Before) 기준선:
  - Phase 2에서는 Mock 데이터를 사용했으므로 문제 없었음

---

## 3. 재현/관측 정보
- 재현 절차:
  1. Client Component에서 직접 `BOT_API_BASE_URL`(`http://bot:8000`) 호출하는 코드 배포
  2. 브라우저에서 Market/History/Exit Analysis/Chatbot 탭 접근
  3. 브라우저 DevTools Network 탭에서 404 에러 확인
- 핵심 로그/에러 메시지:
  ```
  GET http://localhost:13001/api/exit-analysis/data?days=30&limit=800 404 (Not Found)
  GET http://localhost:13001/api/market/candles?symbol=KRW-BTC&interval=15m&limit=200 404 (Not Found)
  GET http://localhost:13001/api/market/brain?symbol=KRW-BTC 404 (Not Found)
  GET http://localhost:13001/api/history/trades?limit=50&offset=0 404 (Not Found)
  ```

---

## 4. 원인 분석
- 가설 목록:
  1) Client Component의 fetch가 브라우저에서 실행되어 Docker 내부 DNS(`bot`)를 resolve 불가
  2) Next.js 서버에서 API Route가 등록되지 않음
  3) 백엔드 API 엔드포인트가 존재하지 않음
- 조사 과정(무엇을 확인했는지):
  1. `docker exec coinpilot-bot curl http://bot:8000/api/mobile/candles` → 정상 200 응답 (백엔드 정상)
  2. Server Component 페이지(Overview/Risk/System) → 정상 표시 (서버→Docker 통신 정상)
  3. Client Component 페이지 → 브라우저에서 `bot:8000` 접근 시도 → DNS resolve 불가
- Root cause(결론):
  - **Next.js의 Server Component와 Client Component의 실행 위치 차이**
  - Server Component: Next.js 서버(Docker 컨테이너 내부)에서 실행 → `bot:8000` 접근 가능
  - Client Component: 브라우저(사용자 PC)에서 실행 → Docker 내부 DNS `bot`를 resolve 불가
  - `lib/bot-api.js`의 `fetchApiJson()`이 서버 전용이었는데, Client Component에서도 동일 함수를 사용하려 함

---

## 5. 해결 전략
- 단기 핫픽스:
  - N/A (근본 해결을 바로 적용)
- 근본 해결:
  - **Next.js API Route Handler를 프록시 계층으로 도입**
  - 브라우저 → Next.js 서버(`/api/*` Route Handler) → Docker 내부(`bot:8000`)
  - Client Component는 `/api/market/candles` 등 상대 경로만 호출
  - API Route Handler가 서버 사이드에서 `bot:8000`으로 프록시 전달
- 안전장치:
  - API Secret은 프록시 서버에서만 주입 (브라우저에 노출되지 않음)
  - 프록시에 10초 타임아웃 설정

---

## 6. 수정 내용
- 변경 요약:
  - `lib/api-proxy.js` 공통 프록시 함수 신규 작성
  - 5개 API Route Handler 신규 추가 (candles/brain/trades/exit-analysis/chatbot)
  - `lib/bot-api.js`에 `fetchClientJson()` 추가 — 브라우저에서 Next.js 프록시 호출용
  - Client Component 함수들(`getTrades`, `getCandles`, `getBotBrain`, `getExitAnalysis`, `askChatbot`)이 프록시 경로 사용하도록 변경
- 변경 파일:
  1. `frontend/next-dashboard/lib/api-proxy.js` (신규)
  2. `frontend/next-dashboard/app/api/market/candles/route.js` (신규)
  3. `frontend/next-dashboard/app/api/market/brain/route.js` (신규)
  4. `frontend/next-dashboard/app/api/history/trades/route.js` (신규)
  5. `frontend/next-dashboard/app/api/exit-analysis/data/route.js` (신규)
  6. `frontend/next-dashboard/app/api/chatbot/ask/route.js` (신규)
  7. `frontend/next-dashboard/lib/bot-api.js` (수정)
- DB/스키마 변경: 없음
- 롤백 방법:
  - 프록시 라우트 6개 파일 삭제 + `bot-api.js`에서 `fetchClientJson` → `fetchApiJson`으로 복구
  - 단, 롤백 시 Client Component 페이지는 다시 동작 불능

---

## 7. 검증
- 실행 명령/절차:
  ```bash
  # 백엔드 + 프론트엔드 재빌드/재배포
  docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml build --no-cache bot next-dashboard
  docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml up -d --force-recreate bot next-dashboard

  # 페이지별 확인
  curl -s http://127.0.0.1:3001/api/market/candles?symbol=KRW-BTC&interval=15m&limit=5
  curl -s http://127.0.0.1:3001/api/market/brain?symbol=KRW-BTC
  curl -s http://127.0.0.1:3001/api/history/trades?limit=5
  curl -s http://127.0.0.1:3001/api/exit-analysis/data?days=7&limit=10
  ```
- 결과:
  - 8/8 페이지 정상 데이터 표시 확인

- 운영 확인 체크:
  1) 브라우저 DevTools Network 탭에서 404 에러 0건
  2) 모든 Client Component 페이지 실데이터 표시 확인

### 7.1 정량 개선 증빙(필수)
- 측정 기간/표본: 2026-03-24 배포 직후 즉시 확인
- 측정 기준(성공/실패 정의): 각 페이지에서 실 데이터 표시 여부
- 데이터 출처: 브라우저 수동 확인 + curl 응답
- Before/After 비교표:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 정상 작동 Client Component 페이지 | 0/4 | 4/4 | +4 | +100% |
| 브라우저 404 에러 수 | 4+ (페이지 접근마다) | 0 | -4 | -100% |
| 프록시 라우트 수 | 0 | 5 | +5 | N/A |
| API Secret 브라우저 노출 | 가능성 있었음 | 서버에서만 주입 | - | 보안 개선 |

---

## 8. 재발 방지
- 가드레일:
  - `lib/bot-api.js`에서 서버 전용(`fetchApiJson`)과 클라이언트 전용(`fetchClientJson`)을 명확히 분리
  - Client Component 함수는 항상 상대 경로(`/api/*`)만 사용하도록 코드 컨벤션 확립
  - 향후 Client Component에서 새 백엔드 API 호출 시 반드시 API Route Handler 프록시를 함께 추가
- 문서 반영:
  - plan/result 업데이트 여부: YES — Phase 3 변경이력 및 결과 Section 10에 프록시 구조 문서화
  - troubleshooting 링크 추가 여부: YES — plan/result/checklist 모두에 본 문서 링크 추가
  - PROJECT_CHARTER.md 변경: 없음 (프론트엔드 내부 구조 변경, 아키텍처 정책 변경 아님)

---

## 9. References
- Next.js Route Handlers 공식 문서: https://nextjs.org/docs/app/building-your-application/routing/route-handlers
- Next.js Server vs Client Component 렌더링 모델

## 10. 배운점
- **Server Component와 Client Component의 실행 환경 차이**는 Docker 기반 마이크로서비스 아키텍처에서 반드시 고려해야 할 핵심 설계 요소다. Server Component는 컨테이너 내부 네트워크에서, Client Component는 사용자 브라우저에서 실행된다는 점이 API 호출 경로 설계를 근본적으로 바꾼다.
- **Next.js API Route Handler를 BFF(Backend for Frontend) 프록시로 활용**하는 패턴은 Docker 환경에서 Client Component의 네트워크 접근 제한을 우아하게 해결하면서, 동시에 API Secret 등 민감 정보를 서버에서만 관리할 수 있어 보안적으로도 이점이 있다.
- 포트폴리오 관점에서 이 트러블슈팅은 **SSR/CSR 하이브리드 렌더링 + 컨테이너 네트워크 분리 환경에서의 실전 문제 해결 경험**을 보여줄 수 있다. 특히 "왜 Server Component는 되고 Client Component는 안 되는가"를 정확히 진단한 과정을 강조하면 좋다.
- Next.js의 프록시 패턴을 통해 **인프라 아키텍처(Docker 네트워크)와 프론트엔드 아키텍처(SSR/CSR)의 교차점**에서 발생하는 문제를 해결하는 역량이 향상되었다.
