# CoinPilot - 이력서/자기소개서용 프로젝트 서술

작성일: 2026-03-11
용도: 이력서 프로젝트 항목, 자기소개서 프로젝트 경험 서술
대상 직무: AI Engineer / MLOps / Backend Engineer

---

## 1. 이력서용 프로젝트 요약 (짧은 버전)

**CoinPilot — AI-Assisted 규칙 기반 암호화폐 자동매매 시스템**
기간: 2025.12 ~ 현재 (1인 개발)
기술: Python, FastAPI, PostgreSQL(TimescaleDB/pgvector), LangGraph, Redis, Docker, Prometheus/Grafana/Loki, OCI

- Rule Engine + Risk Manager 기반 매매 코어 위에 LLM 보조 의사결정(Analyst/Guardian) 계층 설계
- LangGraph 멀티에이전트 라우팅(SQL Agent, RAG Agent, 전략리뷰), deterministic canary routing 구현
- Prometheus/Grafana/Loki 기반 관측 체계 구축 — 로그 수집 0→1,362건/5min, 모니터링 장애 FAIL 1→0
- Rule Funnel + Strategy Feedback Gate로 전략 병목을 레짐별 정량 분해 (SIDEWAYS risk_reject 108건 중 max_per_order 병목 102건 식별)
- CI/CD 파이프라인 구축 (Bandit + pip-audit + pytest, 테스트 70건 통과)

---

## 2. 자기소개서용 — 문제-해결-결과 구조

### 경험 1: AI 보조 의사결정 시스템의 안전한 설계

**[문제]**
암호화폐 자동매매 시스템에 LLM을 도입할 때, LLM의 비결정성(hallucination, timeout, provider 장애)이 실거래 안정성을 위협하는 문제가 있었습니다. AI가 직접 매매를 결정하는 구조는 장애 시 전체 시스템이 멈추거나 의도하지 않은 거래를 실행할 위험이 있었습니다.

**[해결]**
거래 실행의 코어를 Rule Engine(RSI/MA/BB 기반 레짐별 진입 조건)과 Risk Manager(일일 손실 -3% 한도, 단일 포지션 20% 한도, 동시 5포지션 제한 등)에 두고, AI를 실패 허용 가능한 보조 계층으로 제한하는 아키텍처를 설계했습니다. AI Analyst가 CONFIRM/REJECT + 신뢰도를 판단하고, Guardian이 2차 리스크 검증을 수행하되, timeout(40초) 또는 파싱 실패 시 보수적 REJECT로 fallback하도록 구현했습니다.

**[결과]**
- AI provider 장애/timeout 발생 시에도 매매 시스템 무중단 운영 달성
- AI 의사결정 544건 운영 기록, AI reject rate 96.9%로 보수적 필터링 정상 작동 확인
- Claude Haiku 4.5(주) / GPT-4o-mini(카나리 10~20%) 간 deterministic hash 기반 A/B 실험 체계 구축, 72시간 관측에서 primary 25건 / canary 6건 분리 운영 확인

**[도메인]**
금융(암호화폐) × AI 시스템 설계 — LLM의 비결정성을 금융 도메인의 안전성 요구사항과 양립시킨 아키텍처

---

### 경험 2: 운영 관측 체계 구축과 장애 대응

**[문제]**
OCI ARM VM(A1.Flex) + Docker Compose 환경에서 매매 봇, AI 에이전트, 데이터 수집기, 알림 서비스 등 10개 이상의 컨테이너가 동시에 운영되었으나, 메트릭과 로그가 분산되어 장애 발생 시 Root Cause Analysis가 느렸습니다. 또한 cAdvisor의 컨테이너 메트릭 수집 실패, Promtail의 Docker API 버전 불일치 등 관측 인프라 자체의 장애가 반복되었습니다.

