# 31. OCI 운영 모니터링 스크립트 크론 자동화 + 관측 갭 보강 결과

작성일: 2026-03-10
작성자: Codex
관련 계획서: docs/work-plans/31_oci_ops_monitoring_cron_automation_and_gap_hardening_plan.md
상태: In Progress (Phase A/B Verified on OCI, Phase C Implemented)
완료 범위: Phase A, Phase B, Phase C(구현)
관련 트러블슈팅(있다면): `docs/troubleshooting/31_scheduled_monitoring_runtime_path_and_loki_readiness_false_fail.md`

---

## 1. 해결한 문제 정의
- 증상:
  - 운영 점검 스크립트는 존재했지만 cron/systemd에서 바로 쓰기엔 실행 가드, timeout, 로그 표준이 없었다.
  - `check_24h_monitoring.sh t1h`는 수동 UI 확인 항목을 항상 `WARN`으로 올려 자동 실행 시 고정 노이즈가 발생할 수 있었다.
- 영향:
  - 동일 점검을 cron에 억지로 붙이면 중복 실행과 로그 산재, 의미 없는 WARN 누적이 생길 수 있었다.
- 재현 조건:
  - OCI에서 `scripts/ops/check_24h_monitoring.sh t1h`를 주기 실행하거나, 여러 운영 스크립트를 개별 cron 라인으로 직접 등록할 때

## 2. 구현 내용
### 2.1 `check_24h_monitoring.sh` 자동화 모드 추가
- 파일:
  - `scripts/ops/check_24h_monitoring.sh`
- 변경 내용:
  - `--automation-mode` 플래그 추가
  - 자동화 모드에서는 Grafana/Discord 수동 확인 항목을 `WARN`이 아니라 `INFO`로 기록
- 설계 이유:
  - 자동 실행 결과는 “실제 장애” 위주로 해석해야 하므로, 사람이 반드시 UI에서 봐야 하는 항목은 고정 WARN에서 제외하는 편이 운영상 낫다.
- 고려 대안:
  1) 수동 확인 WARN 유지
  2) 해당 항목 자체를 삭제
  3) 자동화 모드에서만 INFO 강등 (채택)
- 트레이드오프:
  - 장점: cron 로그의 고정 노이즈 감소
  - 단점: 수동 확인 필요성이 자동 로그에서는 약해질 수 있음
  - 완화: INFO 메시지와 runbook에 수동 확인 필요성을 그대로 남김

### 2.2 `run_scheduled_monitoring.sh` 래퍼 추가
- 파일:
  - `scripts/ops/run_scheduled_monitoring.sh`
- 변경 내용:
  - `flock` 기반 중복 실행 방지
  - `timeout` 기반 hang 방지
  - `/var/log/coinpilot/ops` 일 단위 로그 표준
  - `started_at`, `ended_at`, `elapsed_sec`, `exit_code` 메타 로그 기록
- 설계 이유:
  - cron 라인마다 flock/timeout/log redirection을 반복하면 운영 실수 가능성이 높다.
  - 공통 래퍼로 고정해야 스케줄 추가 시 검증이 단순해진다.
- 고려 대안:
  1) 각 cron 라인에 직접 flock/timeout 명시
  2) systemd timer 전면 전환
  3) 공통 shell wrapper 사용 (채택)
- 트레이드오프:
  - 장점: 운영 표준 단일화, 로그 증빙 일관성 확보
  - 단점: wrapper 자체의 유지보수 비용
  - 완화: bash 단일 파일 + 최소 env override만 허용

### 2.3 cron 예시 파일 추가
- 파일:
  - `deploy/cloud/oci/ops/coinpilot-monitoring.cron.example`
- 변경 내용:
  - `t1h/t6h/t12h/t24h`, `ai_decision_canary_report.sh 24`, `llm_usage_cost_report.sh 24`, `strategy_feedback_report.sh 7 14 30` 주기표 예시 추가
- 설계 이유:
  - runbook 문장만으로는 실제 등록 시각과 충돌 회피 기준이 흐려진다.
  - 예시 cron 파일이 있으면 운영자가 그대로 검토/적용하기 쉽다.

### 2.4 관측 갭 자동 판정(Phase C) 추가
- 파일:
  - `scripts/ops/check_24h_monitoring.sh`
- 변경 내용:
  - `LLM snapshot freshness` 점검 추가
    - `LLM_COST_SNAPSHOT_ENABLED=false`면 개인 계정 fallback으로 간주하고 INFO 처리
    - 활성화 상태에서는 provider별 snapshot 0건/stale 여부를 WARN으로 판정
  - `AI decision inactivity` 점검 추가
    - 최근 6시간 `agent_decisions` 0건이면 bot 상태와 함께 WARN/FAIL 분기
  - `scheduled monitoring heartbeat` 점검 추가
    - `/var/log/coinpilot/ops/*.log` 최신 갱신 시각을 보고 t1h/t6h/t12h/t24h/ai-canary/llm-usage job의 공백을 WARN으로 판정
