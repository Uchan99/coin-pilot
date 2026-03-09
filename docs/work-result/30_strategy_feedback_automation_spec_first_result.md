# 30. 전략 피드백 자동화(Spec-First) 결과

작성일: 2026-03-10
작성자: Codex
관련 계획서: `docs/work-plans/30_strategy_feedback_automation_spec_first_plan.md`
상태: In Progress (Phase 1 분석기/ops report 구현 완료, OCI 런타임 호환성 보정 포함)

---

## 0. 해결한 문제 정의
- 증상:
  - 전략 수정 판단이 Exit 리포트, Rule Funnel, AI Decision, 비용 리포트로 분산돼 있어 "지금 변경 후보를 검토해도 되는지"를 한 번에 보기 어려웠다.
- 영향:
  - 파라미터 튜닝 판단이 사람의 수동 해석에 의존했고, 표본 부족인지/운영 병목인지/실제 전략 병목인지 분리 판단이 늦었다.
- 재현 조건:
  - SELL 표본이 충분하지 않거나(`12~20` 근처), Rule Funnel/AI/비용 관측이 동시에 엮이는 주간 운영 점검 시점
- Root cause:
  - 전략 피드백용 단일 payload, 게이트 판정(`hold|reviewable|strong_approval`, `recommend|hold|discard`), ops 스크립트가 아직 없었다.

## 1. 이번 Phase 범위
- `src/analytics/strategy_feedback.py` 추가
- `scripts/ops/strategy_feedback_report.sh` 추가
- `scripts/ops/strategy_feedback_gate.sh` 추가
- `tests/analytics/test_strategy_feedback.py` 추가
- 승인 정책 문서/체크리스트 동기화

## 2. 구현 내용
1. 전략 피드백 분석기
   - Exit summary, Rule Funnel, AI reject, LLM cost를 한 payload로 묶음
   - `approval_tier`:
     - `hold`
     - `reviewable`
     - `strong_approval`
   - `gate_result`:
     - `recommend`
     - `hold`
     - `discard`
2. 이중 표본 게이트 구현
   - `SELL < 12`: 후보 생성만, `hold`
   - `12 <= SELL < 20`: 수동 검토 가능, `reviewable`
   - `SELL >= 20`: 강한 승인 게이트, `strong_approval`
3. ops 스크립트
   - `strategy_feedback_report.sh`: 사람이 읽는 리포트 + JSON payload 출력
   - `strategy_feedback_gate.sh`: gate result / approval tier만 빠르게 판정
4. 후보 생성 로직(1차)
   - `TAKE_PROFIT`, `TRAILING_STOP`, `STOP_LOSS` 신호 기반 candidate 생성
   - `max_per_order` 같은 운영 한도 병목이면 전략 후보는 생성하지 않음

## 3. Before / After 정량 증빙
| 항목 | Before | After | 변화량 |
|---|---:|---:|---:|
| 전략 피드백 단일 분석기 | 0 | 1 | +1 |
| 전략 피드백 ops 스크립트 | 0 | 2 | +2 |
| 전략 승인 tier | 0 | 3 (`hold/reviewable/strong_approval`) | +3 |
| 전략 gate result | 0 | 3 (`recommend/hold/discard`) | +3 |
| 신규 테스트 | 0 | 3 passed | +3 |

## 4. 측정 기준
- 기간:
  - 2026-03-10 로컬 구현 검증
- 표본 수:
  - 신규 테스트 3건
- 성공 기준:
  - fallback 윈도우(`14d -> 30d`) 동작
  - `approval_tier` 기준값 동작
  - 운영 한도 병목(`max_per_order`) 시 전략 후보 미생성
- 실패 기준:
  - 분석기 import/pytest 실패
  - gate/report 스크립트 shell syntax 실패