**[해결]**
Prometheus + Grafana(메트릭) / Loki + Promtail(로그) / n8n + Discord(알림)를 분리 적용하고, 각 계층의 장애를 독립적으로 진단할 수 있도록 구성했습니다. cAdvisor 메트릭 수집 실패 시 커스텀 `coinpilot-container-map` 사이드카를 개발해 Prometheus textfile 방식으로 우회했고, Promtail은 Docker API 의존을 제거하고 file-target 수집 방식으로 전환했습니다. 24시간 모니터링 자동화 스크립트(`check_24h_monitoring.sh`)를 작성하고 cron 기반으로 정기 실행하도록 구성했습니다.

**[결과]**
- Loki 로그 수집량: 5분 기준 0건 → 1,362건 (중앙 로그 파이프라인 정상화)
- Grafana 대시보드 패널: 8개 → 13개 (Loki 로그 패널 5개 신설)
- 인프라 모니터링 체크: t1h FAIL 1 → 0, 알림 Contact Point 수신 0 → 1 (Discord 알림 경로 실가동)
- Grafana Alert Rule 7개 YAML provisioning 코드화
- 모니터링 자동화: cron 기반 `FAIL:0 / WARN:0` 달성

**[도메인]**
DevOps/SRE — 클라우드 환경에서 AI 포함 마이크로서비스의 관측성 확보 및 운영 자동화

---

### 경험 3: 데이터 기반 전략 진단 체계 설계

**[문제]**
매매 전략의 성과가 좋지 않을 때, "AI 모델이 나쁜 것인지, 진입 규칙이 너무 보수적인 것인지, 리스크 한도가 병목인 것인지" 원인을 특정할 수 없었습니다. 또한 전략 파라미터 변경을 감에 의존해 적용하는 것은 운영 리스크가 컸습니다.

**[해결]**
Rule Funnel을 도입해 매매 파이프라인의 각 단계(Rule pass → Risk reject → AI prefilter → AI guardrail → AI confirm/reject)를 레짐(BULL/SIDEWAYS/BEAR)별로 기록하고, 어느 단계가 병목인지 정량적으로 분해할 수 있게 했습니다. 이어서 Strategy Feedback Gate를 만들어, 최근 7일/14일/30일 데이터를 기반으로 `hold / reviewable / strong_approval` + `recommend / hold / discard` 판정을 자동 산출하고, 승인 없이는 전략이 자동 적용되지 않는 구조를 설계했습니다.

**[결과]**
- Rule Funnel 분석으로 SIDEWAYS 레짐의 핵심 병목 식별: rule_pass 113건 중 risk_reject 108건, 그 중 max_per_order 한도 병목 102건 (전체 병목의 94.4%)
- Strategy Feedback Gate OCI 운영: sell_samples 16건, profit_factor 0.5807, gate_result=discard → "데이터가 변경안 폐기를 지시"하는 근거 기반 판단 실현
- 백테스트 4개 시나리오 비교: transition_sensitive 시나리오에서 승률 40%→66.7%, PnL -4,408원→+4,687원 개선 확인, 단 장기 윈도우에서 Profit Factor <1.0으로 적용 보류 판단

**[도메인]**
퀀트/데이터 분석 — 감이 아닌 정량 근거 기반의 전략 운영 판단 체계

---

### 경험 4: LangGraph 멀티에이전트 시스템 설계

**[문제]**
운영 중 발생하는 질의(포지션 조회, 문서 검색, 전략 분석, 리스크 진단)가 성격이 서로 달라, 단일 LLM 프롬프트로 처리하면 품질과 추적성이 모두 떨어지는 문제가 있었습니다.

**[해결]**
LangGraph 상태 기반 라우터를 구현해 질의를 `db_query`(SQL Agent), `doc_search`(RAG Agent), `strategy_review`, `risk_diagnosis` 등으로 분기시켰습니다. SQL Agent는 read-only 자연어 SQL 변환, RAG Agent는 pgvector + OpenAI 임베딩 기반 문서 검색, Premium review 경로는 전략/리스크 장단점 분석을 각각 전담하도록 설계했습니다. 모든 경로의 LLM 호출을 route/provider/model 단위 usage ledger에 기록해 비용을 분리 추적할 수 있게 했습니다.

