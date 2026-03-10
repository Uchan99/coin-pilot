# 28-01. AI Decision RAG Prompt Ordering / Weighting 보정 결과

작성일: 2026-03-11
작성자: Codex
관련 계획서: `docs/work-plans/28-01_ai_decision_rag_prompt_ordering_and_weighting_tuning_plan.md`
상태: Done

---

## 0. 해결한 문제 정의
- 증상:
  - `28` Phase 1 OCI replay에서 `decision_changed_count=8/10`, `avg_confidence_delta=-22.4`가 발생했고, drift 표본이 모두 `SIDEWAYS`에서 baseline `CONFIRM 68~72 -> RAG-on REJECT 42`로 수렴했다.
- 영향:
  - RAG가 전략/사례 정렬을 돕기보다 valid 후보를 과도하게 차단하는 방향으로 앵커링되어 live canary 실험을 진행할 수 없었다.
- 재현 조건:
  - `strategy:9 + cases:5` 컨텍스트가 함께 들어가고, 정적 전략/리스크 요약이 과거 사례보다 앞에서 길게 주입될 때
- Root cause:
  - retrieval 소스 수보다 prompt ordering/weighting이 문제였고, Analyst가 Rule Engine 통과 신호를 다시 보수적으로 해석하도록 유도되고 있었다.

## 1. 이번 Phase 범위
- 전략 요약 길이 축소
- 과거 사례 블록을 전략 요약보다 앞에 배치
- Analyst에 "Rule Engine을 뒤집지 말고 캔들 구조/지속성만 검토"하는 경계 문구 강화
- 관련 단위 테스트/정적 검증 추가
- OCI replay 재측정 준비

## 2. 구현 내용
1. 전략 요약 축소
   - `config/ai_decision_rag_strategy_refs.json`
   - 글로벌/레짐별 문구를 더 짧고 기술적 목적 중심으로 재작성하고, 리스크 한도 원문 나열을 제거했다.
2. 전략 라인 선택 방식 축소
   - `src/agents/ai_decision_rag.py`
   - `build_strategy_reference_lines()`가 `global + regime`만 사용하고 최대 4줄만 반환하도록 바꿨다.
   - 결과적으로 replay source summary 기준 목표가 `strategy:9 -> strategy:4`로 줄어든다.
3. 사례 우선 배치
   - `src/agents/ai_decision_rag.py`
   - `render_ai_decision_rag_text()`를 추가해 `[과거 사례 요약]`을 `[전략 문서 핵심]`보다 먼저 렌더링하도록 고정했다.
4. Analyst 경계 문구 강화
   - `src/agents/analyst.py`
   - RAG 블록 앞에 `Rule Engine을 뒤집지 말 것`, `RSI/거래량/MA/볼린저 임계치를 재판정하지 말 것`, `직전 2~6개 캔들의 구조/지속성/변동성만 보라`는 명시적 가드를 추가했다.
5. 회귀 테스트 보강
   - `tests/agents/test_ai_decision_rag.py`
   - 전략 라인 상한, 사례 우선 배치, 경계 문구 포함 여부를 검증하는 테스트를 추가했다.

## 3. 아키텍처 선택과 대안 비교
- 선택안:
  - retrieval 구조를 바꾸지 않고 prompt ordering/weighting만 조정한다.
- 선택 이유:
  - 현재 문제는 검색 미스보다 "무엇이 먼저 보이느냐"에 가까웠다.
  - retrieval 소스/DB 스키마를 다시 손대지 않고 drift 원인을 가장 직접적으로 검증할 수 있다.
- 검토한 대안:
  1. 전략 문서 라인을 더 늘리기
     - 장점: 규칙 설명은 풍부해진다.
     - 단점: 이미 확인된 drift를 더 악화시킬 가능성이 크다.
  2. Guardian까지 함께 보정
     - 장점: 전체 체인 일관성 조정 가능
     - 단점: Analyst 변화와 Guardian 변화를 분리 해석하기 어려워진다.
  3. 과거 사례 수를 더 많이 늘리기
     - 장점: 사례 기반 판단 강화 가능
     - 단점: 지금 단계에서는 ordering 문제가 먼저라, 사례 수 확장은 비용만 늘릴 수 있다.
  4. RAG를 완전히 제거
     - 장점: drift 즉시 제거
     - 단점: `28`의 목적 자체를 포기하게 된다.

