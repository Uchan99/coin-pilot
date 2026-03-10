# 31. Scheduled Monitoring 런타임 경로/권한 및 Loki readiness false fail

작성일: 2026-03-10
작성자: Codex
관련 계획: `docs/work-plans/31_oci_ops_monitoring_cron_automation_and_gap_hardening_plan.md`
관련 결과: `docs/work-result/31_oci_ops_monitoring_cron_automation_and_gap_hardening_result.md`
상태: Resolved

---

## 1. 문제 정의
- 증상:
  1) `run_scheduled_monitoring.sh`를 비root로 `/tmp` 로그 경로에 수동 실행하면 lock 파일 생성에서 `Permission denied`
  2) `check_24h_monitoring.sh t1h --automation-mode`에서 Loki query API는 정상인데 `/ready` 본문이 비어 `FAIL: 1`로 기록
- 영향:
  - 수동 스모크가 cron과 동일한 경로로 재현되지 않았고,
  - Loki 파이프라인이 실제로는 정상인데 운영 점검이 false fail을 낼 수 있었다.
- 재현 조건:
  - root가 먼저 default lock dir을 생성한 뒤 비root가 다른 LOG_ROOT로 래퍼 실행
  - Loki `/ready` 응답이 비거나 curl이 실패하지만 label query는 성공하는 환경

## 2. 원인
- Root cause:
  1) 기본 `LOCK_ROOT`가 `/tmp/coinpilot-ops-locks`로 고정되어 있어, root가 만든 디렉터리를 비root가 재사용할 때 lock 파일 생성 권한이 충돌했다.
  2) Loki readiness 점검이 `/ready` 단일 조건에 의존해, query API 성공을 fallback으로 인정하지 않았다.

## 3. 조치
- `run_scheduled_monitoring.sh`
  - 기본 `LOCK_ROOT`를 `${LOG_ROOT}/locks`로 변경
- `check_24h_monitoring.sh`
  - `/ready` 실패 시에도 label query API가 성공하면 readiness fallback으로 PASS 처리

## 4. 정량 증빙

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 비root `/tmp` 스모크 lock 경로 일관성 | 불일치 | 일치 | 개선 | 측정 불가 |
| Loki query API 성공 시 false FAIL 건수 | 1 | 0 | -1 | -100.0 |

- 측정 기준:
  - 표본: 2026-03-10 OCI 수동 스모크 1회
  - 성공 기준:
    1) custom `COINPILOT_OPS_LOG_ROOT` 사용 시 별도 `COINPILOT_OPS_LOCK_ROOT` 없이 실행 가능
    2) Loki label query success 환경에서 `/ready` empty만으로 FAIL 하지 않을 것

## 5. 검증 명령
- `bash -n scripts/ops/run_scheduled_monitoring.sh`
- `bash -n scripts/ops/check_24h_monitoring.sh`
- `COINPILOT_OPS_LOG_ROOT=/tmp/coinpilot-ops bash scripts/ops/run_scheduled_monitoring.sh monitoring-t1h scripts/ops/check_24h_monitoring.sh t1h --automation-mode`

## 6. 재발 방지
- lock 경로는 기본적으로 log root 하위로 두어 권한 모델을 같이 가져간다.
- readiness probe는 단일 endpoint만 보지 않고 동일 서비스의 query API 성공 여부를 fallback 신호로 함께 본다.
