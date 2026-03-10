# CoinPilot 포트폴리오 / 자기소개 패키지

작성일: 2026-03-10  
대상 직무: AI Engineer / MLOps  
프로젝트: CoinPilot

---

## 1. 프로젝트 한 줄 소개

CoinPilot는 **Rule-Based 자동매매 코어 위에 AI 보조 의사결정, LLM 비용 관측, 운영 모니터링, 승인형 전략 피드백 루프를 결합한 실운영형 시스템**이다.  
핵심은 “AI가 직접 거래를 지배하는 시스템”이 아니라, **검증 가능한 규칙 엔진과 리스크 매니저를 중심에 두고, AI를 실패 허용 가능한 보조 계층으로 제한한 아키텍처**에 있다.

---

## 2. 자기소개서에 바로 가져다 쓸 수 있는 프로젝트 소개문

### 2.1 짧은 버전

CoinPilot는 Upbit 시장을 대상으로 한 규칙 기반 자동매매 시스템입니다.  
저는 이 프로젝트에서 FastAPI 기반 매매 루프, AI Analyst/Guardian 보조 검증 체계, LLM usage/cost observability, Loki-Grafana 기반 운영 관측, Rule Funnel 및 Strategy Feedback Gate 같은 운영 분석 계층을 설계·구현했습니다.  
특히 “예측 모델”보다 “운영 가능한 반응형 시스템”을 지향해, AI가 실패해도 리스크 규칙과 거래 시스템은 안정적으로 동작하도록 설계한 점이 이 프로젝트의 핵심입니다.

### 2.2 긴 버전

CoinPilot는 단순한 트레이딩 봇이 아니라, **운영 가능한 AI-assisted decision system**을 목표로 설계한 프로젝트입니다.  
시장 데이터 수집, 레짐 기반 Rule Engine, Risk Manager, AI Analyst/Guardian, Discord/n8n 알림, Grafana/Loki/Prometheus 관측, LLM 비용 계측, 전략 피드백 자동화까지 하나의 루프로 연결했습니다.  
저는 이 프로젝트에서 “모델이 얼마나 똑똑한가”보다 “AI가 실패해도 시스템이 안전하게 동작하는가”, “비용과 오류를 운영 중에 어떻게 관측하는가”, “전략 수정은 감이 아니라 어떤 근거로 승인하는가”에 초점을 두고 설계를 발전시켰습니다.

---

## 3. 이 프로젝트를 AI Engineer / MLOps 포지션에 맞게 설명하는 핵심 메시지

### 3.1 AI Engineer 관점

이 프로젝트는 LLM을 단순히 붙인 서비스가 아니라, **AI를 운영 환경에서 안전하게 다루기 위한 설계**를 담고 있다.

강조 포인트:
- AI Analyst / Guardian 2단계 검증 구조
- AI timeout, parse fail, provider overload에 대한 보수적 fallback
- deterministic canary routing
- LangChain/LangGraph 기반 멀티 에이전트 라우팅
- RAG / SQL Agent / 전략 리뷰 툴 등 task-specific tool use
- 모델 품질뿐 아니라 **오류율·비용·편향·관측성**까지 포함한 운영 설계

### 3.2 MLOps 관점

이 프로젝트는 모델 개발보다, **AI 기능을 실제 서비스/운영 시스템 안에 안정적으로 넣는 과정**을 잘 보여준다.

강조 포인트:
- OCI + Docker Compose 운영
- Prometheus / Grafana / Loki / Promtail 기반 관측
- n8n + Discord를 통한 운영 알림 자동화
- runbook, troubleshooting, quantified evidence 중심 문서화
- provider cost snapshot / usage ledger / canary 리포트 / strategy feedback gate 등 **운영 판단 자동화**

---

## 4. 왜 이 기술 스택을 썼는가

### 4.1 Rule-Based Core + AI Assistant

가장 중요한 설계 선택은 “AI 예측 모델 중심”이 아니라, **Rule Engine + Risk Manager 중심** 구조를 택한 것이다.

