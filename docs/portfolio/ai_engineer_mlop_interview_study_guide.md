# CoinPilot 면접 / 학습용 스터디 가이드

작성일: 2026-03-10  
대상: AI Engineer / MLOps 면접 대비

---

## 1. 이 문서의 목적

이 문서는 포트폴리오 문서에 적은 내용을 **내가 실제로 이해하고 설명할 수 있도록** 만든 학습 노트다.  
즉, “멋있게 쓰는 문장”이 아니라, 면접관이 꼬리질문했을 때 흔들리지 않도록 **왜 그렇게 설계했는지, 대안은 무엇이었는지, 한계는 무엇인지**를 정리한 문서다.

함께 보면 좋은 보조 문서:
- [coinpilot_system_architecture_reference.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/coinpilot_system_architecture_reference.md)
- [coinpilot_data_flow_reference.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/coinpilot_data_flow_reference.md)
- [coinpilot_service_flow_reference.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/coinpilot_service_flow_reference.md)

---

## 2. CoinPilot를 가장 쉽게 설명하는 방법

### Q. CoinPilot가 뭐예요?

짧은 답변:
- “규칙 기반 자동매매 시스템 위에 AI 보조 판단과 운영 관측 계층을 붙인 프로젝트입니다.”

조금 더 자세한 답변:
- “거래 실행의 코어는 Rule Engine과 Risk Manager가 맡고, AI는 진입 신호 검증, 리스크 점검, 문서 검색, 조회형 챗봇 같은 보조 역할만 맡습니다. 여기에 비용/로그/메트릭 관측과 전략 피드백 자동화까지 붙여 실제 운영 가능한 시스템 형태로 발전시켰습니다.”

쉽게 비유하면:
- “자율주행 자동차라기보다, 사람이 운전하되 고급 운전자 보조 시스템과 계기판, 블랙박스, 정비 리포트를 붙여놓은 구조”라고 설명하면 된다.

---

## 3. 왜 Rule-Based Core를 선택했는가

### 핵심 답변

저는 금융 시스템에서 가장 중요한 것이 **설명 가능성, 재현성, 안전한 실패 방식**이라고 봤습니다.  
LLM은 보조 판단에는 강하지만, 직접 거래 실행의 최종 근거로 두기엔 비결정성과 운영 리스크가 큽니다.  
그래서 거래의 코어는 규칙 기반으로 두고, AI는 검증/조회/설명 계층으로 제한했습니다.

### 꼬리질문 예상

#### Q. 그러면 왜 굳이 AI를 썼나요?

답변:
- 규칙 엔진만으로는 “신호의 질”을 세밀하게 검토하기 어렵습니다.
- 예를 들어 Analyst는 기술적 패턴/맥락을 보고 CONFIRM/REJECT를 보조 판단합니다.
- 또 RAG/SQL Agent는 운영자 질의응답과 정책 검색을 쉽게 만들어줍니다.
- 즉 AI는 거래 코어를 대체하는 게 아니라, **운영자와 시스템의 의사결정 품질을 높이는 도구**로 썼습니다.

#### Q. AI가 실패하면 어떻게 되나요?

답변:
- timeout이나 에러가 나면 보수적으로 REJECT합니다.
- provider overload나 parse fail도 `confidence=0`으로 안전 차단합니다.
- canary가 실패해도 primary fallback으로 설계했습니다.

---

## 4. 왜 LangChain / LangGraph를 썼는가

### 핵심 답변

질의 종류가 너무 달랐기 때문입니다.  
자연어 SQL 조회, 문서 검색형 질의, 전략 리뷰, 리스크 진단, 일반 채팅을 하나의 프롬프트로 처리하면 품질과 추적성이 떨어집니다.  
그래서 LangGraph로 “의도 분류 → 적절한 agent/tool 라우팅” 구조를 만들고, LangChain은 각 체인과 vector store, callback usage 계층에 활용했습니다.

### 쉽게 설명

- LangChain은 “도구 상자”
- LangGraph는 “어떤 도구를 어떤 순서로 쓸지 정하는 흐름도 엔진”

### 꼬리질문 예상

