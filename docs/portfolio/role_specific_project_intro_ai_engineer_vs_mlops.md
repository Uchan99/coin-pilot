# CoinPilot 직무별 프로젝트 소개문

작성일: 2026-03-10  
용도: 지원서 / 포트폴리오 / 면접용 직무 맞춤 소개문  
대상: AI Engineer / MLOps

---

## 1. 문서 목적

같은 프로젝트라도 직무에 따라 강조점이 달라진다.  
이 문서는 CoinPilot를 **AI Engineer 관점**과 **MLOps 관점**으로 각각 어떻게 말해야 하는지 정리한 분리본이다.

---

## 2. AI Engineer 버전

### 2.1 3문장 버전

CoinPilot는 규칙 기반 자동매매 시스템 위에 AI 보조 의사결정 계층을 붙인 프로젝트입니다.  
저는 이 프로젝트에서 Analyst / Guardian 2단계 검증, LangGraph 기반 질의 라우팅, RAG, SQL Agent, canary routing, usage logging 같은 AI 시스템 설계를 담당했습니다.  
특히 AI를 직접 거래 실행의 주체로 두지 않고, 실패 시에도 안전하게 fallback되는 보조 계층으로 설계한 점이 핵심입니다.

### 2.2 긴 버전

AI Engineer 관점에서 CoinPilot의 핵심은 "LLM을 얼마나 많이 썼는가"가 아니라, **LLM을 어떤 책임 경계 안에 배치했는가**입니다. 저는 거래 코어를 Rule Engine과 Risk Manager에 두고, AI는 진입 신호 검증과 리스크 리뷰, 문서 검색, 운영 질의응답 같은 보조 역할만 맡도록 설계했습니다. 매수 판단 경로에서는 Rule pass와 Risk pass 이후에만 Analyst / Guardian이 호출되며, timeout, overload, parse fail이 발생하면 보수적으로 REJECT하도록 했습니다. 또한 챗봇 질의는 LangGraph 기반 Router를 통해 SQL, RAG, 전략 리뷰, 리스크 진단 등으로 분기했고, 각 경로의 usage를 `llm_usage_events`에 별도로 남겨 route/provider/model 단위로 추적할 수 있게 했습니다. 이 프로젝트는 단순 LLM 기능 구현보다, **AI를 안전하고 추적 가능한 시스템으로 설계한 경험**을 보여준다고 생각합니다.

### 2.3 AI Engineer 면접에서 강조할 키워드

- multi-agent decision path
- LangGraph state routing
- RAG for policy-grounded answers
- deterministic canary routing
- timeout / overload / parse-fail fallback
- usage logging / cost awareness
- AI as assistant, not as uncontrolled executor

### 2.4 AI Engineer 지원서 문장 예시

> CoinPilot에서는 AI를 거래 실행의 중심이 아니라 보조 판단 계층으로 제한해, 규칙 기반 코어와 AI 보조 시스템의 책임을 분리했습니다. 저는 Analyst/Guardian 2단계 검증, LangGraph 기반 라우팅, RAG, canary, usage logging을 설계하며, 모델 성능뿐 아니라 실패 대응과 추적성을 포함한 AI 시스템 구조를 구현했습니다.

---

## 3. MLOps 버전

### 3.1 3문장 버전

CoinPilot는 OCI + Docker Compose 환경에서 운영한 규칙 기반 자동매매 및 AI 보조 시스템입니다.  
저는 이 프로젝트에서 Grafana/Loki/Prometheus 기반 모니터링, n8n/Discord 알림, LLM usage/cost observability, Rule Funnel, Strategy Feedback Gate, runbook/troubleshooting 체계를 구축했습니다.  
즉 모델 호출 자체보다, **운영 중 비용·오류·로그·전략 병목을 관측하고 복구하는 구조**를 만드는 데 집중했습니다.

### 3.2 긴 버전

