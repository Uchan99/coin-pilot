# 28. AI Decision 전략문서/과거사례 기반 RAG 보강 계획

**작성일**: 2026-03-05  
**작성자**: Codex  
**상태**: In Progress  
**관련 계획 문서**: `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`, `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`, `docs/work-plans/29-01_bull_regime_rule_funnel_observability_and_review_automation_plan.md`, `docs/work-plans/30_strategy_feedback_automation_spec_first_plan.md`  
**승인 정보**: 2026-03-11 사용자 승인 완료 (`offline replay -> live canary` 2단 구조로 진행)

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - AI Decision 품질 개선 논의에서 RAG 소스 우선순위(일반 차트 이론 vs 우리 전략/사례)가 불명확했다.
- 왜 즉시 대응이 필요했는지:
  - 구현 전 방향을 고정하지 않으면 비용만 늘고 품질 개선 효과가 불확실해질 수 있다.
  - `21-03`은 현재 canary 표본이 작아 모델 성능 차이를 단정하기 어렵고, `29-01`에서는 BULL 표본 부족으로 병목 해석이 아직 미완료다.
  - 따라서 다음 실험은 모델 교체보다 "어떤 컨텍스트를 넣을 것인가"를 작게, canary 범위에서 검증하는 편이 합리적이다.

## 1. 문제 요약
- 증상:
  - AI Decision 판단 품질 개선 아이디어는 있으나, 어떤 지식원을 우선 연결할지 기준이 없다.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: Analyst/Guardian 판단 일관성
  - 리스크: 일반 이론 문서 과적합/잡음 증가
  - 비용: 불필요한 RAG 토큰 증가 가능성
- 재현 조건:
  - RAG 소스 선정 기준 없이 임의 문서를 주입할 때
  - Analyst/Guardian 프롬프트가 현재 시점의 지표와 시스템 프롬프트에만 의존하고, 우리 전략 규칙/과거 실패 사례를 구조적으로 참조하지 않을 때

## 2. 원인 분석
- 가설:
  - 현재 판단 품질의 병목은 일반 차트 이론 부족이 아니라, 전략 규칙 정합성과 과거 의사결정 사례 활용 부족이다.
- 조사 과정:
  - 최근 운영 논의에서 “전략 문서 + 과거 사례 우선”이 더 실용적이라는 합의 도출.
  - 코드 기준으로 현재 `src/agents/rag_agent.py`는 범용 문답용 PGVector 검색기만 제공하고, AI Decision 경로(`analyst.py`, `guardian.py`)에는 연결돼 있지 않다.
  - `29-01` 운영 결과에서는 SIDEWAYS 구간에서 `max_per_order` 같은 운영 병목이 분명히 드러났고, 이런 "우리 시스템 고유의 사례"를 일반 차트 이론보다 우선 컨텍스트로 넣는 편이 설명력과 비용 효율이 높다.
- Root cause:
  - RAG 소스 계층화 기준(우선순위/검증 지표)이 문서화되지 않음.
  - 범용 챗봇용 RAG와 AI Decision용 RAG의 목적이 분리되지 않아, 검색 대상을 그대로 재사용하면 잡음이 커질 가능성이 높다.

## 3. 아키텍처 선택
- 선택안:
  - **전략 문서 + 과거 사례 2계층 RAG를 AI Decision canary 경로에만 제한 주입한다.**
- 선택 이유:
  - Rule Engine/Risk Manager가 코어인 현재 구조를 유지하면서, AI가 "우리 규칙과 과거 운영 맥락"을 참조하도록 최소 변경으로 강화할 수 있다.
  - `21-03` canary 실험과 결합하면 품질/비용/지연 악화를 작은 표본에서 먼저 관찰할 수 있다.
- 검토한 대안:
  1. **일반 차트 이론 문서를 대량 주입**
     - 장점: 데이터 준비가 쉽다.
     - 단점: 우리 전략 규칙과 무관한 잡음이 많고, "좋은 말"은 늘지만 실제 의사결정 일관성 개선 근거가 약하다.
  2. **RAG 없이 프롬프트만 확장**
     - 장점: 구현이 가장 단순하다.
     - 단점: 과거 사례를 구조적으로 재사용할 수 없고, 전략 문서가 바뀔 때 프롬프트 관리 비용이 커진다.
  3. **모든 AI Decision 호출에 즉시 RAG 강제 적용**
     - 장점: 빠르게 전면 적용 가능하다.
     - 단점: latency/cost/오탐 리스크가 커서 현재 관측 기반 운영 원칙과 충돌한다.
  4. **이미지/차트 패턴 기반 멀티모달 RAG**
     - 장점: 직관적으로는 풍부해 보인다.
     - 단점: 현재 운영 방침과 명시적으로 충돌하고, 데이터/비용/검증 복잡도가 과도하다.