#### Q. 그냥 함수 if-else 분기하면 안 됐나요?

답변:
- 초기엔 가능하지만, agent 종류가 늘어나면 상태 관리와 확장성이 나빠집니다.
- LangGraph를 쓰면 상태, 노드, 종료 조건이 명시적이라 유지보수가 쉽습니다.
- 특히 RAG/SQL/전략 리뷰처럼 서로 다른 실패 모드와 입력 포맷을 가진 작업을 분기하기에 적합했습니다.

#### Q. LangGraph의 단점은?

답변:
- 단순한 서비스에는 과할 수 있습니다.
- 디버깅 포인트가 프레임워크 내부까지 들어갈 수 있습니다.
- 하지만 이 프로젝트는 agent/tool 종류가 많아지는 방향이었기 때문에, 장기 구조상 이득이 더 컸습니다.

---

## 5. 왜 RAG를 넣었는가

### 핵심 답변

프로젝트 정책, 리스크 규칙, 운영 문서는 hallucination이 가장 위험한 영역입니다.  
그래서 일반 지식 답변이 아니라, **문서 기반 근거 검색 후 답변**하게 만들기 위해 RAG를 넣었습니다.

### 꼬리질문 예상

#### Q. 검색 없이 프롬프트에 규칙을 다 넣으면 안 되나요?

답변:
- 문서가 커질수록 프롬프트 길이와 유지보수 비용이 커집니다.
- 정책이 자주 바뀌는데, 프롬프트에 하드코딩하면 최신화가 어렵습니다.
- RAG는 문서 저장소를 source of truth로 유지한 채, 필요한 부분만 검색해서 넣을 수 있습니다.

#### Q. 현재 RAG 한계는?

답변:
- 아직 전략 규칙 + 과거 사례 기반 고도화는 진행 중입니다.
- 현재는 문서 검색형 보조 역할이 중심이고, 향후 28번에서 전략 문서/과거 사례 기반 강화가 예정돼 있습니다.

---

## 6. 왜 Monitoring을 이렇게까지 했는가

### 핵심 답변

이 프로젝트는 배치, 매매 루프, AI 호출, 알림, 챗봇, 비용 수집, 로그 수집이 다 얽혀 있습니다.  
따라서 “서비스가 켜져 있다”만으로는 운영이 되지 않습니다.  
메트릭, 로그, 비용, alerting, runbook까지 같이 있어야 RCA 속도가 나옵니다.

### 역할 분리

- Prometheus: 숫자 메트릭 수집
- Grafana: 시각화와 Alerting
- Loki/Promtail: 로그 수집/탐색
- n8n/Discord: 운영 알림 전달

### 꼬리질문 예상

#### Q. CloudWatch 같은 managed service를 안 쓴 이유는?

답변:
- OCI VM + Compose 기반 운영에서 빠르게 제어 가능한 오픈소스 스택이 필요했습니다.
- Prometheus/Grafana/Loki는 설정이 투명하고, Git으로 패널/알림 규칙을 추적하기 좋았습니다.
- provider 종속성을 줄이는 것도 장점이었습니다.

#### Q. 가장 인상적인 운영 개선은?

답변:
- Loki/Promtail 도입 후 `t1h FAIL 2 -> 0`, Loki ingest query `0 -> 1362`로 중앙 로그 파이프라인을 실제 복구한 경험입니다.
- 단순히 설치가 아니라, API mismatch / timestamp too old / No data 같은 운영 이슈를 단계적으로 해결했습니다.

---

## 7. Canary / Cost Observability를 왜 중요하게 봤는가

### 핵심 답변

AI 시스템은 “성능”만큼 “비용”과 “실험 안전성”도 중요합니다.  
그래서 모델 실험은 deterministic canary routing으로, 비용은 usage ledger + provider snapshot 구조로 관측하도록 설계했습니다.

### 쉽게 설명

- canary: “새 모델을 일부만 섞어 태워보는 실험”
- usage ledger: “우리 시스템이 내부적으로 본 호출 장부”
- provider snapshot: “외부 사업자가 집계한 비용 장부”

### 꼬리질문 예상

