# 18-01 Compose System Health / 스키마 정합성 복구 결과

작성일: 2026-02-23  
작성자: Codex (GPT-5)  
관련 계획: `docs/work-plans/18-01_compose_system_health_schema_alignment_plan.md`  
관련 트러블슈팅: `docs/troubleshooting/18-01_system_health_agent_decisions_and_data_sync.md`  
상태: Implemented

---

## 1. 개요
- 목표:
  1) System 페이지 `agent_decisions` 오류 제거
  2) n8n 상태 오탐 제거
  3) Compose DB 데이터 공백 복구

## 2. 구현 내용
### 2.1 스키마 baseline 보강
- 수정: `deploy/db/init.sql`
  - `agent_decisions` 테이블/인덱스 baseline 추가
- 신규: `migrations/v3_3_1_agent_decisions_baseline.sql`
  - 운영 DB 누락 시 즉시 적용 가능한 보정 마이그레이션 추가

### 2.2 System 페이지 로직 보강
- 수정: `src/dashboard/pages/5_system.py`
  - n8n health URL 후보 순차 점검(`N8N_URL`, `N8N_SERVICE_HOST`, `n8n`, `localhost`)
  - `agent_decisions` 테이블 존재 확인 후 조회
  - 테이블 부재 시 DB 에러 대신 안내 메시지 표시

### 2.3 Compose 환경변수 보강
- 수정: `deploy/cloud/oci/docker-compose.prod.yml`
  - dashboard에 `N8N_URL`, `N8N_SERVICE_HOST`, `N8N_SERVICE_PORT` 추가

### 2.4 데이터 복원
- K8s 원본 DB(`coin-pilot-ns/db-0`)에서 Compose DB로 데이터 이관
- 전체 dump 복원 실패(Timescale internal schema 충돌) 후, 아래로 우회:
  1) 대상 DB 재생성
  2) `init.sql + migrations` 적용
  3) public 앱 테이블 data-only 복원
  4) `market_data`는 CSV `\copy`로 별도 이관

## 3. 검증
### 3.1 서비스 상태
```bash
docker compose -f deploy/cloud/oci/docker-compose.prod.yml ps
```
- 결과: core + n8n + prometheus + grafana 전부 `Up`

### 3.2 스키마/데이터 확인
```sql
SELECT to_regclass('public.agent_decisions');
SELECT COUNT(*) FROM trading_history;
SELECT COUNT(*) FROM daily_risk_state;
SELECT COUNT(*) FROM agent_decisions;
SELECT COUNT(*) FROM market_data;
```
- 결과(복구 시점):
  - `trading_history=16`
  - `daily_risk_state=22`
  - `agent_decisions=353`
  - `market_data=182380`

### 3.3 보안 사전점검
```bash
./scripts/security/preflight_security_check.sh
```
- 결과: `PASSED`

## 4. 아키텍처 선택/대안/트레이드오프
### 4.1 선택
- 스키마 기준선 보강 + data-only/CSV 복구

### 4.2 대안
1. UI에서 오류만 숨기기
2. DB 완전 초기화 후 무데이터 운영
3. baseline 보강 + 원본 데이터 복구(채택)

### 4.3 선택 근거
- 1번은 근본 원인 미해결
- 2번은 운영 연속성 손실
- 3번은 원인 제거와 데이터 연속성을 동시에 확보

### 4.4 트레이드오프
- 복구 절차가 다단계라 운영 난도가 높음
- 완화: 트러블슈팅 문서에 복구 순서를 기록하고 재현 명령을 남김

## 5. 후속 작업
1. `docs/runbooks/18_data_migration_runbook.md`에 Timescale data-only/CSV 복구 절차를 표준 경로로 반영
2. 배포 직후 `migrations/*.sql` 적용 자동화 스크립트 정비

---

## Phase 2 (2026-02-23): 운영 문서 동기화

### 1) 목적
- Minikube 중심으로 작성된 운영 문서를 Compose 기본 운영 기준과 일치시켜 혼선을 제거

### 2) 반영 문서
1. `docs/daily-startup-guide.md`
2. `docs/USER_MANUAL.md`
3. `docs/Data_Flow.md`
4. `docs/DEEP_LEARNING_GUIDE.md`
5. `docs/PROJECT_CHARTER.md`

### 3) 핵심 반영 내용
1. Compose를 기본 운영 모드로 명시
2. Minikube는 레거시/검증 모드로 위치 조정
3. 보안 점검(`preflight_security_check.sh`)을 운영 루틴에 명시
4. Minikube -> Compose 전환 배경/비교/트레이드오프 참조 링크 연결

### 4) 검증
```bash
rg -n "Compose|Minikube|preflight_security_check|운영 모드 업데이트" \
  docs/daily-startup-guide.md docs/USER_MANUAL.md docs/Data_Flow.md docs/DEEP_LEARNING_GUIDE.md docs/PROJECT_CHARTER.md
```
- 결과: 대상 문서에 운영 모드/보안 점검/전환 근거가 일관되게 반영됨
