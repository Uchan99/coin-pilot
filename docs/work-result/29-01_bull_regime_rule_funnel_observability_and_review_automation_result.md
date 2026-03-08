# 29-01. BULL 레짐 Rule Funnel 관측성 강화 + 주기 점검 자동화 결과

**작성일**: 2026-03-08  
**작성자**: Codex  
**상태**: In Progress (Phase 1 로컬 구현 + OCI 운영 적재 확인 완료)  
**관련 계획서**: `docs/work-plans/29-01_bull_regime_rule_funnel_observability_and_review_automation_plan.md`

---

## 0. 해결한 문제 정의
- 증상:
  - 운영에서 "BULL 레짐인데 AI decision이 적다"는 관측이 있었지만, 기존 DB에는 `agent_decisions`만 있어 Rule pass 이후 어느 단계에서 병목이 생기는지 분해할 수 없었다.
- 영향:
  - BULL 진입 부족의 원인을 Rule/Risk/AI 중 어디서 찾을지 불명확했고, 29번 전략 판단 이후 후속 핫픽스/튜닝 근거가 약했다.
- 재현 조건:
  - 레짐 노출은 BULL 우세인데 실제 AI decision 건수는 SIDEWAYS 중심으로 보이는 구간
- Root cause:
  - 레짐별 Rule funnel 이벤트 스키마, 런타임 계측 훅, 주간 리포트 통합 경로가 부재했다.

## 1. 이번 Phase 범위
- 신규 퍼널 이벤트 스키마 추가:
  - `rule_funnel_events`
- 런타임 계측 추가:
  - `rule_pass`
  - `risk_reject`
  - `ai_prefilter_reject`
  - `ai_guardrail_block`
  - `ai_confirm`
  - `ai_reject`
- 운영 리포트 추가:
  - `scripts/ops/rule_funnel_regime_report.sh <hours>`
- 기존 Weekly Exit Report 증분 확장:
  - payload에 `rule_funnel`, `rule_funnel_suggestions` 추가
- 자동 수정:
  - 미구현, 금지 정책 유지

## 2. 구현 내용
1. DB/모델
   - `src/common/models.py`에 `RuleFunnelEvent` 추가
   - `migrations/v3_3_4_rule_funnel_events.sql` 추가
   - `deploy/db/init.sql`에 baseline 생성 SQL 반영
2. 런타임 계측
   - `src/bot/main.py`:
     - Entry signal 시 `rule_pass`
     - 주문 금액 0 또는 리스크 검증 실패 시 `risk_reject`
     - AI prefilter 차단 시 `ai_prefilter_reject`
     - AI guardrail 차단 시 `ai_guardrail_block`
   - `src/agents/runner.py`:
     - 최종 AI decision 시 `ai_confirm` / `ai_reject`
3. 공용 계층
   - `src/common/rule_funnel.py`:
     - reason 문자열을 집계 가능한 `reason_code`로 정규화
     - 관측 실패가 주문 흐름을 멈추지 않도록 soft-fail 처리
   - `src/analytics/rule_funnel.py`:
     - 기간별 레짐/단계 집계
     - BULL 기준 자동 제안 생성(자동 수정 아님)
4. 운영 리포트
   - `scripts/ops/rule_funnel_regime_report.sh`
   - `src/analytics/exit_performance.py`에서 주간 payload에 funnel 요약/제안 증분 통합
5. 운영 문서
   - `docs/runbooks/18_data_migration_runbook.md`에 신규 migration 적용 순서 반영

## 3. Before / After 정량 증빙
| 항목 | Before | After | 변화량 |
|---|---:|---:|---:|
| 레짐별 퍼널 DB stage 수 | 0 | 6 | +6 |
| 주간 리포트 내 퍼널 필드 수 | 0 | 2 (`rule_funnel`, `rule_funnel_suggestions`) | +2 |
| 신규 운영 리포트 스크립트 수 | 0 | 1 | +1 |
| 신규/확장 로컬 검증 테스트 | 0 | 6 passed | +6 |
| OCI 운영 `rule_funnel_events` 누적 row | 0 | 4 | +4 |
| OCI 운영 레짐/단계 집계 | 0 | `SIDEWAYS: rule_pass=2, risk_reject=2` | 신규 확인 |

## 4. 측정 기준
- 기간:
  - 로컬 구현 검증 + OCI 운영 확인 시점 2026-03-08 단일 실행
