# 18-03. Dashboard DB 커넥션 풀 복원력 강화 작업 계획

**작성일**: 2026-02-23  
**작성자**: Codex (GPT-5)  
**상태**: Verified  
**관련 계획 문서**: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`  

---

## 0. 트리거(Why started)
- 운영 중 System Health에서 `server closed the connection unexpectedly` 오류가 간헐적으로 노출됨.
- DB 컨테이너 재기동 직후 대시보드가 stale connection을 재사용하는 상황이 관측됨.

## 1. 문제 요약
- 증상:
  - Dashboard DB check query(`SELECT 1`)에서 `OperationalError` 발생
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: System Health의 DB 상태가 순간적으로 Error로 보임
  - 리스크: 사용자 오판/운영 신뢰도 저하
- 재현 조건:
  - DB 컨테이너 재기동/재생성 직후 기존 connection pool 재사용 구간

## 2. 원인 분석
- 가설:
  1) SQLAlchemy sync engine pool이 죽은 커넥션을 재사용
  2) DB 재기동 시 TCP 세션이 끊겼는데 앱 레벨 선검증이 없음
- 조사 과정:
  - 대시보드 DB 유틸(`src/dashboard/utils/db_connector.py`)의 `create_engine` 설정 확인
- Root cause:
  - `pool_pre_ping` 미설정으로 stale socket을 즉시 재연결하지 못하는 창이 존재

## 3. 대응 전략
- 단기 핫픽스:
  - `pool_pre_ping=True` 적용
- 근본 해결:
  - idle 커넥션 노후화 완화를 위한 `pool_recycle`/`pool_timeout` 보강
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 커넥션 반환 전 ping 검증으로 죽은 커넥션 재사용 차단

## 4. 구현/수정 내용
- 변경 파일:
  - `src/dashboard/utils/db_connector.py`
- DB 변경(있다면):
  - 없음
- 주의점:
  - pool 옵션은 dashboard 프로세스 재시작 후 완전 적용됨

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - DB 재기동 후 dashboard `check_db_connection()`이 자동 복구되는지
- 회귀 테스트:
  - dashboard 주요 페이지 조회 오류 여부
- 운영 체크:
  - System Health의 PostgreSQL 상태가 안정적으로 Connected 유지

## 6. 롤백
- 코드 롤백:
  - `src/dashboard/utils/db_connector.py`의 create_engine 옵션 원복
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획 + 결과 문서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 원칙 변경 없음(불필요)

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) 대시보드 startup 시 DB readiness 재시도 로직 검토
  2) DB 재시작 이벤트 알림과 대시보드 health 재검증 자동화 검토

## 9. 변경 이력
- 2026-02-23:
  - `pool_pre_ping` + `pool_recycle` + `pool_timeout` + `pool_use_lifo` 적용으로 대응 완료.
