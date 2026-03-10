# CoinPilot 기반 1페이지 자기소개 초안

작성일: 2026-03-10  
용도: 서류 제출용 자기소개서 초안 / 1페이지 압축 버전  
대상 직무: AI Engineer / MLOps

---

저는 AI 기능을 단순히 제품에 붙이는 것보다, **AI를 실제 운영 가능한 시스템 안에 안전하게 넣는 과정**에 더 큰 흥미를 느끼는 엔지니어입니다. CoinPilot 프로젝트는 이런 제 관심사가 가장 잘 드러나는 사례입니다. 이 프로젝트에서 저는 Upbit 시장을 대상으로 한 규칙 기반 자동매매 시스템 위에 AI 보조 의사결정, LLM 비용 관측, 로그/메트릭 모니터링, 승인형 전략 피드백 루프를 단계적으로 구축했습니다.

CoinPilot의 핵심 설계 원칙은 명확합니다. 저는 거래 실행의 코어를 LLM이 아니라 **Rule Engine과 Risk Manager**에 두었습니다. 금융 시스템에서는 설명 가능성과 재현성, 그리고 실패 시 안전한 동작 방식이 무엇보다 중요하다고 봤기 때문입니다. 실제로 CoinPilot에서는 RSI, MA, 거래량, Bollinger Band와 같은 기술 지표를 기반으로 진입 후보를 만들고, 일일 손실 한도, 단일 주문 한도, 총 노출 한도, 쿨다운 같은 리스크 규칙으로 먼저 차단합니다. AI는 이 코어를 대체하지 않고, Rule Engine이 통과시킨 신호를 **Analyst / Guardian 2단계로 검증**하는 보조 계층만 맡도록 설계했습니다. 이 구조 덕분에 provider overload, timeout, parse fail이 발생해도 시스템은 보수적으로 REJECT 처리되며, 거래 코어 전체가 흔들리지 않도록 만들 수 있었습니다.

또한 저는 “모델 성능”만이 아니라, **운영 중 무엇을 관측할 것인가**를 중요한 문제로 다뤘습니다. CoinPilot에는 route/provider/model 단위의 `llm_usage_events`를 기록하는 usage ledger와, provider 비용 snapshot을 대조하는 구조가 들어 있습니다. 이를 통해 챗봇, RAG, AI Decision, 일간 리포트 같은 서로 다른 경로의 비용과 오류를 나눠 관측할 수 있게 했습니다. 운영 관측 측면에서는 OCI + Docker Compose 환경 위에 Prometheus, Grafana, Loki, Promtail, n8n, Discord를 연결해, 메트릭/로그/알림이 분리되면서도 하나의 운영 루프로 동작하도록 만들었습니다. 실제로 Loki 로그 수집 경로는 운영 검증 과정에서 ingest query 기준 `0 -> 1362`로 회복되었고, 인프라 모니터링 스크립트는 `t1h FAIL 1 -> 0`으로 개선됐습니다. 저는 단순히 스택을 도입하는 데서 끝내지 않고, 왜 실패했는지, 어떻게 재현되는지, before/after가 얼마인지까지 결과 문서와 트러블슈팅 문서로 남기는 방식을 유지했습니다.

이 프로젝트에서 특히 의미 있었던 부분은 **전략 운영을 감이 아니라 데이터로 판단하는 구조**를 만든 것입니다. `Rule Funnel`을 도입해 Rule pass, Risk reject, AI prefilter reject, AI guardrail block, AI confirm/reject를 레짐별로 기록했고, 그 결과 최근 운영 데이터에서는 `SIDEWAYS rule_pass=113`, `risk_reject=108`, 그중 `max_per_order=102`로 AI 이전의 리스크 한도 병목이 크다는 사실을 확인할 수 있었습니다. 이어서 `Strategy Feedback Gate`를 만들어 최근 7일/14일/30일 기준으로 `hold / reviewable / strong_approval`, `recommend / hold / discard`를 나누는 승인형 전략 피드백 루프를 설계했습니다. 이 과정에서 OCI 실행 기준 `sell_samples=16`, `ai_decisions=544`, `profit_factor=0.5807`, `gate_result=discard`가 나왔고, 저는 이를 “자동화가 실패했다”가 아니라 “운영 데이터가 지금은 변경안을 폐기하라고 말한다”는 근거로 해석했습니다. 저는 이런 식으로 시스템이 나쁜 결과를 내더라도, 그 결과를 다음 의사결정의 근거로 활용할 수 있는 구조를 만드는 데 강점이 있습니다.

저는 CoinPilot를 통해 AI Engineer와 MLOps 직무가 만나는 지점을 경험했습니다. LangGraph 기반 질의 라우팅, RAG, SQL Agent, canary routing, usage/cost observability, Rule Funnel, Grafana/Loki 운영, Discord 알림, runbook과 troubleshooting 문서화까지 포함해, **AI 기능을 운영 가능한 시스템으로 만드는 과정 전체**를 설계하고 구현했습니다. 앞으로도 저는 “AI가 얼마나 똑똑한가”보다 “AI가 실패해도 시스템이 안전하게 운영되는가”, “실험과 비용, 장애를 어떻게 관측하고 복구하는가”를 중요하게 생각하는 엔지니어로 성장하고 싶습니다.

---

## 빠른 교체 포인트

- 더 공격적으로 쓰고 싶을 때:
  - `저는 운영 가능한 AI 시스템을 설계하는 데 강점이 있습니다.`
- 더 차분하게 쓰고 싶을 때:
  - `저는 AI 기능을 서비스 안에서 안정적으로 운영하기 위한 구조 설계에 관심이 많습니다.`
- 실거래 표현을 완화하고 싶을 때:
  - `Upbit 시장 데이터를 기반으로 운영한` 정도로 낮춰서 사용