- 표본 수:
  - 테스트 6건
    - `tests/analytics/test_rule_funnel.py`
    - `tests/analytics/test_exit_performance_phase3.py`
    - `tests/analytics/test_exit_performance_phase4.py`
  - OCI 운영 이벤트 4건
    - `KRW-SOL` 2건 (`rule_pass`, `risk_reject`)
    - `KRW-BTC` 2건 (`rule_pass`, `risk_reject`)
- 성공 기준:
  - 신규 모듈 문법 오류 없음
  - 퍼널 제안/주간 payload 테스트 통과
  - 운영 스크립트 쉘 구문 오류 없음
- 실패 기준:
  - 기존 AI decision 흐름 import/compile 실패
  - 주간 payload 확장으로 테스트 회귀 발생

## 5. 증빙 근거 (명령)
```bash
python3 -m py_compile src/common/models.py src/common/rule_funnel.py src/analytics/rule_funnel.py src/analytics/exit_performance.py src/agents/runner.py src/bot/main.py
PYTHONPATH=. .venv/bin/pytest -q tests/analytics/test_rule_funnel.py tests/analytics/test_exit_performance_phase3.py tests/analytics/test_exit_performance_phase4.py
bash -n scripts/ops/rule_funnel_regime_report.sh
```

OCI 운영 확인:
```bash
cd /opt/coin-pilot/deploy/cloud/oci
docker compose --env-file .env -f docker-compose.prod.yml up -d --build bot
cd /opt/coin-pilot
docker exec -i -u postgres coinpilot-db psql -d coinpilot < /opt/coin-pilot/migrations/v3_3_4_rule_funnel_events.sql
scripts/ops/rule_funnel_regime_report.sh 24
docker exec -u postgres coinpilot-db psql -d coinpilot -c "
SELECT created_at, symbol, regime, stage, result, reason_code
FROM rule_funnel_events
ORDER BY created_at DESC
LIMIT 20;
"
```

OCI 운영 결과:
- `coinpilot-bot` 재빌드/재기동 후 봇 루프/스케줄러 정상 시작 확인
- `rule_funnel_events` 적재 4건 확인
  - `2026-03-08 13:09:19+00` / `KRW-SOL` / `SIDEWAYS` / `rule_pass`
  - `2026-03-08 13:09:19+00` / `KRW-SOL` / `SIDEWAYS` / `risk_reject`
  - `2026-03-08 13:11:19+00` / `KRW-BTC` / `SIDEWAYS` / `rule_pass`
  - `2026-03-08 13:11:19+00` / `KRW-BTC` / `SIDEWAYS` / `risk_reject`
- `scripts/ops/rule_funnel_regime_report.sh 24` 출력:
  - `SIDEWAYS rule_pass=2`
  - `SIDEWAYS risk_reject=2`
  - `ai_prefilter_reject/ai_guardrail_block/ai_confirm/ai_reject = 0`
- 로그 근거:
  - `KRW-SOL Entry Signal Detected`
  - `단일 주문 한도(20.0%) 초과`로 주문 스킵
- 주간 리포트 수동 실행 확인:
  - `docker compose --env-file .env -f docker-compose.prod.yml exec -T bot sh -lc 'cd /app && PYTHONPATH=. python -c "import asyncio; from src.bot.main import weekly_exit_report_job; asyncio.run(weekly_exit_report_job())"'`
  - 결과: `[Scheduler] Weekly Exit Report sent successfully.`
  - Discord 실제 수신 확인 완료
  - 단, 당시 Discord 포맷은 기존 `title/period/SELL/summary/suggestions`만 출력했고 `rule_funnel`, `rule_funnel_suggestions`는 노출하지 않았다.

추가 확인:
```bash
timeout 20s env PYTHONPATH=. .venv/bin/pytest -q tests/test_agents.py -vv -s
```
- 결과:
  - `test_agent_runner_confirm_scenario`, `test_agent_runner_low_confidence_rejection` 통과 확인
  - `test_agent_runner_timeout_fallback`은 기존 40초 timeout 대기 특성 때문에 20초 제한에서 중단

## 6. 측정 불가 사유 / 대체 지표 / 추후 계획
- 측정 불가 사유:
  - 아직 BULL 표본과 AI 단계(`ai_confirm`/`ai_reject`) 운영 데이터가 확보되지 않아 "왜 BULL에서 AI decision이 적은지"에 대한 최종 병목 결론은 아직 낼 수 없다.
