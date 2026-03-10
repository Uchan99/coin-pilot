# 28-01. AI Decision RAG Prompt Ordering / Weighting 보정 계획

**작성일**: 2026-03-11  
**작성자**: Codex  
**상태**: Done  
**관련 계획 문서**: `docs/work-plans/28_ai_decision_strategy_case_rag_plan.md`  
**승인 정보**: 2026-03-11 사용자 승인 완료

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - `28` Phase 1 OCI replay 결과에서 `samples=10`, `decision_changed_count=8`, `avg_confidence_delta=-22.4`가 관측됐다.
  - drift 표본 8건은 모두 `SIDEWAYS`였고, baseline `CONFIRM 68~72`가 RAG-on `REJECT 42`로 수렴했다.
- 왜 즉시 대응이 필요했는지:
  - 오류율/지연/비용은 허용 범위였지만 판단 drift가 커서 Phase 2 live canary로 넘어갈 수 없다.
  - 원인은 retrieval 양보다 prompt ordering/weighting에 가까워, 작은 범위 보정으로 다시 replay를 돌려볼 가치가 있다.

## 1. 문제 요약
- 증상:
  - RAG를 붙인 Analyst가 Rule Engine 통과 신호를 과도하게 보수적으로 해석해 `REJECT 42`로 수렴한다.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: Analyst CONFIRM/REJECT 분포 왜곡
  - 리스크: valid 진입 후보의 과차단
  - 비용: 큰 문제 없음 (`avg cost_usd +13.0%`)
  - 지연: 큰 문제 없음 (`p50 latency -19.8%`)
- 재현 조건:
  - `SIDEWAYS` 레짐 BUY replay 샘플에서 현재 `strategy:9 + cases:5` 컨텍스트를 함께 주입할 때

## 2. 원인 분석
- 가설:
  - 정적 전략/리스크 요약이 prompt 앞부분에서 너무 강하게 앵커링되어, Analyst가 "기술적 캔들 검증"보다 "보수적 가드레일 재해석"에 치우친다.
- 조사 과정:
  - replay 결과와 `rag_context_preview`를 비교한 결과, drift 표본 대부분에서 전략 요약 블록이 먼저 길게 배치되고 과거 사례 블록은 후순위였다.
  - `rag_source_summary=['strategy:9','cases:5']`가 drift 표본 전체에서 동일하게 반복되어, retrieval 소스 수 자체보다 prompt weighting이 더 직접 원인으로 보였다.
- Root cause:
  - Analyst 프롬프트 내 RAG ordering/weighting이 현재 업무 목적(캔들 구조/지속성 검증)에 맞지 않다.

## 3. 아키텍처 선택
- 선택안:
  - **retrieval 소스는 유지하고, prompt ordering/weighting만 조정하는 소규모 보정**으로 간다.
- 선택 이유:
  - 현재 문제는 검색 미스보다 "정적 제약이 너무 앞에서 강하게 보이는 것"에 가깝다.
  - 작은 보정으로 drift를 낮출 수 있으면 live canary 전 단계에서 가장 안전하다.
- 검토한 대안:
  1. 전략 문서 레퍼런스를 더 많이 추가
     - 장점: 문맥이 풍부해 보인다.
     - 단점: 현재 drift를 더 악화시킬 가능성이 높다.
  2. 과거 사례 수를 무작정 늘리기
     - 장점: 사례 기반 판단 강화 가능성
     - 단점: 표본 수가 적은 상태에서 잡음 증가와 토큰 비용 상승 위험이 있다.
  3. Guardian까지 함께 조정
     - 장점: 전체 agent chain 일관성 조정 가능
     - 단점: 원인 분리가 더 어려워진다.
  4. RAG를 전면 제거
     - 장점: drift 즉시 제거
     - 단점: `28` 목표 자체를 포기하게 된다.
- 트레이드오프:
  - retrieval 구조를 바꾸지 않고 prompt만 조정하면 수정 범위는 작지만, 효과가 제한적일 수 있다.

## 4. 대응 전략
- 단기 핫픽스:
  - 없음. live canary는 이미 보류 상태다.
- 근본 해결:
  1. 전략 요약 줄 수 축소 (`strategy:9 -> 더 짧은 핵심 bullet`)
  2. 과거 사례 블록을 전략 요약보다 앞에 배치
  3. Analyst에게 "Rule Engine 통과 신호의 기술적 캔들 구조/지속성만 검토하고 규칙 자체를 재판정하지 말 것"이라는 경계 문구 강화
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 이번 단계도 replay 전용
  - live canary 주입 금지 유지
  - replay 기준(`avg_confidence`, `decision_changed_count`, parse fail/timeout, latency/cost`) 재측정 후에만 다음 단계 검토

## 5. 구현/수정 내용
- 변경 파일(예정):
  - `docs/work-result/28-01_ai_decision_rag_prompt_ordering_and_weighting_tuning_result.md`
  - `config/ai_decision_rag_strategy_refs.json`
  - `src/agents/ai_decision_rag.py`
  - `src/agents/analyst.py`
  - 필요 시 `tests/agents/test_ai_decision_rag.py`
  - replay 결과 문서(`docs/work-result/28_ai_decision_strategy_case_rag_result.md`) 업데이트
- DB 변경(있다면):
  - 없음
- 주의점:
  - 과거 사례 우선 배치 시 사례 품질이 낮으면 반대로 잘못된 패턴에 앵커링될 수 있다.
  - 전략 요약을 너무 줄이면 RAG의 존재 의미가 약해질 수 있다.

## 6. 검증 기준
- 재현 케이스에서 해결 확인:
  - 동일 replay 조건에서 `decision_changed_count` 감소 여부 확인
  - `avg_confidence_delta`가 `-5pt`에 더 근접하는지 확인
- 회귀 테스트:
  - `tests/agents/test_ai_decision_rag.py`
  - `python3 -m py_compile ...`
  - `bash -n scripts/ops/replay_ai_decision_rag.sh`
- 운영 체크:
  - OCI replay 재실행
  - `/tmp/ai_rag_replay*.json` summary 비교
- 정량 기준(후속 replay):
  - 최소 `N>=10` 유지
  - `decision_changed_count / samples <= 30%` 목표
  - `avg_confidence_delta >= -5`
  - parse fail 증가 없음
  - latency/cost 악화는 기존 기준 유지 (`+20%` 이내)

## 7. 롤백
- 코드 롤백:
  - prompt ordering/weighting 보정 revert
- 데이터/스키마 롤백:
  - 없음

## 8. 문서 반영
- work-plan/work-result 업데이트:
  - 승인 후 구현 시 `docs/work-result/28_ai_decision_strategy_case_rag_result.md` 하단에 Phase 1-2 또는 drift tuning 섹션으로 이어서 기록
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 없음. 실험 단계이며 공식 운영 정책 변경이 아니다.

## 9. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1. replay summary에 `strategy_line_count`, `case_line_count`를 같이 저장해 weighting 변화를 수치로 추적
  2. `SIDEWAYS`와 `BEAR/BULL`을 레짐별로 따로 replay 비교
  3. prompt ordering 실험이 반복되면 별도 실험 config로 분리

## 10. 진행 현황 메모
- 2026-03-11 현재 상태:
  - 전략 요약 축소(`strategy:9 -> strategy:4` 목표)
  - 과거 사례 블록 선배치
  - Analyst 경계 문구 강화
  - 단위 테스트/정적 검증 후 OCI replay 재측정 완료
  - `decision_changed_count=0`, `avg_confidence_delta=-2.8`로 drift 기준 통과
