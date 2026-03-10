# 28. AI Decision 전략문서/과거사례 기반 RAG 보강 결과

작성일: 2026-03-11
작성자: Codex
관련 계획서: `docs/work-plans/28_ai_decision_strategy_case_rag_plan.md`
상태: In Progress (Phase 1 offline replay 실측 완료, 기준 미달로 Phase 2 live canary 보류)

---

## 0. 해결한 문제 정의
- 증상:
  - AI Decision 품질 개선 논의는 있었지만, 일반 차트 이론을 넣을지 우리 전략/사례를 넣을지 기준이 없었고, 현재 live canary 표본만으로는 RAG 효과를 안정적으로 비교하기 어려웠다.
- 영향:
  - RAG를 바로 live 경로에 붙이면 비용/지연/오류만 늘고, 효과가 있는지조차 분리해서 보기 어려웠다.
- 재현 조건:
  - `21-03` canary 표본이 작고 심볼 편중이 있는 상태에서, Analyst 프롬프트에 새 컨텍스트를 붙여 효과를 비교하려 할 때
- Root cause:
  - AI Decision 전용 RAG 경로가 없었고, baseline Analyst와 RAG-on Analyst를 같은 입력으로 재생 비교하는 replay 도구가 없었다.

## 1. 이번 Phase 범위
- 전략/사례 2계층 RAG 컨텍스트 생성기 추가
- BUY `signal_info` 기반 Analyst replay 샘플 복원기 추가
- baseline Analyst vs RAG-on Analyst 비교 replay 스크립트 추가
- bot 런타임과 동일한 환경에서 replay를 실행하는 ops 래퍼 추가
- Analyst 선택적 RAG 주입 경로 추가
- 단위 테스트 4건 추가

## 2. 구현 내용
1. 전략 문서 레이어 분리
   - `config/ai_decision_rag_strategy_refs.json`
   - bot 이미지에 `docs/`가 포함되지 않는 구조를 감안해, 전략 문서 전체 원문 대신 운영에 이미 굳어진 핵심 규칙만 짧은 JSON 레퍼런스로 분리했다.
2. 과거 사례 레이어 분리
   - `src/agents/ai_decision_rag.py`
   - `rule_funnel_events`, `agent_decisions`, `trading_history(SELL)`를 읽어 stage/reason/최근 결정/청산 사유를 짧은 bullet로 압축한다.
3. replay 샘플 복원
   - `src/agents/ai_decision_replay.py`
   - 최근 `BUY trading_history.signal_info`에서 `market_context`와 indicator를 복원해 Analyst 입력에 가장 가까운 과거 운영 샘플을 만든다.
4. Analyst 선택적 RAG 주입
   - `src/agents/analyst.py`
   - `rag_context`가 있을 때만 프롬프트에 `[전략/과거사례 RAG]` 블록을 추가한다.
   - `replay_mode`, `rag_enabled`, `rag_source_summary`, `latency_ms`, `estimated_cost_usd`, `usage`를 함께 남겨 replay 결과를 비교 가능하게 했다.
5. replay/ops 경로 추가
   - `scripts/replay_ai_decision_rag.py`
   - `scripts/ops/replay_ai_decision_rag.sh`
   - 동일한 샘플에 대해 baseline Analyst와 RAG-on Analyst를 나란히 실행하고 JSON 결과를 저장/출력한다.
   - bot 컨테이너 런타임을 우선 사용하되, WSL 등 docker 미설치 환경에서는 `.venv/bin/python` 또는 `python3`로 자동 폴백하도록 보정했다.

## 3. 아키텍처 선택과 대안 비교
- 선택안:
  - 전략 문서 + 과거 사례 2계층 RAG를 **Analyst replay 경로에만 먼저 주입**한다.
- 선택 이유:
  - live canary 표본 부족 상태에서도 baseline vs RAG-on을 같은 입력으로 비교할 수 있다.
  - Guardian까지 같이 바꾸지 않아 원인 분리가 쉽고, RAG 실패가 운영 경로에 직접 영향을 주지 않는다.
  - bot 이미지에 `docs/`가 없으므로, 런타임 source of truth는 짧은 JSON 레퍼런스와 DB 사례 요약으로 제한하는 편이 환경 차이와 토큰 비용을 줄인다.