- 대체 지표:
  - 2026-03-09 기준 72시간 운영 집계에서 `SIDEWAYS rule_pass=12`, `SIDEWAYS risk_reject=12`, `BULL=0`, `AI stage=0`을 확인했다.
  - 세부 원인은 `max_per_order=6`, `risk_other=6`이며, `risk_other`는 패치 전 legacy row다.
- 추후 측정 계획:
  1. `scripts/ops/rule_funnel_regime_report.sh 72`를 반복 실행해 BULL 표본 확보
  2. 최근 72시간 BULL/SIDEWAYS 레짐별 `rule_pass -> ai_confirm` 전환율 비교
  3. 현재 `risk_other`로 잡힌 `단일 주문 한도 초과` reason을 다음 소규모 패치에서 세분화(`max_per_order`) 검토
  4. 주간 webhook payload에 funnel 섹션이 포함되는지 실제 운영 로그로 확인

### 6.1 BULL 표본 재확인 메모 (보류 조건)
- 현재 판정:
  - 2026-03-09 기준 최근 72시간에 `BULL` row가 0건이므로, `29-01`의 "BULL에서 왜 AI decision이 적은가" 최종 해석은 보류한다.
- 재개 조건:
  - `rule_funnel_events`에 `regime='BULL'` 표본이 1건 이상 누적될 때
- 재확인 명령:
```bash
docker exec -u postgres coinpilot-db psql -d coinpilot -c "
SELECT regime, stage, reason_code, count(*)
FROM rule_funnel_events
WHERE created_at >= now() - interval '72 hours'
GROUP BY 1,2,3
ORDER BY 1,2,3;
"

docker exec -u postgres coinpilot-db psql -d coinpilot -c "
SELECT
  symbol,
  regime,
  stage,
  reason_code,
  count(*) AS cnt
FROM rule_funnel_events
WHERE created_at >= now() - interval '72 hours'
GROUP BY 1,2,3,4
ORDER BY cnt DESC, symbol, regime, stage, reason_code;
"

docker exec -u postgres coinpilot-db psql -d coinpilot -c "
SELECT
  created_at,
  symbol,
  regime,
  stage,
  result,
  reason_code,
  reason
FROM rule_funnel_events
WHERE created_at >= now() - interval '72 hours'
  AND regime = 'BULL'
ORDER BY created_at DESC;
"
```
- 기대 체크:
  - `BULL rule_pass > 0`
  - `BULL risk_reject / ai_prefilter_reject / ai_guardrail_block / ai_confirm / ai_reject` 중 어느 단계가 실제 병목인지 식별 가능

## 7. 리스크 / 가정 / 미확정 사항
- 리스크:
  - 퍼널 이벤트가 현재는 "이벤트 로그"이므로, 장시간 운영 전에는 write volume 증가량을 실제 OCI에서 확인해야 한다.
  - 현재 `단일 주문 한도(20.0%) 초과` 메시지가 `reason_code=risk_other`로 분류돼, risk 병목 세부 원인 해상도는 아직 부족하다.
- 가정:
  - n8n/Discord weekly webhook은 payload의 신규 필드를 무시하지 않고 그대로 전달 가능하다고 가정했다.
- 미확정:
  - `31` 작업에서 cron/systemd 보조 점검을 어떤 경로로 얹을지는 아직 미확정이다.

## 8. README / 체크리스트 동기화
- `README.md`:
  - 미반영
  - 사유: `29-01`은 아직 `done`이 아니고 Phase 1 구현만 완료되어 README 동기화 조건(major completed)에 해당하지 않음
- `remaining_work_master_checklist.md`:
  - `29-01` 상태를 `in_progress`로 반영
  - 본 결과 문서 링크를 추가 완료

## 8.1 Weekly Exit Report 포맷 보정 메모 (2026-03-09)
- 확인 결과:
  - `weekly_exit_report_job` 실행과 Discord 수신은 성공했다.
  - 그러나 n8n `weekly-exit-report` workflow 템플릿은 여전히 `summary/suggestions`만 출력하고 있어,
    repo에서 추가한 `rule_funnel`, `rule_funnel_suggestions`는 Discord 메시지에 보이지 않았다.