- 설계 이유:
  - Phase A/B만으로는 "돌아간다"는 사실만 확인되고, "최근에 안 돌았는지/비용 스냅샷이 멈췄는지/AI 의사결정이 장시간 0건인지"를 자동으로 읽을 수 없었다.
  - 기존 cron 구조를 바꾸지 않고 `check_24h_monitoring.sh` 안에 얇은 판정 로직만 추가하는 편이 운영 리스크가 가장 낮다.
- 고려 대안:
  1) 별도 Phase C 전용 스크립트 생성
  2) `run_scheduled_monitoring.sh`가 로그 본문까지 파싱
  3) `check_24h_monitoring.sh`에 판정 함수 직접 추가 (채택)
- 트레이드오프:
  - 장점: 기존 운영자가 쓰는 단일 점검 스크립트 안에서 모든 판정을 확인 가능
  - 단점: 쉘 스크립트 길이가 길어짐
  - 완화: helper 함수로 분리하고 임계치(`LLM_SNAPSHOT_MAX_LAG_MINUTES`, `AI_DECISION_INACTIVITY_HOURS`)를 env override로 노출

## 3. 정량 증빙

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 자동 실행 전용 플래그 수(`check_24h_monitoring.sh`) | 0 | 1 | +1 | 측정 불가(분모 0) |
| 공통 스케줄 래퍼 수 | 0 | 1 | +1 | 측정 불가(분모 0) |
| cron 예시 등록 라인 수 | 0 | 7 | +7 | 측정 불가(분모 0) |
| 고정 수동 WARN 항목(자동화 모드 기준) | 1 | 0 | -1 | -100.0 |
| Phase C 자동 판정 함수 수 | 0 | 3 | +3 | 측정 불가(분모 0) |
| Phase C env override 수 | 0 | 3 | +3 | 측정 불가(분모 0) |

- 측정 기준:
  - 대상 파일: `scripts/ops/check_24h_monitoring.sh`, `scripts/ops/run_scheduled_monitoring.sh`, `deploy/cloud/oci/ops/coinpilot-monitoring.cron.example`
  - 성공 기준:
    1) `check_24h_monitoring.sh --automation-mode`가 문법상 유효할 것
    2) 래퍼와 cron 예시가 bash/텍스트 기준 유효할 것
    3) 자동화 모드에서 수동 확인 항목이 WARN 누적에서 제외될 것
    4) Phase C helper가 문법상 유효하고, `--help`에 신규 override가 노출될 것
- 측정 불가 사유:
  - Phase C는 이번 턴에서 구현만 완료했고 OCI에서 `t6h/t24h`를 아직 재검증하지 않았다.
  - 대체 지표로 bash syntax, help 출력, helper 함수 수를 사용했다.
  - 추후 측정 계획: OCI에서 `check_24h_monitoring.sh t6h`, `t24h`, `all`을 실행해 inactivity/freshness/heartbeat 판정을 실측한다.

