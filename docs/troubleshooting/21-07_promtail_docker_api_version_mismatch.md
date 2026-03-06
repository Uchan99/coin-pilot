# 21-07. Promtail Docker API Version Mismatch 트러블슈팅 / 핫픽스

작성일: 2026-03-06
상태: Mitigating (코드 반영 완료, OCI 재검증 대기)
우선순위: P1
관련 문서:
- Plan: docs/work-plans/21-07_oci_log_observability_loki_promtail_plan.md
- Result: docs/work-result/21-07_oci_log_observability_loki_promtail_result.md
- Charter update 필요: YES

---

## 1. 트리거(왜 시작했나)
- 모니터링/로그/사용자 리포트로 관측된 내용:
  - 21-07 배포 후 `scripts/ops/check_24h_monitoring.sh t1h`에서 `FAIL:0, WARN:3`가 지속됨.
  - 1차 핫픽스(`PROMTAIL_DOCKER_API_VERSION=1.44`) 반영 후에도 `t1h`가 `FAIL:1, WARN:2`로 재현됨.
  - `promtail` 로그 15분 조회에서 아래 오류가 반복됨:
    - `client version 1.42 is too old. Minimum supported API version is 1.44`
  - 2차 핫픽스(파일 타깃 전환) 후 `t1h`는 `FAIL:0, WARN:2`로 개선됐지만, `Loki service 라벨 미검출` WARN 1건이 잔존함.
  - 3차 보강(`filename` 라벨 추출) 후 `t1h`에서 `FAIL:1, WARN:2`가 재발했고, `timestamp too old`가 확인됨.
- 긴급도/영향:
  - 로그 수집이 실제로 되지 않으면 21-07 핵심 목적(장애 RCA 속도 개선)이 무효화됨.

---

## 2. 증상/영향
- 증상:
  - Loki는 `ready` 상태이나 `service` 라벨이 비어 있음
  - Promtail 로그에 API 버전 오류가 15초 주기로 반복
- 영향(리스크/데이터/비용/운영):
  - 로그 유입 0으로 Explore 검색 불가
  - 장애 시점 증빙 수집 지연
- 발생 조건/재현 조건:
  - Docker Engine API 최소 버전이 1.44 이상인 환경에서 promtail docker_sd 기본 client API(1.42) 사용 시
- 기존 상태(Before) 기준선:
  - `t1h` 실행 결과 `WARN=3`
  - Promtail 오류 로그 반복 발생

---

## 3. 재현/관측 정보
- 재현 절차:
  1) `docker compose ... up -d --build loki promtail grafana`
  2) `scripts/ops/check_24h_monitoring.sh t1h`
  3) `docker compose ... logs --since=15m promtail`
- 입력/데이터:
  - OCI 운영 환경 Docker daemon API version 1.53
- 핵심 로그/에러 메시지:
  - `client version 1.42 is too old. Minimum supported API version is 1.44`
- 관련 지표/대시보드(있다면):
  - Loki `/loki/api/v1/label/service/values` 결과가 `{"status":"success"}`만 반환(라벨 값 없음)

---

## 4. 원인 분석
- 가설 목록:
  1) Loki 미기동/미준비
  2) Promtail 수집 경로 라벨 필터 오설정
  3) Promtail Docker API 버전 불일치
- 조사 과정(무엇을 확인했는지):
  - Loki `/ready`는 정상(`ready`) 확인
  - Promtail 로그에서 docker discovery 단계 오류 반복 확인
  - 오류 메시지에 최소/현재 API 버전이 직접 명시됨
- Root cause(결론):
  - 1차 원인: Promtail docker_sd가 Docker daemon에 API 1.42로 요청해, 최소 지원 1.44 정책에 의해 대상 컨테이너 목록 조회 자체가 실패함.
  - 2차 원인: 파일 타깃 전환 후 `service` 라벨 추출을 relabel `__path__`(glob 패턴)에서 수행해 라벨이 비어 경고가 지속됨.
  - 3차 원인: `promtail-targets`가 symlink를 주기적으로 전량 삭제/재생성해 tailer reopen이 반복되고, 재기동 직후 과거 로그 배치가 `timestamp too old`로 거절됨.

