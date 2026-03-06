# 31. OCI 운영 모니터링 스크립트 크론 자동화 + 관측 갭 보강 계획

**작성일**: 2026-03-07  
**작성자**: Codex  
**상태**: Approval Pending  
**관련 계획 문서**: `docs/work-plans/18-14_oci_24h_monitoring_script_automation_plan.md`, `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`, `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`, `docs/work-plans/21-08_grafana_loki_log_dashboard_panelization_plan.md`  
**승인 정보**: 미승인 / - / 사용자 승인 대기

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 현재 `scripts/ops/check_24h_monitoring.sh`, `scripts/ops/llm_usage_cost_report.sh`, `scripts/ops/ai_decision_canary_report.sh`는 수동 실행 중심이다.
  - 점검 결과를 파일로 남기는 기능(`--output`)은 있으나, 주기 실행/중복 실행 방지/보관 정책이 표준화되지 않았다.
  - 주간 Exit 리포트는 존재하지만, 전략 수정 제안(퍼널 분해 + 백테스트 + 파라미터 후보)까지 포함된 자동 주간 산출은 부재하다.
  - `check_24h_monitoring.sh t1h`는 수동 확인 안내(`Grafana/Discord`)를 WARN으로 출력하므로 cron 상시 실행 시 경고 노이즈가 고정 발생할 수 있다.
- 왜 즉시 대응이 필요한지:
  - 현재 운영 안정화 단계에서 점검 누락/근거 누락/수동 반복 실행 부담이 누적되면 장애 대응 속도와 추적성이 저하된다.

## 1. 문제 요약
- 증상:
  - 동일 점검을 사람이 직접 반복 실행해야 하며, 실행 간격/증빙 로그가 일관되지 않다.
  - 리포트 스크립트(`canary/cost`)는 “출력”은 되지만 자동 판정/알림 연결 기준이 없다.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 모니터링 공백 시간 발생 가능
  - 리스크: 이슈 탐지 지연, 재현 가능한 증빙 누락
  - 데이터: 운영 히스토리(파일 로그) 불연속
  - 비용: 수동 점검 공수 증가, 야간 대응 부담 증가
- 재현 조건:
  - 배포/재기동 이후 24시간 관찰, 또는 일일 운영 점검을 수동으로 수행할 때

## 2. 원인 분석
- 가설:
  1) 18-14에서 “점검 스크립트”는 도입됐지만 “스케줄러 오케스트레이션”은 별도 표준이 없다.
  2) 체크 스크립트의 수동 안내 WARN이 자동 실행 환경에서 오탐성 노이즈로 누적된다.
  3) LLM/AI 의사결정 관측은 리포트 출력형이라 운영 임계치 기반 자동 점검이 부족하다.
- 조사 과정:
  - `scripts/ops` 5개 스크립트 구조 확인
  - `check_24h_monitoring.sh`의 모드/출력/경고 정책(`manual routing notice`) 확인
  - 기존 백업 cron(`03:05/03:15/03:25`)과 충돌 가능 시간대 확인
- Root cause:
  - “운영 스크립트의 표준 주기표 + 실행 가드(flock/timeout) + 로그 보존 + 갭 보강 점검”이 통합 설계되지 않음.

## 3. 대응 전략
- 단기 핫픽스:
  - OCI 기준 cron 주기표와 실행 래퍼를 먼저 도입해 수동 실행 의존도를 낮춘다.
- 근본 해결:
  - 스크립트별 목적에 맞게 주기를 분리하고, 자동 실행 전용 모드(수동 WARN 억제)를 도입한다.
  - 추가 관측 갭(LLM snapshot freshness, AI decision inactivity)을 점검 스크립트로 표준화한다.
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - `flock`으로 중복 실행 방지
  - `timeout`으로 장기 hang 방지
  - 로그 경로 분리(`/var/log/coinpilot/ops/`) + logrotate 적용
  - 백업 cron 시간대와 충돌하지 않는 실행 간격 적용

## 4. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **cron 기반 다중 주기 실행 + 단일 래퍼 스크립트 + 체크 스크립트 자동화 모드 확장**

- 고려 대안:
  1) `check_24h_monitoring.sh all`만 매시간 실행
  2) systemd timer로 전면 전환
  3) cron에서 스크립트별 주기 분리 실행(채택 예정)

- 대안 비교:
  1) `all` 매시간:
    - 장점: 구성 단순
    - 단점: 불필요한 중복 점검/부하 증가, 신호 대 잡음비 저하
  2) systemd timer:
    - 장점: 상태 관리/재시도 강력
    - 단점: 현재 운영 표준(백업 cron)과 이원화되어 초기 운영 난이도 증가
  3) cron 주기 분리:
    - 장점: 기존 운영 방식과 일관, 도입 비용 낮음, 주기 최적화 용이
    - 단점: cron 파일/로그 관리 규칙을 별도 문서화해야 함

## 5. 구현/수정 내용 (예정)
### Phase A. 운영 주기표 확정(내 환경 기준)
- 기준 경로:
  - Repo: `/opt/coin-pilot`
  - Env: `/opt/coin-pilot/deploy/cloud/oci/.env`
  - Compose: `/opt/coin-pilot/deploy/cloud/oci/docker-compose.prod.yml`