**[결과]**
- 4가지 질의 유형을 의도 분류 → 전문 에이전트 라우팅으로 분리, 각 경로의 비용/오류를 독립 추적 가능
- LLM 비용 $0.86/544 의사결정 (건당 약 $0.0016) 수준의 비용 효율 달성
- Discord 슬래시 커맨드 5종(/status, /position, /daily, /ask, /force_report) 연동으로 모바일 운영 실현
- RAG 프롬프트 튜닝으로 의사결정 드리프트 80% → 0% 해소, 신뢰도 편차 -22.4pt → -2.8pt로 안정화

**[도메인]**
AI Engineering — 이질적 AI 작업의 멀티에이전트 라우팅 및 운영 비용 관측

---

## 3. 이력서용 정량 성과 요약표

| 영역 | 지표 | Before → After |
|------|------|----------------|
| 관측성 | Loki 로그 수집 (5min) | 0건 → 1,362건 |
| 관측성 | 모니터링 체크 FAIL | 1 → 0 |
| 관측성 | Grafana 대시보드 패널 | 8개 → 13개 |
| 관측성 | Grafana Alert Rule | 0개 → 7개 (provisioned) |
| AI 안정성 | RAG 의사결정 드리프트 | 80% → 0% |
| AI 안정성 | RAG 신뢰도 편차 | -22.4pt → -2.8pt |
| AI 운영 | Canary 분리 운영 (72h) | primary 25건 / canary 6건 |
| AI 비용 | 의사결정 건당 LLM 비용 | ~$0.0016/건 |
| 전략 분석 | 병목 원인 식별 | max_per_order 병목 102/108건 (94.4%) |
| 백테스트 | transition_sensitive 승률 | 40% → 66.7% |
| CI/CD | 자동화 테스트 | 70건 통과, 보안 스캔(Bandit+pip-audit) 포함 |
| 인프라 | 컨테이너 서비스 | 10+ 컨테이너 Docker Compose 운영 |

---

## 4. 기술 스택 정리

| 분류 | 기술 |
|------|------|
| Language | Python 3.10+ |
| Backend | FastAPI, uvicorn |
| Database | PostgreSQL 16 + TimescaleDB + pgvector |
| Cache | Redis |
| AI/LLM | LangChain, LangGraph, Claude Haiku 4.5, GPT-4o-mini |
| Embedding | OpenAI Embeddings + pgvector |
| Analytics | GARCH 변동성 모델 (PyTorch) |
| Infra | OCI (ARM A1.Flex), Docker Compose, Minikube |
| Monitoring | Prometheus, Grafana, Loki, Promtail |
| Alerting | n8n, Discord Webhook |
| CI/CD | GitHub Actions (Bandit, pip-audit, pytest) |
| Dashboard | Streamlit (7페이지) |

---

## 5. 자기소개서 완성 예시 — 문제해결 중심

저는 AI 기능을 단순히 서비스에 붙이는 것이 아니라, **실패해도 안전하게 동작하는 구조** 안에 AI를 배치하는 데 관심을 가진 엔지니어입니다.

CoinPilot 프로젝트에서 저는 암호화폐 자동매매 시스템에 LLM 보조 의사결정을 도입하면서, AI의 비결정성이 실거래 안정성을 위협하는 문제를 마주했습니다. 이를 해결하기 위해 거래 코어를 Rule Engine과 Risk Manager에 두고, AI는 Analyst/Guardian 2단계 보조 검증 계층으로 제한하는 아키텍처를 설계했습니다. timeout이나 provider 장애 시 보수적 REJECT로 fallback하도록 구현해, AI 장애 상황에서도 매매 시스템의 무중단 운영을 달성했습니다.