이유:
1. 실거래 시스템에서 가장 중요한 것은 설명 가능성과 재현성이다.
2. LLM은 본질적으로 비결정적이며, 장애나 과부하 시 행동이 불안정할 수 있다.
3. 따라서 거래 실행 판단의 코어는 규칙 기반으로 두고, AI는 검증/리뷰/조회/보조 판단에 제한하는 것이 운영 안정성에 유리하다.

어필 문장 예시:
- “저는 AI를 중심에 놓는 대신, Rule Engine과 Risk Manager를 코어로 두고 AI를 보조 계층으로 설계했습니다.”
- “이 선택 덕분에 AI timeout이나 provider overload가 발생해도 거래 시스템 전체가 멈추지 않고 보수적으로 fallback할 수 있었습니다.”

근거:
- AI timeout(40초) 또는 오류 시 REJECT fallback 정책: [PROJECT_CHARTER.md](/home/syt07203/workspace/coin-pilot/docs/PROJECT_CHARTER.md)
- Analyst 구조: [analyst.py](/home/syt07203/workspace/coin-pilot/src/agents/analyst.py)
- 매매 루프: [main.py](/home/syt07203/workspace/coin-pilot/src/bot/main.py)

### 4.2 LangChain / LangGraph

LangChain과 LangGraph는 “트렌디해서” 쓴 것이 아니라, **도메인별로 다른 종류의 AI 작업을 분리하고 라우팅하기 위해** 사용했다.

왜 사용했는가:
1. 챗봇 질의는 SQL 조회, 문서 검색(RAG), 전략 리뷰, 시장 해석 등 유형이 다르다.
2. 이걸 단일 프롬프트로 처리하면 품질과 추적성이 떨어진다.
3. LangGraph의 상태 기반 라우팅은 “의도 분류 → 적절한 agent/tool” 구조를 구현하기 적합했다.

실제 활용:
- Router가 질의를 `db_query`, `doc_search`, `strategy_review`, `risk_diagnosis` 등으로 분기
- SQL Agent는 read-only 자연어 SQL 질의 담당
- RAG Agent는 문서 검색 기반 답변 담당
- Premium review는 전략/리스크 장단점 분석용 고급 경로로 분리

근거 코드:
- Router: [router.py](/home/syt07203/workspace/coin-pilot/src/agents/router.py)
- RAG Agent: [rag_agent.py](/home/syt07203/workspace/coin-pilot/src/agents/rag_agent.py)
- 심층 가이드: [DEEP_LEARNING_GUIDE.md](/home/syt07203/workspace/coin-pilot/docs/DEEP_LEARNING_GUIDE.md)

어필 포인트:
- “단일 LLM 호출이 아니라 의도별로 agent/tool을 분리해 LangGraph 상태 머신으로 라우팅했습니다.”
- “이 구조 덕분에 RAG, SQL, 전략 리뷰 같은 이질적 작업을 공통 프레임워크 안에서 관리할 수 있었습니다.”

### 4.3 RAG

RAG는 일반적인 지식 검색보다, **프로젝트 정책/전략/리스크 규칙을 근거로 답변하게 하기 위한 목적**으로 사용했다.

왜 사용했는가:
1. 운영 규칙, 리스크 한도, 프로젝트 정책은 hallucination이 가장 위험한 영역이다.
2. 따라서 문서 기반 근거 검색 후 답변하는 구조가 적절했다.
3. 추후에는 전략 규칙 + 과거 사례 기반으로 확장해 “변경 제안의 설명 근거”까지 연결할 수 있다.

실제 활용:
- PGVector + OpenAI embeddings로 문서 임베딩 저장
- top-k retrieval 후 간결한 한국어 답변 생성
- usage event도 함께 남겨 embedding/query 비용을 추적

근거:
- Charter의 RAG position: [PROJECT_CHARTER.md](/home/syt07203/workspace/coin-pilot/docs/PROJECT_CHARTER.md)
- 구현: [rag_agent.py](/home/syt07203/workspace/coin-pilot/src/agents/rag_agent.py)
- 후속 계획: [28 plan](/home/syt07203/workspace/coin-pilot/docs/work-plans/28_ai_decision_strategy_case_rag_plan.md)

