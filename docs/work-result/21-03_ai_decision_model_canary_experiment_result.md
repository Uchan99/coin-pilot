# 21-03. AI Decision 모델 카나리 실험(haiku ↔ gpt-4o-mini) 구현 결과

작성일: 2026-03-04
작성자: Codex
관련 계획서: `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`
상태: Partial
완료 범위: Phase 1 (카나리 라우팅/기록/리포트 자동화)
선반영/추가 구현: 있음(Phase 1 전부)
관련 트러블슈팅(있다면): `docs/troubleshooting/21-06_ai_canary_env_injection_and_observability_gap.md`

---

## 1. 개요
- 구현 범위 요약:
  - Analyst/Guardian 경로에 provider/model 카나리 라우팅 추가
  - 라우팅 결과를 실행 상태에 공유하고 DB `model_used`에 기록
  - 운영 집계 스크립트(`scripts/ops/ai_decision_canary_report.sh`) 추가
- 목표(요약):
  - 실거래 전환 전, AI Decision 구간에서 모델 혼재 실험을 안전하게 수행할 수 있는 운영 기반 확보
- 이번 구현이 해결한 문제(한 줄):
  - Anthropic 단일 경로로는 불가능했던 모델 카나리 실험을 코드/운영 레벨에서 재현 가능하게 만들었다.

---

## 2. 구현 내용(핵심 위주)
### 2.1 카나리 라우팅 계층 도입
- 파일/모듈:
  - `src/agents/factory.py`
- 변경 내용:
  - `AIDecisionRoute` 타입, deterministic bucket(sha256), 카나리 퍼센트 상한(최대 20%) 구현
  - `select_ai_decision_route()`로 신호 단위(provider/model/route_label) 선택
  - canary provider 키가 없으면 다른 provider로 우회하지 않고 `primary-fallback`으로 복귀하도록 가드 추가
  - `ChatOpenAI` 경로 추가 및 provider별 LLM 빌더 캐시 분리
- 효과/의미:
  - 실험 재현성(동일 신호 동일 라우팅), 운영 안전성(키 누락 즉시 primary fallback), 비교 가능성(model_used 기록) 확보

### 2.2 실행/노드/로그 경로 연결
- 파일/모듈:
  - `src/agents/runner.py`
  - `src/agents/analyst.py`
  - `src/agents/guardian.py`
  - `src/agents/state.py`
- 변경 내용:
  - Runner에서 라우팅을 1회 결정 후 `state["llm_route"]`로 Analyst/Guardian 공유
  - 노드에서 `get_analyst_llm(route)`, `get_guardian_llm(route)` 호출
  - DB `model_used`를 `provider:model (route_label)` 형식으로 기록
  - Discord 웹훅 payload에도 `model_used` 포함
- 효과/의미:
  - Analyst/Guardian 모델 불일치 방지
  - 사후 분석 시 라우팅/결정 결과를 1:1로 추적 가능

### 2.3 운영 관측/설정 파일 보강
- 파일/모듈:
  - `scripts/ops/ai_decision_canary_report.sh`
  - `.env.example`
  - `deploy/cloud/oci/.env.example`
- 변경 내용:
  - 최근 N시간 모델별 CONFIRM/REJECT/평균 confidence/파싱실패/timeout 집계 스크립트 추가
  - 카나리 운영 변수(`AI_DECISION_PRIMARY_*`, `AI_CANARY_*`, `LLM_PROVIDER`)를 예시 파일에 반영
- 효과/의미:
  - 카나리 실험 기간 중 품질/안정성 지표를 빠르게 비교 가능
  - 운영 환경 변수 누락을 사전에 예방

### 2.4 카나리 실험 용어/정책 정의
- 카나리(canary) 의미:
  - 전체 트래픽을 한 번에 바꾸지 않고, 소량(예: 10%)만 신규 모델로 보내 품질/안정성/비용을 관측하는 점진 전환 방식
- 본 프로젝트에서의 카나리 단위:
  - "AI Decision 1회 실행(심볼 + 전략 + 신호시각)" 단위
  - Analyst/Guardian는 같은 `llm_route`를 공유하므로 한 결정 사이클 안에서 모델이 섞이지 않음
- 라우팅 방식:
  - `symbol|strategy|signal_timestamp`를 seed로 해시 버킷(0~99) 계산
  - 버킷이 `AI_CANARY_PERCENT` 미만이면 canary, 아니면 primary
- 운영 가드레일:
  - 카나리 비율은 코드 상한 20%
  - canary provider API 키 누락 시 `primary-fallback`으로 강등