- 기존 백업 cron(`03:05/03:15/03:25`)과 충돌 회피 스케줄 초안:
  1) `check_24h_monitoring.sh t1h`: 매시 `:40`
  2) `check_24h_monitoring.sh t6h`: `00:50, 06:50, 12:50, 18:50`
  3) `check_24h_monitoring.sh t12h`: `01:00, 13:00`
  4) `check_24h_monitoring.sh t24h`: `04:10` (백업 완료 이후)
  5) `ai_decision_canary_report.sh 24`: `04:20`
  6) `llm_usage_cost_report.sh 24`: `04:30`
  7) `strategy_feedback_report.sh 7`: 매주 일요일 `22:10 KST` (기존 주간 Exit 리포트 직후)
  8) `strategy_feedback_apply.sh` 자동 적용은 Shadow 2주 종료 후에만 활성화(초기 비활성 기본)

### Phase B. 자동 실행 가드 도입
- 변경 파일(예정):
  - `scripts/ops/check_24h_monitoring.sh` (자동화 모드 플래그 추가)
  - `scripts/ops/run_scheduled_monitoring.sh` (신규, flock/timeout/출력 경로 통합)
  - `deploy/cloud/oci/ops/coinpilot-monitoring.cron.example` (신규)
- 핵심 변경:
  - 수동 안내 WARN을 자동화 모드에서 억제(또는 별도 INFO 전환)
  - 실패 종료코드 유지 + 실행 메타 로그(`started_at`, `elapsed_sec`) 기록

### Phase C. 관측 갭 보강(추가 모니터링)
- 후보 1) LLM 비용 스냅샷 freshness 점검 자동화
  - 대상: `llm_provider_cost_snapshots` 최신 시각 지연
  - 기준 초안: lag > 180분 시 WARN
- 후보 2) AI 의사결정 inactivity 점검
  - 대상: 최근 N시간 `agent_decisions` 건수
  - 기준 초안: 6시간 0건 + bot 정상 동작 시 WARN
- 후보 3) cron 실행 자체의 heartbeat
  - 대상: `/var/log/coinpilot/ops/*.log` 갱신 시각
  - 기준 초안: 2주기 이상 미갱신 시 FAIL

### Phase D. 문서/운영절차 동기화
- 변경 파일(예정):
  - `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
  - `docs/work-result/31_oci_ops_monitoring_cron_automation_and_gap_hardening_result.md`
  - `docs/checklists/remaining_work_master_checklist.md`
- 반영 내용:
  - cron 등록/검증/중복 실행 방지/로그 보관/장애 시 조치 절차 추가

## 6. 검증 기준
- 재현 케이스에서 해결 확인:
  1) cron 등록 후 24시간 동안 각 스크립트 실행 로그가 주기대로 누적되는지 확인
  2) 의도된 테스트 실패 상황에서 FAIL/WARN 분류가 기존 정책과 일치하는지 확인
- 회귀 테스트:
  - `check_24h_monitoring.sh` 수동 실행 결과(`t1h`)가 기존 대비 악화되지 않아야 함
  - 자동화 모드 추가 후 기존 `--output` 동작 유지
- 운영 체크:
  - 24시간 누적 결과에서 “고정 WARN(수동 안내)”이 제거되고 의미 있는 WARN만 남는지 확인
  - 백업 cron 시간대와 모니터링 실행이 충돌하지 않는지 확인

## 7. 롤백
- 코드 롤백:
  - 신규 cron 래퍼/cron 예시 제거, `check_24h_monitoring.sh` 자동화 모드 변경 revert
- 데이터/스키마 롤백:
  - 없음

## 8. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획 승인 후 구현 시 결과 문서 생성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 정책(모니터링 표준 주기/임계치) 변경 시 changelog 반영

## 9. 추가 모니터링 필요사항 분석 결과(현 시점)
1) `check_24h_monitoring.sh t1h` 자동 실행 시 수동 안내 WARN이 고정 발생 가능(노이즈)
2) `llm_usage_cost_report.sh`의 snapshot freshness는 출력만 있고 자동 판정 없음
3) `ai_decision_canary_report.sh`는 품질 분포 리포트는 가능하나 “활성도 급감” 경보 기준이 없음
4) 운영 스크립트 로그 보관/회전(logrotate) 표준이 미정

## 10. 후속 조치
1) 승인 후 구현은 Phase A~D 순으로 진행
2) 구현 완료 시 72시간 관찰 결과(실행 성공률/FAIL/WARN 추이)를 결과 문서에 정량 기록
3) 필요 시 21-03/21-04 계획의 완료 조건에 “자동 관측 리포트 존재”를 연결 검토

## 11. 계획 변경 이력
- 2026-03-07: 사용자 요청에 따라 신규 계획 생성(Approval Pending). `scripts/ops` 운영 스크립트의 cron 자동화와 관측 갭 보강 범위를 정의.
- 2026-03-07: 사용자 요청에 따라 전략 자동화 주기를 주 1회(7일)로 명확화하고, 기존 Weekly Exit 리포트 직후 전략 제안 리포트 실행 슬롯(`일요일 22:10 KST`)을 주기표에 추가.
- 2026-03-07: 사용자 요청에 따라 전략 자동 적용 스케줄은 Shadow 2주 종료 전까지 비활성(default off) 정책을 추가.