#### Q. 왜 provider snapshot이 필요한가요? 내부 비용 계산만 있으면 안 되나요?

답변:
- 내부 장부는 추정입니다.
- 실제 청구 기준과 차이가 날 수 있습니다.
- 그래서 ledger와 snapshot을 reconciliation하는 구조가 필요합니다.

#### Q. 지금 완성됐나요?

답변:
- usage ledger는 동작합니다.
- 다만 provider snapshot은 아직 일부 미완이라 `21-04`가 in_progress 상태입니다.
- 이 점은 “운영적으로 무엇이 미완인지 알고 있고, 그 갭이 어떤 영향인지 이해하고 있다”는 식으로 설명하면 됩니다.

---

## 8. Rule Funnel과 Strategy Feedback을 왜 만들었는가

### 핵심 답변

운영 중 “AI decision이 적다”, “전략이 잘 안 맞는다” 같은 현상은 감으로 해석하면 안 됩니다.  
그래서 Rule → Risk → AI 각 단계의 병목을 분해하는 Rule Funnel을 만들고, 그 결과를 기반으로 전략 변경 가능 여부를 판단하는 Strategy Feedback Gate를 만들었습니다.

### 쉽게 설명

- Rule Funnel은 “지원자 전형 단계별 탈락률 분석”
- Strategy Feedback Gate는 “지금 이 정책을 바꿔도 되는지 승인 심사표”

### 꼬리질문 예상

#### Q. 지금 어떤 병목이 보이나요?

답변:
- 최근 관측에서는 `SIDEWAYS`에서 `rule_pass=113`, `risk_reject=108`, 그중 `max_per_order=102`라 전략보다 주문 한도 병목이 더 큽니다.
- `BEAR`에선 `weak_volume_recovery` prefilter reject가 주요 원인입니다.
- 즉 “AI가 이상하다”가 아니라, 어느 단계에서 막히는지 분해해서 보는 구조가 핵심입니다.

#### Q. 왜 자동 적용까지 안 갔나요?

답변:
- 승인형 운영 원칙 때문입니다.
- 초기에는 `hold / reviewable / strong_approval`로 등급만 내리고, 실제 변경은 수동 승인 뒤에 하도록 설계했습니다.
- 금융/리스크 시스템에서는 이 단계가 필요하다고 판단했습니다.

---

## 9. 내가 이 프로젝트에서 강조해야 할 진짜 역량

### 9.1 AI Engineer로서
- LLM을 시스템 안에서 안전하게 다루는 설계
- multi-agent routing / RAG / tool use
- canary / fallback / usage logging / error handling
- 품질이 아니라 운영까지 포함한 AI lifecycle 사고

### 9.2 MLOps로서
- 실험과 운영을 분리하고 관측하는 구조
- 비용/오류/로그/메트릭을 하나의 운영 관점으로 묶는 사고
- 문서화와 runbook, troubleshooting 체계
- 수동 운영 의존 구간을 점차 자동화/표준화하는 접근

---

## 10. 면접에서 피해야 할 답변

1. “AI가 매매를 결정합니다”
2. “이 프로젝트로 수익을 냈습니다” 중심 서술
3. “Prometheus/Grafana/Loki는 그냥 붙였습니다”
4. “LangGraph는 남들이 많이 써서 썼습니다”

더 좋은 답변:
- “AI는 보조 계층으로 제한했고, 실패 시 fallback되도록 설계했습니다”
- “운영 기준과 비용 관측을 함께 설계했습니다”
- “각 스택은 역할이 명확했습니다”

---

## 11. 자주 나올 꼬리질문과 답변 초안

### Q. 이 프로젝트에서 가장 어려웠던 기술적 문제는?

답변 초안:
- 운영 관측 경로를 안정화하는 과정이 어려웠습니다.
- 예를 들어 Loki/Promtail 도입 시 Docker API mismatch, timestamp too old, Grafana No data 같은 문제가 연쇄적으로 나왔습니다.
- 단순히 설치하는 것이 아니라, 원인을 분리하고 `before/after` 수치와 검증 스크립트까지 정리해 운영 표준으로 만드는 과정이 가장 난이도가 높았습니다.