---

## 5. 해결 전략
- 1차 핫픽스(부분 완화):
  - `promtail` 서비스에 `DOCKER_API_VERSION=1.44` 강제 주입
  - 결과: OCI에서 mismatch 재현(`FAIL:1`)으로 근본 해소 실패
- 2차 근본 해결(구조 전환):
  - `promtail`이 Docker API(`docker_sd`)를 직접 호출하지 않도록 설계 변경
  - `promtail-targets` 사이드카가 `coinpilot-*` 컨테이너 로그 경로 symlink를 생성
  - `promtail`은 `/targets/logs/*.log` 파일 타깃만 수집하도록 전환
- 3차 보강(라벨 추출 안정화):
  - relabel 단계의 `__path__`(glob) 기반 추출 대신, pipeline 단계의 `filename` 라벨 기반으로 `service/container`를 추출
- 4차 보강(안정화):
  - `promtail-targets`를 증분 갱신(변경 타깃만 갱신) 방식으로 전환해 symlink churn 최소화
  - promtail positions를 `/run/promtail/positions.yaml` + 영속 볼륨으로 전환
  - `t1h` 스크립트에서 `timestamp too old/entry too far behind`를 경고로 분리
- 안전장치(feature flag, rate limit, timeout/cooldown, circuit breaker 등):
  - `check_24h_monitoring.sh t1h`에서 API mismatch 패턴을 WARN이 아닌 FAIL로 격상

---

## 6. 수정 내용
- 변경 요약:
  - (1차) promtail Docker API 버전 명시
  - (2차) `promtail-targets` 파일 타깃 생성 + promtail 파일 수집 구조 전환
  - (3차) promtail `filename` 기반 라벨 추출로 `service` 라벨 유입 보강
  - (4차) symlink 증분 갱신 + positions 영속화 + too old 경고 분리
  - 운영 점검 스크립트의 탐지 민감도 강화
- 변경 파일:
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `deploy/cloud/oci/monitoring/promtail/config.yml`
  - `deploy/cloud/oci/monitoring/scripts/generate_promtail_log_targets.sh`
  - `.env.example`
  - `deploy/cloud/oci/.env.example`
  - `scripts/ops/check_24h_monitoring.sh`
- DB/스키마 변경(있다면):
  - 없음
- 롤백 방법(필수):
  1) `deploy/cloud/oci/docker-compose.prod.yml`에서 `promtail-targets` 제거 및 `promtail`에 docker socket 수집 방식 복원
  2) `deploy/cloud/oci/monitoring/promtail/config.yml`을 docker_sd 버전으로 원복
  3) `scripts/ops/check_24h_monitoring.sh`의 promtail FAIL 패턴 기준을 이전 단계로 원복
  4) `docker compose ... up -d --no-deps --force-recreate promtail-targets promtail`

---

## 7. 검증
- 실행 명령/절차:
  - `docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-deps --force-recreate promtail-targets promtail`
  - `sleep 45`
  - `docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=15m promtail-targets`
  - `docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=15m promtail`
  - `curl -sS -G http://127.0.0.1:3100/loki/api/v1/label/service/values`
  - `scripts/ops/check_24h_monitoring.sh t1h`
- 결과:
  - 1차 핫픽스 검증 결과:
    - `scripts/ops/check_24h_monitoring.sh t1h` => `FAIL:1`, `WARN:2`
    - `promtail` 15분 로그에서 mismatch 오류 3건 검출
  - 2차 핫픽스 검증 결과:
    - `scripts/ops/check_24h_monitoring.sh t1h` => `FAIL:0`, `WARN:2`
    - `promtail` 전송/`promtail-targets` 타깃 오류는 미검출
    - `Loki service 라벨 미검출` WARN 잔존
  - 3차 보강 코드 반영 완료(OCI 재배포/재측정 대기)
  - 4차 보강 코드 반영 완료(OCI 재배포/재측정 대기)

- 운영 확인 체크:
  1) promtail 로그에서 `client version ... too old` 0건
  2) `promtail-targets` 로그에서 symlink 생성 루프 오류 0건
  3) Loki `service` 라벨에 `coinpilot-*` 1개 이상 확인