MLOps 관점에서 CoinPilot의 핵심은 모델을 배포하는 것보다, **AI 기능이 포함된 전체 시스템을 지속적으로 운영할 수 있게 만든 것**입니다. 저는 OCI VM 위에 Docker Compose 기반 서비스를 운영하면서, Prometheus/Grafana로 메트릭을, Loki/Promtail로 로그를, n8n/Discord로 운영 알림을 연결했습니다. 또한 `llm_usage_events`와 `llm_provider_cost_snapshots`를 통해 내부 usage ledger와 외부 provider 비용을 대조할 수 있는 비용 관측 구조를 설계했고, Rule Funnel로 Rule/Risk/AI 단계 병목을 분해했습니다. 전략 변경 역시 자동 적용이 아니라 `hold / reviewable / strong_approval`과 `recommend / hold / discard`로 나누는 Strategy Feedback Gate를 통해 승인형으로 설계했습니다. 이 프로젝트는 제가 단순 인프라 운영자가 아니라, **AI 시스템의 실험, 비용, 관측, 복구, 운영 정책까지 함께 설계할 수 있는 엔지니어**라는 점을 보여줍니다.

### 3.3 MLOps 면접에서 강조할 키워드

- observability-first operation
- metrics + logs + alerting split
- cost reconciliation
- canary operation
- runtime guardrails
- runbook / troubleshooting / quantified evidence
- approval-based deployment and feedback loop

### 3.4 MLOps 지원서 문장 예시

> CoinPilot에서는 AI 기능을 포함한 서비스를 OCI + Docker Compose 환경에서 운영하면서, Prometheus/Grafana/Loki/Promtail, n8n/Discord, usage/cost observability, Rule Funnel, Strategy Feedback Gate를 연결해 운영 가능한 구조를 만들었습니다. 저는 특히 장애를 재현하고 before/after 수치와 검증 명령을 남기는 방식으로 운영 표준을 만드는 데 강점을 갖고 있습니다.

---

## 4. 같은 질문에 대한 직무별 답변 차이

### Q. 이 프로젝트에서 가장 중요한 기술적 포인트가 무엇인가요?

AI Engineer 답변:
- "AI가 직접 거래를 지배하지 않도록 책임 경계를 나눈 구조입니다."

MLOps 답변:
- "AI가 포함된 시스템을 실제로 운영 가능한 상태로 관측·복구·비용 추적할 수 있게 만든 점입니다."

### Q. 왜 LangGraph를 썼나요?

AI Engineer 답변:
- "이질적인 질의를 intent별 agent/tool로 안정적으로 라우팅하기 위해서입니다."

MLOps 답변:
- "route가 명시적이라 usage/error/cost를 경로별로 추적하기 쉬웠기 때문입니다."

### Q. 왜 Rule Funnel이 중요했나요?

AI Engineer 답변:
- "AI 판단이 적은 이유를 모델 탓이 아니라 Rule/Risk/AI 단계별로 분해할 수 있었기 때문입니다."

MLOps 답변:
- "운영 병목을 정량적으로 보고, 전략 변경 승인 여부를 데이터 기반으로 판단할 수 있게 했기 때문입니다."

---

## 5. 실전 사용 가이드

### 서류 제출 시

- AI Engineer 지원:
  - 2장, 4장 중심
- MLOps 지원:
  - 3장, 4장 중심

### 포트폴리오 발표 시

- 공통 1분:
  - Rule-Based Core + AI Assistant
- 추가 1분:
  - AI Engineer면 AI decision / LangGraph / RAG
  - MLOps면 observability / canary / cost / runbook

### 면접 시

- 먼저 공통 버전으로 설명
- 면접관 질문이 모델 중심이면 AI Engineer 축으로
- 운영/배포/장애 질문이면 MLOps 축으로 바로 전환

---

## 6. 같이 보면 좋은 문서

- [ai_engineer_mlop_self_intro_and_project_showcase.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/ai_engineer_mlop_self_intro_and_project_showcase.md)
- [ai_engineer_mlop_one_page_self_intro.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/ai_engineer_mlop_one_page_self_intro.md)
- [coinpilot_system_architecture_reference.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/coinpilot_system_architecture_reference.md)
- [coinpilot_data_flow_reference.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/coinpilot_data_flow_reference.md)
- [coinpilot_service_flow_reference.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/coinpilot_service_flow_reference.md)