### Q. 가장 자랑할 만한 설계 선택은?

답변 초안:
- Rule-Based Core + AI Assistant 구조입니다.
- 거래 코어를 규칙 기반으로 두고 AI를 보조 검증/조회 계층으로 분리한 덕분에, AI failure와 운영 안정성을 동시에 관리할 수 있었습니다.

### Q. 이 프로젝트에서 “AI Engineer스럽다”는 지점은?

답변 초안:
- 단순히 LLM 호출이 아니라, task routing, canary, fallback, usage/cost observability, RAG, reviewer 흐름까지 포함해 AI를 시스템적으로 다룬 점입니다.

### Q. 이 프로젝트에서 “MLOps스럽다”는 지점은?

답변 초안:
- 모델/LLM 자체보다 운영 환경에서의 관측, 비용, 알림, 실험 경로, 승인 게이트, 장애 복구까지 하나의 lifecycle로 다룬 점입니다.

---

## 12. 내가 꼭 외워야 하는 숫자

1. `21-05`: `t1h FAIL 1 -> 0`, Discord Contact point `0 -> 1`
2. `21-07`: Loki ingest `0 -> 1362`
3. `21-08`: 패널 수 `8 -> 13`, Loki 패널 `0 -> 5`
4. `21-03`: 72h `primary=25`, `canary=6`
5. `29-01`: `SIDEWAYS rule_pass=12`, `risk_reject=12`, `BULL=0`
6. `30`: `gate_result=discard`, `approval_tier=reviewable`, `sell_samples=16`, `ai_decisions=544`, `PF=0.5807`

이 숫자는 “외워서 자랑”하려는 게 아니라, 면접 중 프로젝트를 실제로 운영해본 사람처럼 설명하기 위한 최소 기준이다.

---

## 13. 이 프로젝트를 공부할 때 추천 순서

1. [PROJECT_CHARTER.md](/home/syt07203/workspace/coin-pilot/docs/PROJECT_CHARTER.md)
2. [README.md](/home/syt07203/workspace/coin-pilot/README.md)
3. [DEEP_LEARNING_GUIDE.md](/home/syt07203/workspace/coin-pilot/docs/DEEP_LEARNING_GUIDE.md)
4. [main.py](/home/syt07203/workspace/coin-pilot/src/bot/main.py)
5. [router.py](/home/syt07203/workspace/coin-pilot/src/agents/router.py)
6. [rag_agent.py](/home/syt07203/workspace/coin-pilot/src/agents/rag_agent.py)
7. [llm_usage.py](/home/syt07203/workspace/coin-pilot/src/common/llm_usage.py)
8. [rule_funnel.py](/home/syt07203/workspace/coin-pilot/src/analytics/rule_funnel.py)
9. [strategy_feedback.py](/home/syt07203/workspace/coin-pilot/src/analytics/strategy_feedback.py)
10. 결과 문서들:
   - [21-03 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-03_ai_decision_model_canary_experiment_result.md)
   - [21-05 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md)
   - [21-07 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-07_oci_log_observability_loki_promtail_result.md)
   - [21-08 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-08_grafana_loki_log_dashboard_panelization_result.md)
   - [29-01 result](/home/syt07203/workspace/coin-pilot/docs/work-result/29-01_bull_regime_rule_funnel_observability_and_review_automation_result.md)
   - [30 result](/home/syt07203/workspace/coin-pilot/docs/work-result/30_strategy_feedback_automation_spec_first_result.md)

---

## 14. 마지막 정리

면접에서 제일 중요한 건 “많이 했다”가 아니라,  
**왜 그렇게 설계했는지, 무엇을 버렸는지, 어떤 리스크를 어떻게 통제했는지**를 말하는 것입니다.

CoinPilot를 이야기할 때는 아래 구조만 기억하면 됩니다.

1. 예측보다 반응
2. Rule-based core + AI assistant
3. 운영 가능한 AI 시스템 설계
4. 비용/로그/메트릭/알림까지 포함한 관측
5. 감이 아니라 gate와 evidence로 변경 판단