- 트레이드오프:
  - 선택안은 초기 효과가 제한적일 수 있지만, 현재 프로젝트의 승인형/관측형 운영 원칙과 가장 잘 맞는다.
  - 일반 이론/이미지 자료를 일부러 제외하므로, "이론 설명력"보다 "운영 정합성"을 우선하는 설계다.

## 4. 대응 전략
- 단기 핫픽스:
  - 없음 (계획/기준 확정 단계)
- 근본 해결:
  - RAG 소스를 2계층으로 정의:
    1) 전략/리스크 규칙 문서(정적)
    2) 과거 의사결정 + 결과 사례(동적)
  - 일반 차트 이론/이미지는 보조 소스로만 제한
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - canary A/B로만 실험, 기준 미달 시 즉시 비활성
  - Phase 1에서는 primary 경로에 주입하지 않고, `AI_CANARY_ENABLED=true` 경로에서만 선택적으로 활성화
  - retrieval 실패/timeout 시 기존 AI Decision 경로로 폴백
  - RAG 컨텍스트 길이와 검색 문서 수를 상한(`k<=3`)으로 제한

## 5. 구현 범위 (승인 시)
### Phase 1. Offline Replay 기반 안전성/품질 비교
- 목표:
  - live canary 표본 부족 상태에서도 baseline Analyst와 RAG-on Analyst를 같은 입력으로 비교 가능한 재생(replay) 경로를 만든다.
  - 이 단계에서는 "운영 성능 우열 결론"이 아니라 "주입 가능성/오류율/latency/cost/reasoning 정렬"을 본다.
- 변경 파일(예정):
  1) `src/agents/analyst.py`
     - replay 실행 시 RAG on/off를 토글할 수 있는 주입 지점 추가
  2) `src/agents/guardian.py`
     - Phase 1에서는 직접 주입하지 않거나, Analyst 대비 최소 범위로 제한
  3) `src/agents/rag_agent.py` 또는 신규 모듈
     - AI Decision 전용 retriever 생성기 분리
  4) 신규 인덱싱/검색 모듈(예정)
     - 전략 문서 source set
     - 과거 사례 source set
  5) 신규 replay 스크립트(예정)
     - 최근 `agent_decisions` 또는 저장된 입력 샘플을 읽어 baseline/RAG-on Analyst를 나란히 실행
  6) `scripts/ops/ai_decision_canary_report.sh`
     - Phase 2 live canary 진입 전까지는 변경 없음 또는 후속 확장만 검토
  6) 결과 문서/필요 시 트러블슈팅 문서
- Phase 1에서 의도적으로 제외:
  - 이미지/차트 패턴 자료
  - live 운영 경로 강제 적용
  - 신규 복잡 스키마 도입
  - Guardian 대규모 리프롬프팅
- DB 변경:
  - 우선 없음이 기본
  - Phase 1은 기존 PGVector/문서 컬렉션 재사용 또는 최소 메타데이터 확장으로 제한
- 주의점:
  - 판단 경로 지연 증가(토큰/latency) 관리 필요
  - 전략 문서가 오래된 경우 stale context가 오히려 판단 품질을 해칠 수 있음
  - 과거 사례는 "정답"이 아니라 참고 맥락이므로, retrieval 결과가 Rule Engine을 override하면 안 됨

### Phase 2. Live Canary 제한 주입
- 시작 조건:
  - Phase 1 replay에서 parse fail/timeout/latency/cost 악화가 허용 범위 이내일 것
- 목표:
  - canary Analyst에만 전략/사례 RAG를 제한 주입하고 실제 운영 표본을 소량 수집한다.

## 6. 데이터 소스 정책
- 전략 문서(허용):
  - `docs/PROJECT_CHARTER.md`
  - 전략/리스크 관련 approved plan/result에서 운영 규칙으로 굳어진 문서
- 과거 사례(허용):
  - `agent_decisions`
  - `rule_funnel_events`
  - `trading_history`
  - 관련 result/troubleshooting 문서의 확정 사례
- 후순위/제외:
  - 일반 차트 이론 문서
  - 이미지/차트 패턴 자료
  - 외부 커뮤니티 게시글

## 7. 검증 기준 (예정)
- 재현 케이스에서 해결 확인:
  1) parse_fail/timeout 악화 없음
  2) CONFIRM/REJECT 분포 급변 없음
  3) 샘플 확보 후 거래 성과 지표(기대값/drawdown) 악화 없음
- 회귀 테스트:
  - 기존 AI Decision 경로 테스트 + RAG 비활성 fallback 테스트
