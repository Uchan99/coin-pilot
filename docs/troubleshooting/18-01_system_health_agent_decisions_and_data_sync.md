# 18-01 트러블슈팅: System Health `agent_decisions` 오류 및 Compose 데이터 공백

작성일: 2026-02-23  
관련 계획: `docs/work-plans/18-01_compose_system_health_schema_alignment_plan.md`  
관련 결과: `docs/work-result/18-01_compose_system_health_schema_alignment_result.md`  
상위 계획: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`

---

## 1. 증상
1. System 페이지에서 아래 오류가 노출됨
- `relation "agent_decisions" does not exist`

2. System Health에서 n8n 상태가 `Error`로 표시됨

3. Overview에서 과거 지표(누적 손익/거래 이력)가 사라진 것처럼 보임

## 2. 원인
1. Compose DB 스키마 누락
- `deploy/db/init.sql`에 `agent_decisions` baseline 테이블 정의가 없어 신규 DB에서 조회 오류 발생

2. n8n 헬스체크 대상 기본값 불일치
- dashboard 코드가 `localhost:5678` 기본값을 우선 사용해 Compose 네트워크(`n8n`)를 보지 못하는 경우 발생

3. 데이터 원본 분리
- 기존 거래 데이터는 Minikube DB(`coin-pilot-ns/db-0`)에 존재
- Compose DB는 신규 생성되어 데이터가 비어 있었음

## 2.1 Minikube -> Docker Compose 전환 배경/이유
이번 이슈의 직접 원인은 스키마/데이터 정합성이었지만, 근본적으로 운영 방식이 Minikube에서 Compose로 바뀌면서 관측/복구 방식이 달라진 영향이 있었다.

전환한 이유(의사결정 기준):
1. 비용/리소스 효율
- 단일 VM 운영 기준에서 Minikube(K8s control plane + 부가 컴포넌트)보다 Compose가 메모리/CPU 오버헤드가 작다.
- 18번 목표가 "가성비 최적화 + 상시 운영"이라 오케스트레이션 복잡도보다 운영 안정성과 비용을 우선했다.

2. 운영 단순성
- Compose는 `docker compose ps/logs/up -d --build` 중심으로 일일 운영 루틴이 단순하다.
- Minikube는 `kubectl rollout`, `port-forward`, 서비스/네임스페이스 상태 확인이 필요해 초반 운영 난도가 높았다.

3. 현재 단계 요구사항 적합성
- 현재 프로젝트는 단일 노드 운영으로도 요구사항 충족이 가능하다.
- 고급 K8s 기능(오토스케일/정교한 네트워크 정책/복수 노드 스케줄링)보다 빠른 복구성과 운영 단순성이 더 중요했다.

4. 기존 배포 자산 재사용
- `deploy/cloud/oci/docker-compose.prod.yml`과 runbook/preflight 체계를 중심으로 이미 운영 절차가 정비되어 있었다.

## 2.2 Minikube vs Compose 비교 (이번 전환 기준)
| 항목 | Minikube(K8s) | Docker Compose |
|---|---|---|
| 초기 설정 난이도 | 높음 (cluster/namespace/resource) | 낮음 (compose + env) |
| 일일 운영 명령 | `kubectl` 다수 | `docker compose` 중심 |
| 로컬 접근 방식 | `port-forward` 필요 사례 많음 | `ports` 바인딩으로 직접 접근 |
| 리소스 오버헤드 | 상대적으로 큼 | 상대적으로 작음 |
| 단일 노드 비용 효율 | 불리한 편 | 유리한 편 |
| 장애 원인 파악 속도 | 리소스 계층이 많아 느릴 수 있음 | 컨테이너/로그 중심으로 빠름 |
| 확장성/정책 정밀도 | 높음 | 중간 |

## 2.3 전환의 트레이드오프
1. 장점
- 운영 절차 단순화, 비용 절감, 장애 대응 속도 향상

2. 단점
- K8s-native 기능(고급 배포 전략/정교한 정책/확장성) 활용 폭이 줄어듦

3. 보완 방향
- 현재는 Compose 유지
- 트래픽/팀 규모/운영 요구가 커지면 Minikube가 아니라 관리형 K8s(OKE/EKS)로 상향 전환 검토

## 3. 진단 근거
1. Compose DB 상태
- `to_regclass('public.agent_decisions')`가 null
- `positions/trading_history` 건수 0

2. Minikube DB 상태
- `trading_history=16`, `agent_decisions=353`, `market_data=182341` (조회 시점)

3. n8n 헬스체크
- dashboard 컨테이너에서 `http://n8n:5678/healthz`는 200 정상

## 4. 조치
1. 스키마 보강
- 신규 마이그레이션 추가: `migrations/v3_3_1_agent_decisions_baseline.sql`
- `deploy/db/init.sql`에 `agent_decisions` baseline 및 인덱스 추가

2. dashboard n8n 체크 로직 보강
- `src/dashboard/pages/5_system.py`에서 후보 URL(`N8N_URL`, `N8N_SERVICE_HOST`, `n8n`, `localhost`) 순차 점검
- `agent_decisions` 테이블 존재 여부를 선확인 후 조회하도록 개선

3. Compose 환경변수 보강
- `deploy/cloud/oci/docker-compose.prod.yml` dashboard 환경에
  - `N8N_URL=http://n8n:5678`
  - `N8N_SERVICE_HOST=n8n`
  - `N8N_SERVICE_PORT=5678`

4. 데이터 복원
- K8s → Compose 전체 dump 복원은 Timescale internal schema 충돌로 실패
- 우회:
  1) 대상 DB 재생성
  2) `init.sql + migrations`로 스키마 생성
  3) K8s DB에서 `public` 앱 테이블 data-only 복원
  4) `market_data`는 CSV `\copy`로 별도 이관

## 5. 결과
- `agent_decisions` 테이블 조회 정상
- n8n 헬스체크 경로 정상화
- Compose DB에 과거 이력 데이터 복원
  - `trading_history=16`
  - `daily_risk_state=22`
  - `agent_decisions=353`
  - `market_data=182380` (복원 시점)

## 6. 재발 방지
1. 신규 환경 생성 시 `init.sql`만으로도 최신 baseline 스키마가 생성되도록 유지
2. 18번 runbook에 `init.sql + migrations + data restore` 순서 고정
3. 대시보드 health check는 배포 모드(Compose/K8s)와 무관하게 다중 후보 점검 유지