## 5. 증빙 근거 (명령)
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/analytics/test_strategy_feedback.py
python3 -m py_compile src/analytics/strategy_feedback.py
bash -n scripts/ops/strategy_feedback_report.sh
bash -n scripts/ops/strategy_feedback_gate.sh
```

## 6. 측정 불가 사유 / 대체 지표 / 추후 계획
- 측정 불가 사유:
  - provider 비용 snapshot이 아직 0건이라 비용 reconciliation 기반 승인 판단은 완결되지 않았다.
- 대체 지표:
  - 단위 테스트로 `14d 표본 부족 -> 30d 확장`, `reviewable`, `candidate 생성` 동작을 검증했다.
  - OCI 운영에서 `strategy_feedback_report.sh 7 14 30` / `strategy_feedback_gate.sh 7 14 30`를 실제 실행해 현재 게이트 판정과 보류/폐기 사유를 확보했다.
- 추후 계획:
  1. `21-04` provider cost snapshot 수집 경로를 복구해 비용 gate를 활성화
  2. Discord 주간 리포트 통합은 다음 Phase에서 반영
  3. 자동 적용기/PR 생성기는 승인 후 후속 Phase로 분리

## 6.1 OCI 운영 검증 결과 (2026-03-10)
- 실행 명령:
```bash
bash scripts/ops/strategy_feedback_report.sh 7 14 30
bash scripts/ops/strategy_feedback_gate.sh 7 14 30
```
- 실제 판정:
  - `gate_result=discard`
  - `approval_tier=reviewable`
  - `sell_samples=16`
  - `ai_decisions=544`
  - `bull_rule_pass=0`
- 핵심 수치:
  - `avg_realized_pnl_pct=-0.6369`
  - `profit_factor=0.5807`
  - `max_drawdown_pct=19.7283`
  - `ai_reject_rate_pct=96.875`
  - `llm_cost_usd=0.862175`
  - `llm_cost_delta_pct=null` (`provider_snapshot_count=0`)
- hold 사유:
  - `provider cost snapshot 누락: 비용 reconciliation 보류`
  - `BULL rule_pass 부족: 0건 (최소 5건 필요)`
- discard 사유:
  - `평균 실현 손익률이 0 이하`
  - `Profit Factor가 1.0 미만`
- 해석:
  - 현재 전략 피드백 자동화는 정상적으로 데이터 집계와 게이트 판정을 수행했다.
  - 다만 현 시점 운영 데이터 기준으로는 비용 snapshot 누락과 BULL 표본 부족이 남아 있고, 실현 손익/Profit Factor 자체도 기준 미달이라 변경 제안은 생성되지 않았다.

## 7. 리스크 / 가정 / 미확정 사항
- 리스크:
  - 현재 `max_drawdown_pct`는 포트폴리오 equity curve가 아니라 SELL 시퀀스 기반 MDD proxy다.
  - `21-04` snapshot 누락이 해소되지 않으면 cost gate는 계속 `hold`를 반환할 수 있다.
- 가정:
  - 초기 운영은 Discord 승인 UI 없이 서버 명령 기반 수동 승인으로 진행한다.
- 미확정:
  - Discord/n8n에 `Strategy Feedback` 블록을 어떤 메시지 포맷으로 붙일지는 다음 Phase에서 확정한다.

## 7.1 운영 이슈 메모 (2026-03-10)
- 증상:
  - OCI에서 `scripts/ops/strategy_feedback_report.sh`, `scripts/ops/strategy_feedback_gate.sh` 직접 실행 시 초기에는 `Permission denied`, 이후 `python: command not found`, 그 다음 `ModuleNotFoundError: No module named 'sqlalchemy'`
- 원인:
  - 스크립트 내용은 반영됐지만 git 실행 권한 비트(`+x`)가 누락된 상태로 pull됐다.
  - 추가로 스크립트가 다른 운영 스크립트와 달리 host python을 직접 사용해, bot 이미지에만 설치된 `sqlalchemy` 등 런타임 의존성을 OCI 호스트에서 찾지 못했다.
  - heredoc 파이썬이 읽을 일수 파라미터도 container exec 환경 변수로 명시 주입되지 않았다.
- 조치:
  - repo에서 두 스크립트에 실행 권한을 부여했다.
  - 두 스크립트를 `docker compose exec -T bot python` 패턴으로 전환하고, `REPORT_DAYS/APPROVAL_DAYS/FALLBACK_DAYS/PYTHONPATH=/app`를 container exec 환경 변수로 주입하도록 수정했다.
- 결과:
  - 보정 후 OCI에서 `report`, `gate` 스크립트 모두 정상 실행됐고, 실제 게이트 판정(`discard`, `reviewable`)을 출력했다.
- 임시 우회 명령:
```bash
bash scripts/ops/strategy_feedback_report.sh 7 14 30
bash scripts/ops/strategy_feedback_gate.sh 7 14 30
```
- 관련 트러블슈팅:
  - `docs/troubleshooting/30_strategy_feedback_ops_script_runtime_compatibility.md`

## 8. README / 체크리스트 동기화
- `README.md`:
  - 미반영
  - 사유: `30`은 아직 `done`이 아니고 Phase 1만 구현됨
- `remaining_work_master_checklist.md`:
  - `30` 상태를 `in_progress`로 반영
  - 본 결과 문서와 OCI 런타임 호환성 트러블슈팅 링크를 추가 완료