- 운영 체크:
  - Phase 1: replay 비교 결과를 파일/JSON으로 저장
  - Phase 2: canary 기간(24~72h) 품질/비용 리포트 비교
  - `21-03` 리포트와 같은 관측 방식으로 `model_used` 외 `rag_context_source` 또는 유사 메타 차이를 비교
  - `29-01` rule funnel 상 `ai_confirm/ai_reject` 단계 비율이 급격히 악화되지 않는지 확인
- 정량 성공 기준(Phase 1 replay):
  - replay 표본 최소 `N>=30` 확보 시도
  - `parse_fail_rate` 증가 `+2%p` 이내
  - `timeout_count` 증가 `+2%p` 이내
  - `avg_confidence`가 baseline 대비 `-5pt` 초과 하락하지 않을 것
  - `p50 latency_ms` 증가 `+20%` 이내
  - `avg cost_usd` 증가 `+20%` 이내
- 정량 성공 기준(Phase 2 live canary):
  - canary 표본 `N>=20` 확보 전에는 `hold`
- 측정 명령(예정):
```bash
PYTHONPATH=. python scripts/replay_ai_decision_rag.py --hours 168 --limit 50 --output /tmp/ai_rag_replay.json
scripts/ops/ai_decision_canary_report.sh 24
docker exec -u postgres coinpilot-db psql -d coinpilot -c "
SELECT model_used, count(*), avg(confidence)
FROM agent_decisions
WHERE created_at >= now() - interval '72 hours'
GROUP BY 1;
"
scripts/ops/rule_funnel_regime_report.sh 72
```

## 8. 롤백
- 코드 롤백:
  - RAG 주입 기능 revert
- 데이터/스키마 롤백:
  - 인덱스/메타 테이블 비활성 또는 drop
- 운영 롤백:
  - canary 전용 RAG env를 비활성화하고 기존 AI Decision 경로로 즉시 복귀

## 9. 문서 반영
- work-plan/work-result 업데이트:
  - 승인 후 구현 시 result 문서 별도 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 판단 정책(공식) 변경 시 Charter changelog 반영
  - 단, 현재는 "AI Decision canary에 전략/사례 RAG를 제한 주입한다" 수준이라 운영 정책으로 채택되기 전까지 Charter 본문 변경 없이 changelog 후보만 기록

## 10. 리스크 / 가정 / 미확정
- 리스크:
  - 표본이 작은 상태에서 RAG on/off 차이를 과대해석할 수 있다.
  - retrieval 품질보다 source 문서 품질이 병목일 수 있다.
  - RAG가 Rule Engine 경계(reason boundary)를 재해석하는 듯한 부작용이 생길 수 있다.
  - replay용 과거 입력이 완전히 재현되지 않으면 live와 오차가 발생할 수 있다.
- 가정:
  - 현재 PGVector 기반 문서 검색 경로를 AI Decision 전용으로 재사용 가능하다.
  - 개인 계정 fallback으로도 token/latency 비교는 가능하다.
- 미확정:
  - 과거 사례를 문서화된 natural language로 인덱싱할지, 구조화 요약문으로 만들지
  - Guardian까지 주입할지, Analyst만 먼저 볼지
  - replay 입력을 `agent_decisions`에서 직접 복원할지, 별도 fixture/샘플 파일을 만들지

## 11. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) 전략 문서 변경 시 RAG 인덱스 재생성 절차 자동화
  2) 사례 품질 라벨링 규칙(성공/실패) 표준화
  3) Phase 2에서 `30` 전략 피드백 후보와 연동 가능한 사례 요약 포맷 표준화

## 12. 변경 이력
- 2026-03-11: `21-04`를 개인 계정 capability 제약으로 `blocked`, `31`을 `done`으로 반영해 선행 상태를 최신화했다. 기존 방향성 메모 수준의 계획을 "전략 문서 + 과거 사례 2계층 RAG를 AI Decision canary 경로에만 제한 주입"하는 Phase 1 실험 계획으로 재정의했다.
- 2026-03-11: live canary 표본 부족을 반영해 Phase 1을 `offline replay` 비교 경로로 재정의했다. Phase 2부터 canary Analyst 제한 주입으로 이어가는 2단 구조로 계획을 보정했다.
- 2026-03-11: 사용자 승인 후 구현 착수. Phase 1 범위로 `ai_decision_rag.py`, `ai_decision_replay.py`, `scripts/replay_ai_decision_rag.py`, `scripts/ops/replay_ai_decision_rag.sh`, Analyst 선택적 RAG 주입 경로, 단위 테스트를 반영한다.
- 2026-03-11: WSL 로컬 검증에서 docker 미설치로 replay ops 래퍼가 실패한 것을 반영해, `scripts/ops/replay_ai_decision_rag.sh`에 `.venv/bin/python`/`python3` 로컬 폴백 경로를 추가했다. 운영 환경에서는 여전히 bot 컨테이너 경로를 우선 사용한다.