- 조치:
  - `config/n8n_workflows/weekly-exit-report-workflow.json`에 Rule Funnel 섹션과 Rule Funnel 제안 섹션을 추가했다.
  - 1차 시도에서는 `description`에 Rule Funnel 내용을 직접 이어붙였으나, n8n `Send Discord Message` 노드/Discord 400 응답이 발생했다.
  - 2차 보정으로는 사용 중인 Weekly Exit Report workflow의 기존 형식(`jsonBody = {{ { \"embeds\": [...] } }}`)을 유지하고, 기존 `기간/SELL 샘플/요약` description은 그대로 둔 채 `제안`, `Rule Funnel`, `Rule Funnel 제안`만 embed `fields`로 추가했다.
- 정량 상태:
  - webhook 전송 성공: `1/1`
  - Discord 수신 성공: `2/2`
  - Rule Funnel 표시: before `0/1`, after `1/1`
  - 실제 표시된 운영 값:
    - `SIDEWAYS: rule_pass=21, risk_reject=21, prefilter=0, guardrail=0, ai_confirm=0, ai_reject=0`
    - `BULL 퍼널 데이터 부족: rule_pass 0건 (최소 5건 필요)`
- 후속 운영 확인 명령:
```bash
cd /opt/coin-pilot/deploy/cloud/oci
docker compose --env-file .env -f docker-compose.prod.yml logs --since=5m bot
docker compose --env-file .env -f docker-compose.prod.yml logs --since=5m n8n
```
- 주의:
  - n8n workflow JSON 템플릿 변경은 repo 반영만으로 운영 UI 상태가 자동 갱신되지 않을 수 있으므로,
    OCI n8n UI에 workflow import/수동 반영 후 Active 상태를 다시 확인해야 한다.
  - 2026-03-09 01:04 KST 수동 실행에서는 Discord 메시지에 `제안`, `Rule Funnel`, `Rule Funnel 제안` 3개 필드가 실제 표시되는 것을 확인했다.

## 8.2 현재 단계 판정 (2026-03-09)
- 구현/운영 검증 완료 항목:
  1. `rule_funnel_events` 스키마/런타임 계측 반영
  2. OCI 운영 적재 확인
  3. `risk_reject` reason 세분화(`max_per_order`) 확인
  4. Weekly Exit Report Discord 노출 확인
- 남은 항목:
  - `BULL` 표본 확보
  - `ai_prefilter_reject` / `ai_guardrail_block` / `ai_confirm` / `ai_reject` 운영 표본 확보
- 해석:
  - 현재 `29-01`은 추가 구현보다 운영 관측이 남은 상태다.
  - 따라서 본 스트림은 `in_progress`를 유지하되, 신규 구현 포커스는 다음 우선순위 작업(`30`)으로 이동 가능하다.
- 정량 근거:
  - 최근 72시간 Rule Funnel:
    - `SIDEWAYS rule_pass=21`
    - `SIDEWAYS risk_reject=21`
    - `BULL=0`
    - `AI stage=0`
  - Weekly Exit Report Discord 표시:
    - before `0/1`
    - after `1/1`

## 9. Phase 1.1 후속 보정 (2026-03-08)
- 문제:
  - OCI 운영 검증에서 `단일 주문 한도(20.0%) 초과`가 `reason_code=risk_other`로 분류돼, 리스크 병목 원인 해상도가 낮았다.
- 개선:
  - `src/common/rule_funnel.py`의 `risk_reject` 분류를 세분화했다.
  - 신규 세분화 코드:
    - `max_per_order`
    - `max_total_exposure`
    - `cash_cap`
    - `max_positions`
    - `duplicate_position`
    - `risk_cooldown`
- 정량 변화:
  - before: `단일 주문 한도 초과 -> risk_other`
  - after: `단일 주문 한도 초과 -> max_per_order`
- 증빙:
```bash
python3 -m py_compile src/common/rule_funnel.py
PYTHONPATH=. .venv/bin/pytest -q tests/analytics/test_rule_funnel.py tests/analytics/test_exit_performance_phase4.py
```
- 결과:
  - 4 passed
- 후속 확인 계획:
  - 다음 OCI 이벤트부터 `risk_other` 대신 `max_per_order`로 적재되는지 `scripts/ops/rule_funnel_regime_report.sh 24`로 재확인