### 4.4 Monitoring Stack: Prometheus / Grafana / Loki / Promtail

모니터링 스택은 단순 “붙여놓은 대시보드”가 아니라, **운영 장애를 실제로 줄이기 위해 점진적으로 확장·보정된 시스템**이다.

왜 사용했는가:
1. 매매/AI/배치/알림/로그 모두가 얽혀 있어, 한 종류의 관측만으로는 RCA가 느리다.
2. 메트릭과 로그를 분리해 각각 Prometheus/Grafana, Loki/Promtail로 관측하는 편이 운영상 명확하다.
3. Alerting과 Discord 라우팅까지 포함하면 “탐지 → 확인 → 대응” 리드타임을 줄일 수 있다.

실제 구현/운영 내용:
- `node-exporter`, `cadvisor`, `container-map`으로 OCI 인프라 관측성 확장
- Loki/Promtail로 중앙 로그 조회 표준화
- Grafana 패널 13개 description 및 threshold 반영
- Alert rule 7개 provisioning 코드화

정량 근거:
- `21-05`: `check_24h_monitoring.sh t1h FAIL 1 -> 0`, Discord Contact point 수신 여부 `0 -> 1`  
  출처: [21-05 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md)
- `21-07`: Loki ingest query `0 -> 1362`, `t1h FAIL 2 -> 0`  
  출처: [21-07 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-07_oci_log_observability_loki_promtail_result.md)
- `21-08`: infra dashboard 패널 수 `8 -> 13`, Loki datasource 패널 수 `0 -> 5`, `t1h WARN 2 -> 1`  
  출처: [21-08 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-08_grafana_loki_log_dashboard_panelization_result.md)

### 4.5 LLM Usage / Cost Observability

이 부분은 AI Engineer / MLOps 직무에서 매우 강한 포인트다.  
많은 프로젝트가 LLM을 호출만 하고 끝나지만, CoinPilot는 **route/provider/model 단위의 usage ledger와 provider snapshot 구조**를 분리해 운영 비용을 추적하려고 했다.

왜 중요했는가:
1. LLM 기능은 성능만큼 비용도 운영 변수다.
2. AI Decision, 챗봇, RAG, 일간 리포트는 서로 호출 특성이 다르다.
3. 따라서 route/provider/model별로 usage를 남기지 않으면 최적화가 불가능하다.

실제 구현:
- `llm_usage_events` 스키마
- usage callback 기반 토큰/비용 기록
- provider 구간 비용 snapshot 구조
- route/provider/model별 집계 스크립트

근거 코드/문서:
- 구현: [llm_usage.py](/home/syt07203/workspace/coin-pilot/src/common/llm_usage.py)
- 운영 리포트: [21-04 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-04_llm_token_cost_observability_dashboard_result.md)

### 4.6 Canary / Fallback

이 프로젝트는 “새 모델을 바꿔 끼웠다”가 아니라, **실험 경로를 운영 안전성과 함께 설계했다**는 점이 중요하다.

핵심:
- deterministic hash 기반 canary routing
- primary / canary 모델 분리
- canary 키 누락 시 cross-provider 임의 우회가 아니라 primary fallback
- 결과는 `agent_decisions.model_used`와 리포트 스크립트로 관측

정량 근거:
- 72h 관측에서 `primary=25`, `canary=6` 실제 분리 관측
- canary env 유효 개수 `0 -> 7`
- 비활성 오해 상태에서 “정상 활성, 다만 표본 부족” 상태로 정정

출처:
- [21-03 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-03_ai_decision_model_canary_experiment_result.md)

### 4.7 Rule Funnel / Strategy Feedback

이 두 작업은 “그냥 전략을 고친다”가 아니라, **왜 AI decision이 적은지, 왜 전략 변경이 필요한지, 지금 변경해도 되는지**를 데이터로 판단하는 계층이다.

Rule Funnel의 의미:
- `rule_pass`
- `risk_reject`
- `ai_prefilter_reject`
- `ai_guardrail_block`
- `ai_confirm / ai_reject`

즉, “AI가 안 좋다” 같은 막연한 말 대신 **Rule / Risk / AI 어느 단계가 병목인지**를 레짐별로 분리한다.

