# 18-01 Compose System Health / 스키마 정합성 복구 계획

작성일: 2026-02-23  
작성자: Codex (GPT-5)  
상태: Completed (2026-02-23)  
상위 에픽: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`  
관련 트러블슈팅: `docs/troubleshooting/18-01_system_health_agent_decisions_and_data_sync.md`

---

## 0. 배경
- Compose 전환 직후 System 페이지에서 `agent_decisions` 테이블 미존재 오류가 발생했다.
- Overview 페이지에서 보유 종목/수익률이 사라진 것처럼 보인다.

## 1. 문제 정의
1. `agent_decisions` 테이블 누락으로 System 페이지 SQL이 실패한다.
2. n8n 상태 점검 로직이 Compose 기본 네트워크(`n8n`)를 쓰지 않고 `localhost`로 검사해 오탐(`Error`)이 발생한다.
3. 운영 DB의 `positions/trading_history` 데이터가 0건으로, Overview가 정상적으로 "없음" 상태를 표시한다.

## 2. 목표 / 비목표
### 2.1 목표
1. System 페이지에서 DB 오류 없이 최근 의사결정 목록이 표시되도록 복구한다.
2. n8n 헬스체크를 Compose 환경에 맞게 안정화한다.
3. Overview 데이터 공백 원인이 "데이터 유실"이 아닌 "현재 DB에 데이터 없음"임을 검증 가능하게 정리한다.

### 2.2 비목표
1. 과거 Minikube 데이터 자동 복원까지는 이번 작업 범위에 포함하지 않는다.
2. 전체 마이그레이션 프레임워크(Alembic 등) 재구축은 이번 작업 범위에서 제외한다.

## 3. 설계 선택 및 대안
### 3.1 선택
- 누락 스키마를 SQL로 즉시 보정하고, Compose 헬스체크 환경변수/코드를 정합성 있게 맞춘다.

### 3.2 대안
1. 대시보드에서 테이블 오류만 try/except로 숨긴다.
2. DB를 새로 초기화한다.
3. 누락 테이블 생성 + 환경변수 정합화 + 운영 문서 반영(채택).

### 3.3 채택 근거
- 1번은 근본 원인(스키마 누락)을 숨겨 재발 위험이 크다.
- 2번은 데이터 복구 관점에서 위험하고 불필요하게 파괴적이다.
- 3번이 최소 변경으로 장애 원인을 제거하고 재현 가능 운영 절차를 남긴다.

## 4. 작업 항목
1. 운영 DB에 `agent_decisions` 기준 스키마를 생성하고 인덱스를 반영한다.
2. Compose dashboard의 n8n 헬스체크 경로를 `localhost` 의존 없이 동작하게 수정한다.
3. Dashboard System 페이지의 n8n 체크 로직을 Compose/K8s 양쪽에서 오작동 없도록 보강한다.
4. 검증 명령(`psql`, `docker logs`, `redis-cli`, `preflight`)을 실행해 증적을 확보한다.
5. 결과/트러블슈팅 문서에 원인-조치-검증을 기록한다.

## 5. 검증 기준
1. `to_regclass('public.agent_decisions')`가 null이 아니어야 한다.
2. `System Health`에서 n8n이 `Active`로 표시되어야 한다.
3. System 페이지에서 `relation "agent_decisions" does not exist` 오류가 사라져야 한다.
4. `positions/trading_history` 건수를 SQL로 조회해 현재 데이터 상태를 명시적으로 확인해야 한다.

## 6. 계획 변경 이력
- 2026-02-23: 초안 작성.
- 2026-02-23: 구현 완료. 관련 결과/트러블슈팅 문서 연결.
  - `docs/work-result/18-01_compose_system_health_schema_alignment_result.md`
  - `docs/troubleshooting/18-01_system_health_agent_decisions_and_data_sync.md`
- 2026-02-23: 트러블슈팅 문서에 Minikube -> Compose 전환 배경/비교/트레이드오프 상세 설명 추가.
- 2026-02-23: 운영 문서 동기화 범위 추가 (`daily-startup-guide`, `USER_MANUAL`, `Data_Flow`, `DEEP_LEARNING_GUIDE`).