### 2.5 환경변수 상세(운영자가 자주 헷갈리는 포인트)
| 변수 | 역할 | 예시 | 비고 |
|---|---|---|---|
| `LLM_PROVIDER` | 기본 전역 provider | `anthropic` | 챗봇/RAG 등 공용 기본값 |
| `AI_DECISION_PRIMARY_PROVIDER` | AI Decision primary provider | `anthropic` | Analyst/Guardian 기본 경로 |
| `AI_DECISION_PRIMARY_MODEL` | AI Decision primary model | `claude-haiku-4-5-20251001` | primary 모델 고정 |
| `AI_CANARY_ENABLED` | 카나리 on/off | `true` | `false`면 100% primary |
| `AI_CANARY_PROVIDER` | 카나리 provider | `openai` | 현재 `openai|anthropic` 지원 |
| `AI_CANARY_MODEL` | 카나리 모델명 | `gpt-4o-mini` | canary 경로 모델 |
| `AI_CANARY_PERCENT` | 카나리 비율(%) | `10` | 0~20 허용(코드 clamp) |

추가 동작 예시:
1) `AI_CANARY_ENABLED=false`: 전체 100% primary
2) `AI_CANARY_ENABLED=true`, `AI_CANARY_PERCENT=10`: 대략 10% canary / 90% primary
3) `AI_CANARY_PERCENT=30` 입력: 실제 동작은 20% (상한 적용)
4) `AI_CANARY_PROVIDER=openai`인데 `OPENAI_API_KEY` 없음: `primary-fallback` 기록 후 primary 실행

### 2.6 분포/오류율 비교 기준(운영 판정 방식)
- 비교 기본 단위:
  - `model_used`별 `total`, `confirm_rate`, `avg_confidence`, `parse_fail_count`, `timeout_count`
- 1차 집계:
  - `scripts/ops/ai_decision_canary_report.sh 24`
- 추가 상세 SQL(필요 시):
```sql
SELECT
  model_used,
  count(*) AS total,
  count(*) FILTER (WHERE decision='CONFIRM') AS confirm_count,
  round(100.0 * count(*) FILTER (WHERE decision='CONFIRM') / nullif(count(*),0), 2) AS confirm_rate_pct,
  count(*) FILTER (WHERE reasoning LIKE '분석가 출력 검증 실패:%') AS parse_fail_count,
  count(*) FILTER (WHERE reasoning ILIKE '%timed out%') AS timeout_count
FROM agent_decisions
WHERE created_at >= now() - interval '24 hours'
GROUP BY model_used
ORDER BY total DESC;
```
- 해석 기준(21-03 plan과 정합):
  1) parse_fail/timeout이 primary 대비 +2%p 이상 악화되면 중단 검토
  2) confirm/reject 분포가 비정상 급변하면 프롬프트/모델 재검토
  3) 품질 저하 없이 비용 이점이 확인되면 canary 유지 또는 단계적 확대 검토

### 2.7 향후 Gemini 등 신규 모델 확장 가이드
- 현재 코드 제약:
  - `src/agents/factory.py`의 `SUPPORTED_PROVIDERS`는 `anthropic`, `openai`만 포함
- Gemini 확장 최소 단계:
  1) provider SDK 의존성 추가(예: LangChain Google GenAI 계열)
  2) `_build_gemini_llm()` 구현 + `_build_llm()` 분기 추가
  3) `SUPPORTED_PROVIDERS`에 `gemini` 추가
  4) `_is_provider_configured()`에 Gemini API 키 검사 추가
  5) `.env.example` / `deploy/cloud/oci/.env.example`에 Gemini 키/모델 예시 추가
  6) `tests/agents/test_factory_canary.py`에 Gemini 경로/키누락 fallback 테스트 추가
- 운영 원칙:
  - 신규 provider는 canary 5~10%로 시작
  - 24h~72h 관찰 후 실패율/분포 이상 없을 때만 확대
  - 실패 시 즉시 `AI_CANARY_ENABLED=false`로 롤백

---

## 3. 변경 파일 목록
### 3.1 수정
1) `src/agents/factory.py`
2) `src/agents/runner.py`
3) `src/agents/analyst.py`
4) `src/agents/guardian.py`
5) `src/agents/state.py`
6) `.env.example`
7) `deploy/cloud/oci/.env.example`
8) `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`
9) `docs/checklists/remaining_work_master_checklist.md`
10) `docs/PROJECT_CHARTER.md`

### 3.2 신규
1) `tests/agents/test_factory_canary.py`
2) `scripts/ops/ai_decision_canary_report.sh`
3) `docs/work-result/21-03_ai_decision_model_canary_experiment_result.md`

---

## 4. DB/스키마 변경
- 변경 사항:
  - 없음(기존 `agent_decisions.model_used` 활용)
- 마이그레이션:
  - 필요 없음