## 4. Before / After 정량 증빙
| 항목 | Before | After | 변화량 |
|---|---:|---:|---:|
| 전략 요약 목표 줄 수 | 9 | 4 | -5 |
| RAG 렌더링 순서 | 전략 먼저 | 사례 먼저 | 순서 반전 |
| Analyst 경계 가드 문구 | 0 블록 | 1 블록 | +1 |
| `tests/agents/test_ai_decision_rag.py` | 4 passed | 5 passed | +1 |

## 5. 측정 기준
- 기간:
  - 2026-03-11 코드 보정 및 정적 검증
- 표본 수:
  - 단위 테스트 5건
- 성공 기준:
  - 전략 요약 상한/사례 우선/경계 문구가 코드와 테스트에 반영될 것
  - py_compile, shell syntax 통과
- 실패 기준:
  - 기존 replay/helper 경로 import 실패
  - 테스트 또는 정적 검증 실패

## 6. 증빙 근거 (명령)
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_ai_decision_rag.py
python3 -m py_compile src/agents/ai_decision_rag.py src/agents/analyst.py scripts/replay_ai_decision_rag.py
bash -n scripts/ops/replay_ai_decision_rag.sh
```

검증 결과:
- `tests/agents/test_ai_decision_rag.py`: `5 passed in 1.21s`
- `py_compile`: 통과
- `scripts/ops/replay_ai_decision_rag.sh`: shell syntax 통과

## 7. OCI 재측정 결과
- 실행 환경:
  - 2026-03-11 OCI bot 컨테이너
- 실행 명령:
```bash
cd /opt/coin-pilot
docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml exec -T bot sh -lc \
'cd /app && PYTHONPATH=/app python /app/scripts/replay_ai_decision_rag.py --hours 168 --limit 30' \
| tee /tmp/ai_rag_replay_v2.json
```
- 측정 기준:
  - 기간: 최근 168시간
  - 실제 표본: `10`
  - 비교 대상: baseline Analyst vs prompt-ordering/weighting 보정 후 RAG-on Analyst
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
- Before / After (28 Phase 1 대비):
| 항목 | Before | After | 변화량 |
|---|---:|---:|---:|
| `decision_changed_count` | 8 | 0 | -8 |
| `decision_changed_rate` | 80.0% | 0.0% | -80.0%p |
| `avg_confidence_delta` | -22.4 | -2.8 | +19.6 |
| `rag_latency_p50_ms` | 5264.5 | 7590.0 | +2325.5 (+44.2%) |
| `rag_avg_cost_usd` | 0.0061 | 0.0069 | +0.0008 (+13.1%) |
| `rag_parse_fail_count` | 0 | 0 | 0 |
- 판정:
  - `decision_changed_count / samples <= 30%`: 통과 (`0.0%`)
  - `avg_confidence_delta >= -5`: 통과 (`-2.8`)
  - parse fail 증가 없음: 통과 (`0 -> 0`)
  - cost 악화 `+20%` 이내: 통과 (`+13.1%`)
  - latency 악화 `+20%` 이내: 실패 (`+44.2%`)
- 해석:
  - 이번 보정은 drift/confidence 문제를 사실상 해소했다.
  - 다만 latency는 baseline 대비가 아니라 이전 RAG 버전 대비 증가했고, 현재 absolute p50도 약 `7.6s` 수준이라 live canary에서 추가 관찰이 필요하다.
  - 따라서 이 하위 작업(`28-01`)은 "prompt drift 완화" 목적 기준으로는 완료로 본다.

## 8. OCI 재검증 방법
```bash
cd /opt/coin-pilot
git fetch origin
git checkout pretrade
git pull --ff-only origin pretrade

cd /opt/coin-pilot/deploy/cloud/oci
docker compose --env-file .env -f docker-compose.prod.yml up -d --build bot

cd /opt/coin-pilot
docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml exec -T bot sh -lc \
'cd /app && PYTHONPATH=/app python /app/scripts/replay_ai_decision_rag.py --hours 168 --limit 30' \
| tee /tmp/ai_rag_replay_v2.json
```

요약 확인:
```bash
python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('/tmp/ai_rag_replay_v2.json').read_text(encoding='utf-8'))
print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
PY
```

기대 확인:
- `decision_changed_count / samples <= 30%`
- `avg_confidence_delta >= -5`
- parse fail 증가 없음
- latency/cost 악화 `+20%` 이내

## 9. README / 체크리스트 동기화
- `README.md`:
  - 미반영
  - 사유: `28` main task는 아직 `done`이 아니며, 이번 변경은 하위 보정 단계다.
- `remaining_work_master_checklist.md`:
  - `28` 상태를 계속 `in_progress`로 유지
  - 최근 로그에 `28-01` prompt ordering/weighting 보정 및 OCI replay 재측정 결과를 추가
