# 30. Strategy Feedback Ops Script Runtime Compatibility

작성일: 2026-03-10  
작성자: Codex  
관련 계획서: `docs/work-plans/30_strategy_feedback_automation_spec_first_plan.md`  
관련 결과서: `docs/work-result/30_strategy_feedback_automation_spec_first_result.md`

---

## 0. 문제 정의
- 증상:
  - OCI에서 `scripts/ops/strategy_feedback_report.sh 7 14 30`, `scripts/ops/strategy_feedback_gate.sh 7 14 30` 실행 시 초기에는 `Permission denied`, 이후 `python: command not found`
- 영향:
  - 30 Phase 1 분석기/게이트 PoC를 운영 데이터로 즉시 검증할 수 없었다.
- 재현 조건:
  - `/opt/coin-pilot`에서 직접 스크립트를 실행하는 OCI 운영 셸
- Root cause:
  1. 스크립트가 `python` 바이너리만 가정하고 `python3` 환경을 고려하지 않았다.
  2. `REPORT_DAYS`, `APPROVAL_DAYS`, `FALLBACK_DAYS`를 셸 지역변수로만 두고 heredoc 파이썬에서 `os.environ[...]`으로 읽도록 작성해 런타임 환경 주입이 불완전했다.
  3. 최초 커밋에는 실행 권한 비트(`+x`)가 빠져 있었다.

## 1. 대응 내용
1. `python3 -> python` 순으로 실행 파일을 자동 탐지하도록 수정
2. `REPORT_DAYS`, `APPROVAL_DAYS`, `FALLBACK_DAYS`, `PYTHONPATH`를 명시적으로 `export`
3. 실행 파일이 아예 없을 때는 `[FAIL]` 메시지와 `127` exit code를 반환
4. 실행 권한 비트(`100755`)를 부여해 직접 실행 가능하도록 보정

## 2. Before / After 정량 증빙
| 항목 | Before | After | 변화량 |
|---|---:|---:|---:|
| OCI 직접 실행 성공률 | 0/2 | 2/2 기대치(호환성 패치 후 재검증 대상) | +2 |
| 지원 파이썬 바이너리 | 1 (`python`) | 2 (`python3`, `python`) | +1 |
| export된 필수 환경 변수 | 0 | 4 | +4 |
| 직접 실행 가능 여부 | `100644` | `100755` | +1 권한 비트 |

## 3. 측정 기준
- 기간:
  - 2026-03-10 운영 재현
- 표본 수:
  - `report`, `gate` 스크립트 각 1회 이상
- 성공 기준:
  - OCI에서 두 스크립트가 `command not found` 없이 실행
  - `REPORT_DAYS/APPROVAL_DAYS/FALLBACK_DAYS`가 파이썬에서 정상 참조
- 실패 기준:
  - `python3/python` 탐지 실패
  - 환경 변수 누락으로 `KeyError`

## 4. 증빙 명령
```bash
stat -c '%A %n' scripts/ops/strategy_feedback_report.sh scripts/ops/strategy_feedback_gate.sh
bash scripts/ops/strategy_feedback_report.sh 7 14 30
bash scripts/ops/strategy_feedback_gate.sh 7 14 30
```

## 5. 재발 방지
1. 신규 ops 스크립트는 `python3` 우선 탐지 + `python` fallback을 기본 패턴으로 사용
2. heredoc 파이썬이 셸 변수를 읽어야 하면 반드시 `export`를 먼저 수행
3. 로컬 검증 시 `bash -n`만 하지 말고 실제 실행 경로(`bash script.sh ...`)까지 포함