- 롤백 전략/주의점:
  - `AI_CANARY_ENABLED=false` 후 bot 재기동으로 즉시 primary 단일 경로 복귀

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `PYTHONPATH=. .venv/bin/python -m pytest tests/agents/test_factory_canary.py`
  - `PYTHONPATH=. .venv/bin/python -m pytest tests/test_agents.py`
- 결과:
  - 통과
  - `test_factory_canary.py`: 4 passed
  - `tests/test_agents.py`: 3 passed

### 5.2 테스트 검증
- 실행 명령:
  - `PYTHONPATH=. .venv/bin/python -m pytest tests/agents/test_factory_canary.py tests/test_agents.py`
- 결과:
  - 개별 실행으로 모두 통과 확인(총 7 passed)
  - 카나리 fallback 동작 검증 실패 1건은 라우팅 fallback 정책 수정 후 해결

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법:
  - `scripts/ops/ai_decision_canary_report.sh 24`
  - `agent_decisions.model_used` 모델 혼재 여부 확인
- 결과:
  - 운영 반영 후 컨테이너 env 투영 상태(`AI_CANARY_*`, `AI_DECISION_PRIMARY_*`) 정상 확인.
  - 카나리 리포트는 생성되지만 post-restart 구간 신규 의사결정 0건으로 표본 부족 상태.
  - 권장 확인 순서:
    1) canary on 후 최소 6~24시간 데이터 확보
    2) model별 total 표본수 확인(너무 적으면 판정 유보)
    3) parse_fail/timeout 우선 확인
    4) confirm_rate와 avg_confidence를 보조 지표로 비교

---

## 6. 배포/운영 확인 체크리스트(필수)
1) OCI `.env`에 `OPENAI_API_KEY`와 `AI_CANARY_*` 값 설정
2) `docker compose ... up -d --build bot` 반영 후 `bot` 로그에서 startup 이상 유무 확인
3) `scripts/ops/ai_decision_canary_report.sh 24`로 모델별 분포/오류율 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - "신호 단위 deterministic 라우팅 + primary/canary 이원 경로 + canary 실패 시 primary fallback"
- 고려했던 대안:
  1) 전체 LLM 경로 일괄 OpenAI 전환
  2) AI Decision 경로만 카나리 라우팅(채택)
  3) Shadow mode(결정은 primary, canary는 병렬 관측만 저장)
- 대안 대비 실제 이점(근거/관측 포함):
  1) 영향 범위를 Analyst/Guardian으로 제한해 운영 리스크 축소
  2) `model_used` 기록으로 모델별 분포/오류율 관측 가능
  3) canary 키 누락 시 자동 fallback으로 장애 전파 차단
- 트레이드오프(단점)와 보완/완화:
  1) 환경변수/운영 규칙이 늘어 복잡도 증가
  2) 이를 보완하기 위해 `.env.example`/리포트 스크립트/체크리스트를 동시 반영

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `src/agents/factory.py`의 canary fallback 정책 설명
  2) deterministic 라우팅 및 canary 퍼센트 가드레일 설명
- 주석에 포함한 핵심 요소:
  - 의도/왜(why): 실험 의미 보존, 안전한 fallback
  - 불변조건(invariants): 동일 신호 → 동일 라우팅
  - 엣지케이스/실패 케이스: 키 누락, 퍼센트 오입력, provider 미설정
  - 대안 대비 판단 근거: provider 우회 대신 primary fallback 채택 이유

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - provider/model 분기, canary 비율 라우팅, 운영 리포트 스크립트 추가
- 변경/추가된 부분(왜 바뀌었는지):
  - canary provider 키 누락 시 cross-provider fallback을 제거하고 primary-fallback으로 고정
  - 이유: 실험 모델 오염 방지 및 운영 해석 일관성 확보
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - 카나리 실험 코드/테스트/운영 집계 기반은 반영 완료
  - 체크리스트 기준으로는 운영 관찰(24h 지표 확인) 전이라 `in_progress` 유지
- 후속 작업(다음 plan 번호로 넘길 것):
  1) `21-03`: 24h 카나리 관찰 및 성공/중단 기준 판정 후 상태 `done` 전환
  2) `21-04`: 모델별 토큰/비용 대시보드 구축으로 비용 비교 자동화

---

## 11. Phase 2 운영 관측 업데이트 (2026-03-04)
- 관측 요약:
  - OCI `.env`에는 canary 변수 값이 존재했지만, 컨테이너 내부 env 투영이 누락되어 초기에 값이 모두 비어 있었음.
  - `deploy/cloud/oci/docker-compose.prod.yml` env projection 보정 후, 컨테이너 내부에서 canary/primary/timeout 값이 정상 확인됨.
  - 재기동 후 `agent_decisions` 신규 건수가 0건이라 canary 분포(특히 OpenAI 경로) 평가는 아직 유보 상태.