Strategy Feedback의 의미:
- 최근 7일 보고 + 14일 승인 창 + 30일 fallback
- `hold / reviewable / strong_approval`
- `recommend / hold / discard`
- 승인 전 자동 적용 금지

정량 근거:
- `29-01` 72h 운영 관측: `SIDEWAYS rule_pass=12`, `risk_reject=12`, `BULL=0`, `AI stage=0`
- 이후 Discord 리포트에서 `SIDEWAYS: rule_pass=21, risk_reject=21...` 표시 확인
- `30` OCI 실행: `gate_result=discard`, `approval_tier=reviewable`, `sell_samples=16`, `ai_decisions=544`, `bull_rule_pass=0`, `avg_realized_pnl_pct=-0.6369`, `profit_factor=0.5807`

출처:
- [29-01 result](/home/syt07203/workspace/coin-pilot/docs/work-result/29-01_bull_regime_rule_funnel_observability_and_review_automation_result.md)
- [30 result](/home/syt07203/workspace/coin-pilot/docs/work-result/30_strategy_feedback_automation_spec_first_result.md)

---

## 5. 수치로 어필할 수 있는 핵심 근거

| 주제 | 수치 | 의미 | 출처 |
|---|---:|---|---|
| 21-05 인프라 모니터링 | `t1h FAIL 1 -> 0` | 인프라 관측 경로 정상화 | [21-05 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md) |
| 21-05 알림 연동 | Discord Contact point `0 -> 1` | 운영 알림 경로 실제 검증 | [21-05 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md) |
| 21-07 로그 관측 | Loki ingest `0 -> 1362` | 중앙 로그 파이프라인 실가동 | [21-07 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-07_oci_log_observability_loki_promtail_result.md) |
| 21-08 대시보드 확장 | 패널 `8 -> 13` | 운영 판독력 향상 | [21-08 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-08_grafana_loki_log_dashboard_panelization_result.md) |
| 21-08 Loki 패널 | `0 -> 5` | 로그 축 대시보드 상시 관측화 | [21-08 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-08_grafana_loki_log_dashboard_panelization_result.md) |
| 21-03 canary env | 핵심 env `0 -> 7` | canary 운영 경로 복구 | [21-03 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-03_ai_decision_model_canary_experiment_result.md) |
| 21-03 canary 실행 | `canary 0 -> 6` (72h) | 모델 실험 경로 실제 활성 | [21-03 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-03_ai_decision_model_canary_experiment_result.md) |
| 29-01 funnel 운영화 | `rule_funnel_events 0 -> 운영 적재 확인` | 병목 원인 분해 계층 도입 | [29-01 result](/home/syt07203/workspace/coin-pilot/docs/work-result/29-01_bull_regime_rule_funnel_observability_and_review_automation_result.md) |
| 30 전략 피드백 자동화 | 신규 테스트 `3 passed` | 승인형 자동화 PoC 검증 | [30 result](/home/syt07203/workspace/coin-pilot/docs/work-result/30_strategy_feedback_automation_spec_first_result.md) |

---

## 6. 내 역할을 어떻게 서술하면 좋은가

### 6.1 강하게 쓸 수 있는 역할 정의

- “규칙 기반 자동매매 시스템 위에 AI 보조 의사결정과 운영 관측 계층을 설계·구현했다.”
- “모델 성능 자체보다 운영 가능한 구조를 만드는 데 집중했다.”
- “장애가 발생했을 때 재현 조건, 원인, before/after 수치, 재발 방지 기준까지 문서화하는 방식으로 운영 체계를 정착시켰다.”

### 6.2 약하게 쓰면 안 되는 표현

- “AI가 시장을 예측해서 매매한다”
- “LLM으로 수익률을 높였다”
- “완전 자동 매매 최적화 시스템”

이 프로젝트의 진짜 강점은
- 수익률 과장이 아니라
- **운영 가능한 AI 시스템 설계**
- **Fallback/Guardrail/Observability**
- **승인형 변경 프로세스**
입니다.

---

## 7. 포트폴리오 페이지 구조 추천