운영 과정에서는 "왜 AI 의사결정이 적은가"라는 질문에 감이 아닌 데이터로 답하기 위해, Rule Funnel을 도입해 매매 파이프라인의 각 단계를 레짐별로 정량 분해했습니다. 그 결과 SIDEWAYS 레짐에서 risk_reject 108건 중 max_per_order 한도 병목이 102건(94.4%)을 차지한다는 사실을 식별하고, Strategy Feedback Gate를 통해 승인 기반으로 전략 변경 여부를 판단하는 구조를 만들었습니다.

관측 체계 측면에서는 10개 이상의 컨테이너가 동시에 운영되는 OCI 클라우드 환경에서 Prometheus/Grafana(메트릭) + Loki/Promtail(로그) + Discord(알림)를 분리 적용하고, 관측 인프라 자체의 장애(cAdvisor 수집 실패, Promtail API 불일치)를 사이드카 개발과 아키텍처 전환으로 해결해 로그 수집 0건→1,362건/5분, 모니터링 FAIL 1→0으로 정상화했습니다.

또한 LangGraph 기반 멀티에이전트 라우팅으로 SQL 조회, RAG 문서 검색, 전략 리뷰, 리스크 진단을 분리하고, RAG 도입 시 발생한 의사결정 드리프트(80%)를 프롬프트 튜닝으로 0%까지 해소하며, 모든 경로의 LLM 비용을 route/provider/model 단위로 추적할 수 있는 구조를 구현했습니다.

이 프로젝트를 통해 저는 "AI가 얼마나 똑똑한가"보다 "AI가 실패해도 시스템이 안전하게 운영되는가"를 고민하는 엔지니어로 성장했습니다.

---

## 6. [메모] 미구현 항목 완료 시 어필 포인트 및 자기소개서 수정 가이드

### 6.1 Upbit 실거래 연동 완료 시

**추가 어필 포인트:**
- "Paper Trading → 실거래 전환까지 포함한 End-to-End 자동매매 시스템 구축"
- 실거래 Reconciliation(주문-체결-잔고 대조) 자동화 경험
- 실제 자금을 다루는 시스템에서의 안전장치(일일 손실 한도, 비상 정지, 주문 재시도 정책) 운영 경험

**정량 수치 후보:**
- 실거래 운영 기간 (예: "3개월 실거래 운영")
- 총 거래 건수, 승률, Profit Factor
- 최대 드로다운 대비 회복 시간
- Reconciliation 불일치 발견 건수 및 자동 해소율
- 실거래 전환 후에도 시스템 무중단 운영 일수

**자기소개서 수정 방향:**
- 현재: "실거래 운영을 염두에 두고 리스크 규칙, fallback, 관측, 승인형 변경 루프를 설계"
- 변경: "Paper Trading에서 실거래까지 점진적으로 전환하며, 주문-체결-잔고 Reconciliation 자동화와 일일 손실 한도 기반 비상 정지를 포함한 실운영 체계를 구축했습니다. X개월간 Y건의 실거래를 처리하며 Reconciliation 불일치 Z건을 자동 감지·해소했습니다."

**경험 서술 추가안 (문제-해결-결과):**
- 문제: Paper Trading과 실거래 간 주문 실행 차이(슬리피지, 부분 체결, API rate limit)로 인해 시뮬레이션 성과와 실제 성과가 괴리
- 해결: exchange_orders/exchange_fills/reconciliation_runs 스키마 설계, 주문-체결 대조 자동화, 부분 체결 처리 로직 구현
- 결과: (실제 수치로 채울 것)

---

### 6.2 AI Decision RAG 라이브 운영 완료 시

**추가 어필 포인트:**
- "RAG 도입 시 발생한 AI 의사결정 드리프트를 정량 진단하고 프롬프트 엔지니어링으로 해소한 경험"
- 전략 문서 + 과거 사례를 근거로 AI 판단의 설명 가능성(Explainability) 향상
- RAG가 실운영 의사결정 품질에 미치는 영향을 A/B(canary) 실험으로 검증