### 7.1 정량 개선 증빙(필수)
- 측정 기간/표본:
  - 2026-03-06 09:14~09:31 UTC 구간, `t1h` 점검 2회 + promtail 로그 15분 조회 2회
- 측정 기준(성공/실패 정의):
  - 성공: API mismatch 오류 0건 + `t1h` 로그 파이프라인 관련 FAIL 0건
  - 실패: API mismatch 오류 1건 이상
- 데이터 출처(SQL/로그/대시보드/스크립트):
  - `docker compose logs --since=15m promtail`
  - `scripts/ops/check_24h_monitoring.sh t1h`
- 재현 명령:
  - `docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=15m promtail-targets`
  - `docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=15m promtail`
  - `scripts/ops/check_24h_monitoring.sh t1h`
- Before/After 비교표:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| promtail API mismatch 오류(15분) | 11 | 3 (1차 핫픽스 후) | -8 | -72.7 |
| `check_24h_monitoring.sh t1h` FAIL | 0 | 1 (1차 핫픽스 후) | +1 | N/A |
| `check_24h_monitoring.sh t1h` WARN | 3 | 2 (1차 핫픽스 후) | -1 | -33.3 |
| promtail API mismatch 오류(15분, 2차 핫픽스 후) | 3 | 0 | -3 | -100.0 |
| `check_24h_monitoring.sh t1h` FAIL(2차 핫픽스 후) | 1 | 0 | -1 | -100.0 |
| Loki `service` 라벨 coinpilot-* 검출(2차 핫픽스 후) | 0 | 0 | 0 | 0.0 |
| `timestamp too old` 오류(15분, 3차 보강 후) | 0 | 2 | +2 | N/A |

- 정량 측정 불가 시(예외):
  - 불가 사유:
    - 4차 보강(증분 symlink + positions 영속화 + too old 분류) 코드는 반영됐지만 OCI 재배포/재측정이 아직 수행되지 않음
  - 대체 지표:
    - Root cause 로그 메시지(버전 수치 포함)와 15초 주기 반복 패턴
  - 추후 측정 계획/기한:
    - OCI 재배포 직후 동일 명령으로 15분 내 재측정해 `FAIL=0` 및 `timestamp too old` 경고 축소 여부를 확정

---

## 8. 재발 방지
- 가드레일(테스트/알림/검증 스크립트/권한/필터/타임아웃 등):
  - Docker API 직접 의존을 제거한 파일 타깃 수집 구조로 표준화
  - `PROMTAIL_TARGET_INTERVAL_SEC`를 env로 노출해 동기화 주기 조정 가능
  - 점검 스크립트에서 API mismatch 키워드를 FAIL로 즉시 차단
- 문서 반영:
  - plan/result 업데이트 여부:
    - 반영 완료
  - troubleshooting 링크 추가 여부:
    - result 문서에 링크 반영 완료
  - PROJECT_CHARTER.md 변경(있다면): 무엇을/왜 + changelog 기록
    - 21-07 운영 핫픽스(changelog)에 1차 API 버전 핫픽스와 2차 파일 타깃 구조 전환 사유를 기록

---

## 9. References
- Docker daemon API mismatch 로그 원문(운영 콘솔 출력)
- `docs/work-result/21-07_oci_log_observability_loki_promtail_result.md`

## 10. 배운점
- 트러블 슈팅 경험을 통해 깨달은 점이나 배운점
  - 로그 수집 파이프라인은 "서비스 Up"만으로 정상 판단하면 안 되고, 수집 경로 자체의 프로토콜 호환성까지 검증해야 한다.
- 포트폴리오용으로 트러블 슈팅을 작성할때, 어떤 점을 강조해야하는지, 활용하면 좋을 내용
  - 장애 시점의 수치(오류 건수/반복 주기)와 원인 메시지의 버전 정보(1.42 vs 1.44)를 같이 제시하면 문제 특정의 신뢰도가 높아진다.
- 트러블 슈팅을 통해 어떤 능력이 향상되었는지
  - 운영 로그 기반 Root cause 분리(워밍업 이슈 vs 구조적 버전 불일치) 능력이 향상됐다.