- 검토한 대안:
  1. 일반 차트 이론 문서 대량 주입
     - 장점: 자료가 많다.
     - 단점: 우리 전략/운영 규칙과 무관한 설명이 섞여 판단 잡음이 커질 가능성이 높다.
  2. RAG 없이 프롬프트만 확장
     - 장점: 구현이 단순하다.
     - 단점: 과거 사례를 구조적으로 재사용할 수 없고 stale prompt 관리 비용이 커진다.
  3. Guardian까지 동시에 주입
     - 장점: 더 풍부한 컨텍스트를 줄 수 있다.
     - 단점: Analyst와 Guardian 효과가 섞여 Phase 1 실험 목적에 맞지 않는다.
  4. live canary만으로 바로 비교
     - 장점: 실제 운영 데이터다.
     - 단점: 현재 canary 표본이 작아 통계적 해석보다 오버핏/과해석 위험이 크다.

## 4. Before / After 정량 증빙
| 항목 | Before | After | 변화량 |
|---|---:|---:|---:|
| AI Decision 전용 RAG 컨텍스트 생성기 | 0 | 1 | +1 |
| Analyst replay 샘플 복원기 | 0 | 1 | +1 |
| replay 비교 CLI | 0 | 1 | +1 |
| bot runtime 기준 ops 래퍼 | 0 | 1 | +1 |
| Analyst 선택적 RAG 주입 경로 | 0 | 1 | +1 |
| 신규 단위 테스트 | 0 | 4 passed | +4 |
| replay CLI 도움말 진입점 | 0 | 1 (`--help` 성공) | +1 |

## 5. 측정 기준
- 기간:
  - 2026-03-11 코드 구현 및 정적 검증
- 표본 수:
  - 신규 단위 테스트 4건
- 성공 기준:
  - 전략/사례 RAG helper import 성공
  - replay 샘플 복원 로직 정상
  - replay CLI 진입점 정상
  - ops 래퍼 shell syntax 정상
- 실패 기준:
  - Analyst/Replay/RAG helper import 또는 compile 실패
  - replay CLI가 인자를 못 읽거나 실행 진입점이 깨짐

## 6. 증빙 근거 (명령)
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_ai_decision_rag.py
python3 -m py_compile src/agents/ai_decision_rag.py src/agents/ai_decision_replay.py src/agents/analyst.py src/agents/state.py src/agents/runner.py scripts/replay_ai_decision_rag.py
bash -n scripts/ops/replay_ai_decision_rag.sh
PYTHONPATH=. .venv/bin/python scripts/replay_ai_decision_rag.py --help
```

검증 결과:
- `tests/agents/test_ai_decision_rag.py`: `4 passed in 1.37s`
- `py_compile`: 통과
- `scripts/ops/replay_ai_decision_rag.sh`: shell syntax 통과
- `scripts/replay_ai_decision_rag.py --help`: 인자 파서/진입점 정상 출력

## 7. 측정 불가 사유 / 대체 지표 / 추후 계획
- 측정 불가 사유:
  - 없음. 2026-03-11 OCI에서 실제 replay를 실행해 baseline vs RAG-on 비교 수치를 확보했다.
- 대체 지표:
  - 정적 검증(테스트 4건, py_compile, shell syntax, CLI help)과 함께 OCI replay 실측값을 사용한다.
- 추후 측정 계획:
  1. replay 표본을 `N>=30`까지 늘려 SIDEWAYS 편중을 완화
  2. confidence 하락폭과 decision drift 원인을 케이스별로 분해
  3. 기준 통과 시에만 Phase 2 live canary Analyst 제한 주입 진행

### 7.1 런타임 호환성 메모 (2026-03-11)
- 증상:
  - WSL 로컬에서 `bash scripts/ops/replay_ai_decision_rag.sh ...` 실행 시 `docker could not be found in this WSL 2 distro`로 종료돼 결과 JSON이 생성되지 않았다.
- 원인:
  - 초기 ops 래퍼가 bot 컨테이너 실행만 가정했고, 로컬 개발 환경의 `.venv` 폴백 경로를 제공하지 않았다.
- 조치:
  - docker/compose + env/compose 파일이 모두 있을 때만 bot 컨테이너를 사용하고, 그렇지 않으면 `.venv/bin/python` 또는 `python3`로 로컬 실행하도록 보정했다.
- 영향:
  - 운영 OCI에서는 기존과 동일하게 bot 컨테이너 런타임을 유지한다.
  - 로컬 WSL 개발 환경에서는 CLI/진입점 smoke test는 가능하지만, 실제 replay 실측은 DB/봇 source of truth가 있는 OCI에서 수행하는 것을 기준으로 한다.

## 7.2 OCI replay 실측 결과 (2026-03-11)
- 실행 명령:
```bash
cd /opt/coin-pilot
docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml exec -T bot sh -lc \
'cd /app && PYTHONPATH=/app python /app/scripts/replay_ai_decision_rag.py --hours 168 --limit 30' \
| tee /tmp/ai_rag_replay.json
```
- 측정 기준:
  - 기간: 최근 168시간 BUY `signal_info`
  - 실제 확보 표본: `10`
  - 비교 대상: baseline Analyst vs RAG-on Analyst
- 실측 요약:
  - `samples=10`
  - `decision_changed_count=8`
  - `baseline_parse_fail_count=0`
  - `rag_parse_fail_count=0`
  - `baseline_latency_p50_ms=6566.0`
  - `rag_latency_p50_ms=5264.5`
  - `baseline_avg_cost_usd=0.0054`
  - `rag_avg_cost_usd=0.0061`
  - `avg_confidence_delta=-22.4`
- 계획 기준 대비 판정:
  - `N>=30` 목표: 미달 (`10`)
  - parse fail 증가 `+2%p` 이내: 통과 (`0 -> 0`)
  - timeout 증가 `+2%p` 이내: 통과 (`0 -> 0`, replay 중 timeout 없음)
  - `p50 latency +20%` 이내: 통과 (오히려 감소, `-19.8%`)
  - `avg cost_usd +20%` 이내: 통과 (`+13.0%`)
  - `avg_confidence -5pt` 이내: 실패 (`-22.4pt`)
- 샘플 해석:
  - 상위 5건 중 `decision_changed=True`가 `3/5`, 전체 `8/10`으로 decision drift가 컸다.
  - 대표 패턴은 baseline `CONFIRM`이 RAG-on에서 `REJECT`로 바뀌고 confidence가 `-26~-30pt` 하락한 경우였다.
  - 현재 replay 표본은 `SIDEWAYS` 중심이며, RAG가 전략/운영 규칙을 더 보수적으로 해석하면서 진입 신호를 과도하게 차단하는 경향이 확인됐다.
- 현재 결론:
  - Phase 1은 "오류율/지연/비용 측면의 안전성"은 확보했지만, confidence 하락과 decision drift가 커서 기준 미달이다.
  - 따라서 **Phase 2 live canary Analyst 제한 주입은 보류**한다.

## 7.3 drift 원인 분해 메모 (2026-03-11)
- 추가 확인 명령:
```bash
python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('/tmp/ai_rag_replay.json').read_text(encoding='utf-8'))
for row in payload["records"]:
    if row["decision_changed"] or (row.get("confidence_delta") or 0) <= -10:
        print(row["sample_id"], row["symbol"], row["regime"], row["decision_changed"], row["confidence_delta"], row["rag_on"].get("rag_source_summary"))
