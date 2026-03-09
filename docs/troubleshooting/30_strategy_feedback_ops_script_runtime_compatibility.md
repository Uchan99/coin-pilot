# 30. Strategy Feedback Ops Script Runtime Compatibility

작성일: 2026-03-10  
작성자: Codex  
관련 계획서: `docs/work-plans/30_strategy_feedback_automation_spec_first_plan.md`  
관련 결과서: `docs/work-result/30_strategy_feedback_automation_spec_first_result.md`

---

## 0. 문제 정의
- 증상:
  - OCI에서 `scripts/ops/strategy_feedback_report.sh 7 14 30`, `scripts/ops/strategy_feedback_gate.sh 7 14 30` 실행 시 초기에는 `Permission denied`, 이후 `python: command not found`, 그 다음 `ModuleNotFoundError: No module named 'sqlalchemy'`
- 영향:
  - 30 Phase 1 분석기/게이트 PoC를 운영 데이터로 즉시 검증할 수 없었다.
- 재현 조건:
  - `/opt/coin-pilot`에서 직접 스크립트를 실행하는 OCI 운영 셸
- Root cause:
  1. 스크립트가 다른 운영 스크립트와 달리 `bot` 컨테이너가 아닌 호스트 Python 런타임을 직접 사용하도록 작성돼, OCI 호스트에 설치되지 않은 `sqlalchemy` 등 의존성 import가 실패했다.
  2. 호스트 런타임 기준에서는 `python` 바이너리 별칭도 고정돼 있지 않아 `python: command not found`가 추가로 발생했다.
  3. `REPORT_DAYS`, `APPROVAL_DAYS`, `FALLBACK_DAYS`를 셸 지역변수로만 두고 heredoc 파이썬에서 `os.environ[...]`으로 읽도록 작성해 런타임 환경 주입이 불완전했다.
  4. 최초 커밋에는 실행 권한 비트(`+x`)가 빠져 있었다.

## 1. 대응 내용
1. `strategy_feedback_report.sh`, `strategy_feedback_gate.sh`를 `docker compose exec -T bot python` 패턴으로 전환
2. `REPORT_DAYS`, `APPROVAL_DAYS`, `FALLBACK_DAYS`, `PYTHONPATH=/app`를 container exec 환경 변수로 주입
3. `ENV_FILE`, `COMPOSE_FILE` 경로 검증을 추가
4. 실행 권한 비트(`100755`)를 부여해 직접 실행 가능하도록 보정

## 2. Before / After 정량 증빙
| 항목 | Before | After | 변화량 |
|---|---:|---:|---:|
| OCI 직접 실행 성공률 | 0/2 | 2/2 | +2 |
| 런타임 일관성 | host python 의존 | bot 컨테이너 런타임 고정 | +1 |
| container exec 주입 변수 | 0 | 4 | +4 |
| 직접 실행 가능 여부 | `100644` | `100755` | +1 권한 비트 |

## 3. 측정 기준
- 기간:
  - 2026-03-10 운영 재현
- 표본 수:
  - `report`, `gate` 스크립트 각 1회 이상
- 성공 기준:
  - OCI에서 두 스크립트가 `command not found`/`ModuleNotFoundError` 없이 실행
  - `REPORT_DAYS/APPROVAL_DAYS/FALLBACK_DAYS`가 bot 컨테이너 파이썬에서 정상 참조
- 실패 기준:
  - compose env/파일 경로 불일치
  - 환경 변수 누락으로 `KeyError`

## 4. 증빙 명령
```bash
stat -c '%A %n' scripts/ops/strategy_feedback_report.sh scripts/ops/strategy_feedback_gate.sh
bash scripts/ops/strategy_feedback_report.sh 7 14 30
bash scripts/ops/strategy_feedback_gate.sh 7 14 30
```

## 4.1 최종 확인 결과
- `strategy_feedback_report.sh 7 14 30`:
  - `gate_result=discard`
  - `approval_tier=reviewable`
  - `sell_samples=16`
  - `ai_decisions=544`
- `strategy_feedback_gate.sh 7 14 30`:
  - `gate_result=discard approval_tier=reviewable sell_samples=16 ai_decisions=544`
- 결론:
  - 런타임 호환성 이슈는 해소됐고, 현재 남은 문제는 스크립트 실행 자체가 아니라 실제 전략 KPI/표본 조건이다.

## 5. 재발 방지
1. 신규 ops 스크립트는 host python보다 `docker compose exec -T bot python`을 기본 패턴으로 사용
2. heredoc 파이썬이 파라미터를 읽어야 하면 container exec `-e` 또는 명시적 `export`를 먼저 수행
3. 로컬 검증 시 `bash -n`만 하지 말고 실제 실행 경로(`bash script.sh ...`)까지 포함