**정량 수치 후보:**
- RAG 적용 전후 의사결정 드리프트율: 80% → 0% (이미 확보)
- RAG 적용 전후 신뢰도 편차: -22.4pt → -2.8pt (이미 확보)
- RAG 적용 후 latency 변화: p50 6.5s → 7.6s (+16.3%) (이미 확보)
- RAG 적용 후 비용 변화: $0.0054 → $0.0069/건 (+27.8%) (이미 확보)
- **라이브 canary 운영 후 추가 수치:**
  - RAG-on vs RAG-off 간 승률/PnL 차이
  - RAG-on 의사결정의 사후 검증(Post-Exit Tracker) 정확도
  - canary N>=20 달성 후 통계적 유의성 여부

**자기소개서 수정 방향:**
- 현재: "RAG 프롬프트 튜닝으로 의사결정 드리프트 80%→0% 해소"
- 변경: "RAG 도입 초기 의사결정 드리프트 80%를 프롬프트 순서 재배치와 Analyst 경계 가드 텍스트로 0%까지 해소하고, 이후 canary 실험을 통해 RAG-on 그룹의 의사결정이 사후 검증에서 X% 더 정확한 판단을 내린다는 것을 확인했습니다. 이 과정에서 RAG가 단순 답변 보강이 아니라 의사결정 품질에 실제로 기여하는지를 정량적으로 검증하는 체계를 만들었습니다."

**경험 서술 추가안 (문제-해결-결과):**
- 문제: 전략 문서와 과거 사례를 RAG로 주입했더니, Analyst의 기존 판단 경계가 무너져 SIDEWAYS 레짐에서 CONFIRM 68~72 → REJECT 42로 대량 드리프트 발생 (80%)
- 해결: (1) 프롬프트 순서를 사례 우선(cases-first)으로 변경, (2) 전략 요약을 9줄→4줄로 압축, (3) Analyst 경계 가드 텍스트 추가, (4) Replay 도구로 동일 입력 대비 before/after 비교 검증
- 결과: 드리프트 0%, 신뢰도 편차 -2.8pt, latency +16.3% (허용 범위), 비용 +27.8% (모니터링 지속). 이후 canary 실험에서 RAG-on 그룹이 (실제 결과로 채울 것)

---

### 6.3 두 항목 모두 완료 시 자기소개서 전체 톤 변경 가이드

**현재 톤:**
"운영 가능한 AI 시스템 설계"에 초점. Paper Trading 기반이므로 설계/관측/안전성 강조.

**변경 톤:**
"설계부터 실운영까지 End-to-End로 검증한 AI-Assisted 자동매매 시스템"으로 격상.

**추가 강조 가능 메시지:**
1. "Paper Trading으로 안전성을 검증한 뒤, 실거래로 점진 전환하며 Reconciliation과 비상 정지까지 운영한 풀사이클 경험"
2. "RAG를 통한 AI 판단의 설명 가능성 향상을 canary 실험으로 정량 검증한 경험"
3. "설계 → 관측 → 실험 → 실운영까지 이어지는 AI 시스템 라이프사이클 전체를 경험"

**자기소개서 마지막 문단 수정안:**
- 현재: "이 프로젝트를 통해 저는 'AI가 얼마나 똑똑한가'보다 'AI가 실패해도 시스템이 안전하게 운영되는가'를 고민하는 엔지니어로 성장했습니다."
- 변경: "이 프로젝트를 통해 저는 AI 시스템의 설계, 관측, 실험, 실운영까지 전체 라이프사이클을 경험했으며, 'AI가 얼마나 똑똑한가'보다 'AI가 실패해도 안전하게 운영되는가, 그리고 그 판단을 어떻게 데이터로 검증하는가'를 고민하는 엔지니어로 성장했습니다."