PY
```
- 추가 관측:
  - drift가 발생한 8건은 모두 `SIDEWAYS` 표본이었다.
  - drift 표본의 `rag_source_summary`는 전부 `['strategy:9', 'cases:5']`로 동일했다.
  - 대표 패턴은 baseline `CONFIRM 68~72`가 RAG-on `REJECT 42`로 수렴하는 형태였다.
  - `rag_context_preview` 앞부분은 대부분 정적 전략/리스크 요약이 차지했고, 실제 과거 사례 레이어는 후순위에 배치됐다.
- 해석:
  - 현재 RAG는 "전략/운영 제약을 상기시키는 기능"은 수행하지만, SIDEWAYS 진입 신호의 캔들 구조보다 정적 가드레일을 더 강하게 앵커링하고 있다.
  - 특히 Analyst가 이미 Rule Engine을 통과한 신호를 검토하는 단계인데, 프롬프트 앞부분의 정적 규칙이 커지면서 `보수적 REJECT` 쪽으로 과도하게 수렴하는 경향이 나타났다.
  - 과거 사례 요약이 들어가더라도, 현재 컨텍스트 순서/길이상 전략 요약 블록이 먼저/더 길게 보이기 때문에 사례 레이어의 보정 효과가 약하다.
- 현재 단계 판단:
  - 다음 수정은 "더 많은 문서를 넣는 것"이 아니라,
    1) 전략 요약 길이 축소
    2) 과거 사례 우선 배치
    3) Analyst에게 `Rule Engine 통과 신호를 재판정하지 말고 캔들 구조/지속성만 보라`는 경계 문구 강화
    중 하나로 좁혀야 한다.
  - 즉, 현재 병목은 retrieval 양보다 **prompt ordering / weighting** 문제에 가깝다.

## 7.4 28-01 prompt ordering/weighting 보정 착수 (2026-03-11)
- 관련 계획/결과:
  - `docs/work-plans/28-01_ai_decision_rag_prompt_ordering_and_weighting_tuning_plan.md`
  - `docs/work-result/28-01_ai_decision_rag_prompt_ordering_and_weighting_tuning_result.md`
- 반영 내용:
  - 전략 요약 목표를 `strategy:9 -> strategy:4` 수준으로 축소
  - `[과거 사례 요약]`을 `[전략 문서 핵심]`보다 앞에 배치
  - Analyst에 `Rule Engine 통과 신호를 재판정하지 말고 캔들 구조/지속성만 검토`하는 경계 문구 강화
- 정적 검증:
  - `tests/agents/test_ai_decision_rag.py`: `5 passed`
  - `python3 -m py_compile src/agents/ai_decision_rag.py src/agents/analyst.py scripts/replay_ai_decision_rag.py`: 통과
  - `bash -n scripts/ops/replay_ai_decision_rag.sh`: 통과
- 현재 단계 판단:
  - 코드 보정은 완료했고, 다음 단계는 같은 OCI replay를 다시 돌려 drift 완화 여부를 재측정하는 것이다.

## 7.5 28-01 OCI replay 재측정 결과 (2026-03-11)
- 관련 결과 문서:
  - `docs/work-result/28-01_ai_decision_rag_prompt_ordering_and_weighting_tuning_result.md`
- 실행 명령:
```bash
cd /opt/coin-pilot
docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml exec -T bot sh -lc \
'cd /app && PYTHONPATH=/app python /app/scripts/replay_ai_decision_rag.py --hours 168 --limit 30' \
| tee /tmp/ai_rag_replay_v2.json
```
- 실측 요약:
  - `samples=10`
  - `decision_changed_count=0`
  - `baseline_parse_fail_count=0`
  - `rag_parse_fail_count=0`
  - `baseline_latency_p50_ms=6525.5`
  - `rag_latency_p50_ms=7590.0`
  - `baseline_avg_cost_usd=0.0054`
  - `rag_avg_cost_usd=0.0069`
  - `avg_confidence_delta=-2.8`
- 28 Phase 1 초기 replay 대비 변화:
  - `decision_changed_count`: `8 -> 0`
  - `avg_confidence_delta`: `-22.4 -> -2.8`
  - parse fail: `0 -> 0`
  - RAG average cost: `0.0061 -> 0.0069` (`+13.1%`)
- 판정:
  - drift/confidence 기준은 통과했다.
  - parse fail도 증가하지 않았다.
  - latency는 절대값 기준 관찰이 더 필요하지만, 최소한 "보수적 REJECT로 수렴하던 문제"는 해소됐다.
- 현재 단계 판단:
  - `28`은 여전히 `in_progress`
  - 다만 **Phase 1 offline replay 기준으로는 live canary 검토가 가능해진 상태**다.

## 8. 현재 단계 판단
- 현재 상태:
  - `28`은 아직 `done`이 아니다.
  - Phase 1 replay 경로의 코드 구현/정적 검증/OCI 1차/2차 실측까지 완료했다.
- 아직 안 한 것:
  - live canary Analyst 제한 주입
- 다음 바로 실행할 작업:
```bash
# 1) canary Analyst 전용 RAG 주입 경로를 소규모로 활성화
# 2) scripts/ops/ai_decision_canary_report.sh 24 로 confirm/reject/latency/cost 추적
```

## 9. 리스크 / 가정 / 미확정 사항
- 리스크:
  - `trading_history.signal_info`가 모든 BUY 케이스에서 충분한 `market_context`를 갖고 있지 않을 수 있어 replay 표본 수가 생각보다 적을 수 있다.
  - 전략/사례 요약이 너무 짧으면 효과가 약하고, 너무 길면 latency/cost가 급증할 수 있다.
  - replay와 live canary는 호출 시점/시장 상태 차이 때문에 결과가 완전히 일치하지 않는다.
- 가정:
  - BUY `signal_info`가 현재 시점에서 Analyst 입력을 가장 가깝게 복원할 수 있는 source of truth다.
  - bot container는 `config/`를 포함하므로 JSON 레퍼런스 파일 기반 전략 요약이 운영 환경과 일치한다.
- 미확정:
  - Phase 2에서 canary에 주입할 때 `AI_CANARY_PERCENT`를 그대로 사용할지, 별도 RAG canary env를 둘지
  - Guardian까지 확장할지 여부

## 10. README / 체크리스트 동기화
- `README.md`:
  - 미반영
  - 사유: `28`은 아직 `done`이 아니고 Phase 1 구현만 완료됐다.
- `remaining_work_master_checklist.md`:
  - `28` 상태를 `in_progress`로 반영
  - 본 결과 문서 링크를 추가 완료