### 7.1 1페이지 버전
1. 프로젝트 한 줄 소개
2. 시스템 아키텍처 다이어그램
3. 기술 스택과 선택 이유
4. 내가 맡은 핵심 구현 4개
5. 정량 성과 5개
6. 트러블슈팅 사례 2개

### 7.2 기술 부록으로 같이 제출하면 좋은 문서

아래 3개 문서를 포트폴리오 부록이나 Notion 하위 페이지로 함께 두면, "말만 번듯한 설명"이 아니라 실제 시스템 설계 자료를 갖고 있다는 인상을 줄 수 있다.

1. [coinpilot_system_architecture_reference.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/coinpilot_system_architecture_reference.md)
2. [coinpilot_data_flow_reference.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/coinpilot_data_flow_reference.md)
3. [coinpilot_service_flow_reference.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/coinpilot_service_flow_reference.md)

추천 활용 방식:
- 자기소개서/포트폴리오 본문에는 이 문서의 1~2페이지 요약만 사용
- 면접/과제 제출/기술 질문 대응에는 위 3개 레퍼런스를 근거 자료로 활용

### 7.3 제출용 문서로 바로 가져다 쓸 수 있는 추가 산출물

1. [ai_engineer_mlop_one_page_self_intro.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/ai_engineer_mlop_one_page_self_intro.md)
2. [role_specific_project_intro_ai_engineer_vs_mlops.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/role_specific_project_intro_ai_engineer_vs_mlops.md)

### 7.2 깊이 있는 버전
1. 왜 “Prediction” 대신 “Reaction”이었는가
2. Rule Engine + Risk Manager + AI Assistant 구조
3. LangChain / LangGraph / RAG / SQL Agent 설계
4. 운영 관측: Prometheus / Grafana / Loki / Discord / n8n
5. 비용과 실험: canary / usage ledger / snapshot
6. 전략 개선 루프: Rule Funnel / Strategy Feedback
7. 장애 대응 사례와 정량 근거
8. 내가 배운 점 / 한계 / 다음 단계

---

## 8. 자기소개서 문장 예시

### 8.1 지원동기형

저는 AI 기능을 “붙이는 것”보다, AI를 실제 운영 가능한 시스템 안에 안전하게 넣는 과정에 더 큰 흥미를 느낍니다. CoinPilot 프로젝트에서는 규칙 기반 자동매매 시스템 위에 AI Analyst/Guardian, RAG, canary, 비용 관측, Rule Funnel, 전략 피드백 게이트를 단계적으로 구축하며, 모델 품질뿐 아니라 실패 대응·비용·관측성까지 포함한 AI 운영 구조를 설계했습니다. 이런 경험은 AI Engineer와 MLOps 직무에서 요구하는 시스템 설계 역량과 운영 감각을 동시에 보여준다고 생각합니다.

### 8.2 문제 해결형

CoinPilot에서 제가 가장 중요하게 본 문제는 “AI가 잘 대답하는가”가 아니라 “AI가 실패해도 시스템이 안전하게 운영되는가”였습니다. 그래서 거래 코어는 Rule Engine과 Risk Manager에 두고, AI는 보조 판단 계층으로 제한했습니다. 또한 canary routing, usage ledger, provider cost snapshot, Loki/Grafana 기반 운영 관측, Rule Funnel과 Strategy Feedback Gate를 통해 감이 아닌 데이터로 운영 판단을 할 수 있는 구조를 만들었습니다.

### 8.3 협업/운영형

저는 구현 이후의 운영 단계를 중요하게 생각합니다. CoinPilot에서는 plan-result-troubleshooting 구조를 기준으로, 문제의 증상·영향·재현 조건·root cause·before/after 수치까지 남기는 방식으로 문서를 관리했습니다. 그 결과 단순한 기능 추가가 아니라, 장애 재발 방지와 승인형 운영 프로세스까지 함께 정리할 수 있었습니다.

---

## 9. 실거래(Upbit 실제 돈 거래) 이야기를 어떻게 다룰 것인가