## 4. 검증 명령
- 정적 검증:
  - `bash -n scripts/ops/check_24h_monitoring.sh`
  - `bash -n scripts/ops/run_scheduled_monitoring.sh`
  - `scripts/ops/check_24h_monitoring.sh --help`
  - `scripts/ops/run_scheduled_monitoring.sh --help || true`
  - `rg -n "automation-mode|run_scheduled_monitoring|coinpilot-monitoring.cron.example" scripts/ops deploy/cloud/oci/ops docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
  - `rg -n "LLM_SNAPSHOT_MAX_LAG_MINUTES|AI_DECISION_INACTIVITY_HOURS|heartbeat" scripts/ops/check_24h_monitoring.sh`
- OCI 적용 후 검증(예정):
  - `sudo install -m 0644 /opt/coin-pilot/deploy/cloud/oci/ops/coinpilot-monitoring.cron.example /etc/cron.d/coinpilot-monitoring`
  - `sudo systemctl restart cron`
  - `sudo tail -n 200 /var/log/coinpilot/ops/*.log`
  - `crontab -l || sudo cat /etc/cron.d/coinpilot-monitoring`
  - `sudo bash /opt/coin-pilot/scripts/ops/check_24h_monitoring.sh t6h --automation-mode`
  - `sudo bash /opt/coin-pilot/scripts/ops/check_24h_monitoring.sh t24h --automation-mode`

## 5. 운영 적용 메모
- 이번 Phase는 host-side script/doc 변경만 포함한다.
- OCI 적용 시 `git pull`만으로 충분하고 bot 재빌드는 불필요하다.

## 5.1 OCI 1차 운영 검증 메모
- 확인된 사실:
  - `/etc/cron.d/coinpilot-monitoring` 설치와 `cron active`는 정상 확인됨
  - root 기준 스모크에서 `ai-canary-24h`, `llm-usage-24h`는 `exit_code=0`
  - `monitoring-t1h`는 첫 실행에서 사용자 입력 줄바꿈으로 `--automation-` 잘림 오타가 있었고, 두 번째 정상 실행에서는 Loki `/ready` empty 응답 때문에 false FAIL이 발생했다.
  - 비root `/tmp` 스모크에서는 기본 lock 경로가 root 생성 디렉터리를 재사용해 `Permission denied`가 발생했다.
- 조치:
  - 관련 원인을 트러블슈팅 문서로 분리하고,
  - 기본 lock 경로를 `${LOG_ROOT}/locks`로 변경,
  - Loki query API success를 readiness fallback으로 인정하도록 보정했다.

## 5.2 OCI 2차 운영 검증(보정 후 최종)
- 검증 시각:
  - 2026-03-10 14:28 UTC 전후
- 실행 명령:
  - `sudo bash /opt/coin-pilot/scripts/ops/run_scheduled_monitoring.sh monitoring-t1h /opt/coin-pilot/scripts/ops/check_24h_monitoring.sh t1h --automation-mode`
  - `sudo bash /opt/coin-pilot/scripts/ops/run_scheduled_monitoring.sh ai-canary-24h /opt/coin-pilot/scripts/ops/ai_decision_canary_report.sh 24`
  - `sudo bash /opt/coin-pilot/scripts/ops/run_scheduled_monitoring.sh llm-usage-24h /opt/coin-pilot/scripts/ops/llm_usage_cost_report.sh 24`
  - `sudo tail -n 200 /var/log/coinpilot/ops/*.log`
- 정량 결과:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| `monitoring-t1h` exit_code | 1 | 0 | -1 | -100.0 |
| `monitoring-t1h` FAIL 개수 | 1 | 0 | -1 | -100.0 |
| `monitoring-t1h` WARN 개수 | 0 | 0 | 0 | 0.0 |
| `ai-canary-24h` exit_code | 0 | 0 | 0 | 0.0 |
| `llm-usage-24h` exit_code | 0 | 0 | 0 | 0.0 |
| cron 활성 상태 | active | active | 0 | 0.0 |

- 세부 확인:
  - `monitoring-t1h` 최신 로그에서 `Loki readiness 확인(ready)`와 `FAIL: 0 / WARN: 0 / exit_code=0`를 확인했다.
  - `ai-canary-24h` 최신 로그에서 `primary 14건`, `canary 3건`, `exit_code=0`를 확인했다.
  - `llm-usage-24h` 최신 로그에서 route/provider/model 집계 5행과 `exit_code=0`를 확인했다.
  - `llm_provider_cost_snapshots`가 `0 rows`인 상태는 21-04 개인 계정 fallback 정책과 일치하므로, 본 Phase에서는 FAIL 조건으로 취급하지 않았다.
- 해석:
  - cron 파일 설치, root 실행, 로그 보관, `flock/timeout` 래퍼, 자동화 모드, Loki readiness fallback이 모두 OCI에서 실제 동작함을 확인했다.
  - 따라서 31은 전체 완료 전 단계이지만, **Phase A/B의 설계와 운영 적용은 검증 완료**로 판단한다.

## 5.3 Phase C 구현 메모
- 확인된 사실:
  - 21-04가 개인 계정 fallback 모드(`LLM_COST_SNAPSHOT_ENABLED=false`)로 고정되면서, Phase C의 freshness 점검은 "0 rows를 장애로 오해하지 않는 정책"을 함께 가져가야 했다.
  - 운영 공백은 비용 snapshot 자체보다 "최근 의사결정이 0건인지"와 "scheduled log가 갱신되지 않는지"를 먼저 보는 편이 실무적으로 더 유효하다.
- 조치:
  - `check_24h_monitoring.sh`에 snapshot freshness, AI inactivity, cron heartbeat helper를 추가했다.
  - 다만 OCI에서 이번 턴에 직접 검증한 것은 Phase A/B 로그 경로이므로, Phase C는 구현 완료 상태로 기록하고 OCI 재검증은 다음 실행으로 남긴다.

## 6. README 동기화 여부
- 이번 Phase는 main task `done`이 아니고 운영 예시/래퍼 추가 수준이므로 `README.md`는 동기화하지 않았다.
- 추후 31 전체 완료 또는 운영 정책 확정 시 README 동기화 여부를 다시 판단한다.