- 정량 관측(운영 로그 기반):

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| bot 내부 canary 핵심 env 유효 개수(7개 기준) | 0 | 7 | +7 | +100.0 |
| post-restart `agent_decisions` 신규 건수 | 0 | 0 | 0 | 0.0 |
| 24h canary report 내 OpenAI 모델 집계 건수 | 0 | 0 | 0 | 0.0 |

- 24h 모델별 집계(2026-03-04 관측 시점):

| model_used | total | confirm_count | reject_count |
|---|---:|---:|---:|
| `claude-haiku-4-5-20251001` | 59 | 1 | 58 |
| `anthropic:claude-haiku-4-5-20251001 (primary)` | 3 | 0 | 3 |

- 해석:
  - 현재 병목은 "카나리 라우팅 코드"가 아니라 "관측 구간 표본 부족"이다.
  - 따라서 `21-03`은 `done` 전환 조건(모델별 충분 표본 + 분포/오류율 비교)을 아직 충족하지 못했다.
- 후속 실행 기준:
  1) 최소 24~48시간 추가 관찰.
  2) 모델별 표본 N>=20 확보 후 `confirm_rate/timeout/parse_fail` 비교.
  3) 기준 충족 시 `21-03` 상태 전환 검토.

---

## 12. References
- `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`
- `docs/checklists/remaining_work_master_checklist.md`
- `docs/PROJECT_CHARTER.md`
- `docs/troubleshooting/21-06_ai_canary_env_injection_and_observability_gap.md`

---

## 13. Phase 3 운영 관측 업데이트 (2026-03-08)
- 관측 요약:
  - 24시간 구간에서 primary 13건, canary 5건이 기록되어 모델 혼재 자체는 확인됐다.
  - 다만 계획서의 최소 표본 기준(`모델별 N>=20`)에는 미달하므로 `21-03`은 계속 `in_progress`가 맞다.
  - 운영 명령은 `/opt/coin-pilot/deploy/cloud/oci`에서 바로 `scripts/ops/...`로 실행하면 경로가 맞지 않으므로, `cd /opt/coin-pilot` 후 실행하거나 절대경로(`/opt/coin-pilot/scripts/ops/...`)를 써야 한다.
- 정량 관측(2026-03-08, 최근 24h):

| model_used | total | confirm_count | confirm_rate_pct | parse_fail_count | timeout_count |
|---|---:|---:|---:|---:|---:|
| `anthropic:claude-haiku-4-5-20251001 (primary)` | 13 | 1 | 7.69 | 1 | 0 |
| `openai:gpt-4o-mini (canary)` | 5 | 0 | 0.00 | 0 | 0 |

- 정량 개선 증빙(추가):
  - 측정 기간/표본:
    - 최근 24시간, 총 18 decisions
  - 측정 기준:
    - 모델 혼재 확인 + 최소 표본 기준 충족 여부
  - 데이터 출처:
    - `agent_decisions` SQL 집계
  - 재현 명령:
    - `cd /opt/coin-pilot && scripts/ops/ai_decision_canary_report.sh 24`
    - `docker exec -u postgres coinpilot-db psql -d coinpilot -c "SELECT model_used, count(*) AS total, count(*) FILTER (WHERE decision='CONFIRM') AS confirm_count, round(100.0 * count(*) FILTER (WHERE decision='CONFIRM') / nullif(count(*),0), 2) AS confirm_rate_pct, count(*) FILTER (WHERE reasoning LIKE '분석가 출력 검증 실패:%') AS parse_fail_count, count(*) FILTER (WHERE reasoning ILIKE '%timed out%') AS timeout_count FROM agent_decisions WHERE created_at >= now() - interval '24 hours' GROUP BY model_used ORDER BY total DESC;"`

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 24h canary 모델 집계 건수 | 0 | 5 | +5 | 측정 불가(분모 0) |
| 24h primary 모델 집계 건수 | 3 | 13 | +10 | +333.3 |
| 모델별 최소 표본 기준 충족 수(2모델 기준) | 0 | 0 | 0 | 0.0 |

- 해석:
  - 카나리 라우팅은 실제 운영 데이터에서 동작 중이다.
  - 그러나 canary 표본 5건은 분포/품질 판정에 부족하므로, 현재 단계에서 `done` 전환이나 기본 모델 승격 판단은 이르다.
- 다음 판정 조건:
  1) 모델별 `N>=20` 확보
  2) parse_fail/timeout 악화가 primary 대비 `+2%p` 이내
  3) confirm/reject 분포 해석이 가능한 수준의 표본 확보