현재 기준 추천:
- “실거래 연동이 가능하도록 설계된 시스템”
- “실거래 운영을 염두에 두고 리스크 규칙, fallback, 관측, 승인형 변경 루프를 설계”
- “실거래 성과”를 중심 성과로 쓰지 않기

이유:
1. AI Engineer / MLOps 지원에서 더 중요한 것은 수익률보다 운영 구조다.
2. 실거래 수익은 시장 국면에 좌우돼 재현성과 일반성이 약하다.
3. 반면 이 프로젝트의 설계/관측/운영 자동화는 직무 역량과 직접 연결된다.

즉, 실제 돈 거래는 “추가 신뢰 보강 요소”로 짧게 언급하는 건 괜찮지만, 핵심 메시지는 아니다.

---

## 10. 이 프로젝트에서 가장 강하게 어필할 수 있는 문장 10개

1. Rule Engine과 Risk Manager를 코어로 두고, AI를 실패 허용 가능한 보조 계층으로 제한한 아키텍처를 설계했습니다.
2. LangGraph 기반 라우팅으로 SQL, RAG, 전략 리뷰, 리스크 진단 같은 이질적인 AI 작업을 분리했습니다.
3. LLM 호출을 route/provider/model 단위로 usage ledger에 기록하고 비용 관측 구조를 설계했습니다.
4. deterministic canary routing과 primary fallback으로 모델 실험을 운영 안전성과 함께 설계했습니다.
5. Prometheus, Grafana, Loki, Promtail을 붙여 메트릭과 로그를 모두 관측 가능한 운영 환경을 만들었습니다.
6. Discord와 n8n을 통해 운영 알림, 주간 리포트, 퍼널 요약을 실제 운영 채널로 연결했습니다.
7. Rule Funnel을 도입해 Rule/Risk/AI 어느 단계가 병목인지 레짐별로 분해할 수 있게 했습니다.
8. 전략 변경은 자동 적용이 아니라 `hold/reviewable/strong_approval` 게이트를 거치는 승인형 구조로 설계했습니다.
9. 장애 대응 시 원인과 before/after 수치를 문서화해 재발 방지까지 추적했습니다.
10. 이 프로젝트를 통해 AI 모델 자체보다 AI 시스템 운영 구조를 설계하는 역량을 강화했습니다.

---

## 11. 실제 제출 전 체크포인트

1. “돈을 벌었다”보다 “운영 가능한 구조를 만들었다”가 중심인가
2. 미완료 항목(`21-03`, `21-04`, `29-01`, `30`)을 완료처럼 쓰지 않았는가
3. 수치는 결과 문서와 일치하는가
4. 실거래/실수익을 과장하지 않았는가
5. AI Engineer / MLOps 관점의 키워드가 분명한가

---

## 12. References

- [PROJECT_CHARTER.md](/home/syt07203/workspace/coin-pilot/docs/PROJECT_CHARTER.md)
- [README.md](/home/syt07203/workspace/coin-pilot/README.md)
- [DEEP_LEARNING_GUIDE.md](/home/syt07203/workspace/coin-pilot/docs/DEEP_LEARNING_GUIDE.md)
- [21-03 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-03_ai_decision_model_canary_experiment_result.md)
- [21-04 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-04_llm_token_cost_observability_dashboard_result.md)
- [21-05 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md)
- [21-07 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-07_oci_log_observability_loki_promtail_result.md)
- [21-08 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-08_grafana_loki_log_dashboard_panelization_result.md)
- [24 result](/home/syt07203/workspace/coin-pilot/docs/work-result/24_discord_mobile_chatbot_query_result.md)
- [27 result](/home/syt07203/workspace/coin-pilot/docs/work-result/27_ci_pipeline_dependency_and_test_env_fix_result.md)
- [29 result](/home/syt07203/workspace/coin-pilot/docs/work-result/29_regime_transition_strategy_evaluation_and_hotfix_result.md)
- [29-01 result](/home/syt07203/workspace/coin-pilot/docs/work-result/29-01_bull_regime_rule_funnel_observability_and_review_automation_result.md)
- [30 result](/home/syt07203/workspace/coin-pilot/docs/work-result/30_strategy_feedback_automation_spec_first_result.md)
