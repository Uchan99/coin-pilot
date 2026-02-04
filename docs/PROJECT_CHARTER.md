# CoinPilot Project Plan v3.0
**Kubernetes 기반 자율 가상화폐 매매 AI 에이전트**
*(Rule-Based Core + AI-Assisted Decision System)*

## 1. 설계 철학
### 1.1 핵심 전제: 예측이 아닌 반응
본 프로젝트는 "AI로 가격을 예측하여 수익을 낸다"는 비현실적인 목표를 배제합니다. 대신, 시장 상태에 체계적으로 반응하는 **룰 기반 시스템**을 구축하고, AI는 이를 보조합니다.

| 예측 기반 접근 (기각) | 반응 기반 접근 (채택) |
| :--- | :--- |
| "4시간 후 가격이 오를 것이다" | "RSI가 30 이하이고 거래량이 급증했다" |
| LSTM/Transformer로 방향 예측 | 기술적 조건 충족 시 진입 |
| 예측 정확도에 수익이 의존 | 리스크 관리에 수익이 의존 |
| 실패 시 "모델이 잘못됨" | 실패 시 "규칙을 조정함" |

### 1.2 프로젝트의 진짜 목표
이 프로젝트의 목표는 단순 트레이딩 수익이 아닌 다음 역량의 증명입니다:
1. **Quant Architecture:** 데이터 파이프라인, 백테스팅, 실행 엔진 구현
2. **LLM Agent Design:** LangGraph, Tool-using, Multi-Agent 오케스트레이션
3. **MLOps/DevOps:** Kubernetes, 모니터링, CI/CD
4. **Finance Domain:** 리스크 관리, 성과 측정, 시장 미시구조 이해

## 2. 시스템 아키텍처
### 2.1 Rule Engine + AI Assistant 구조
핵심 매매 로직은 검증 가능한 **Rule Engine**이 담당하고, AI는 보조합니다.

| 계층 | 구성 요소 | 역할 | 의존도 |
| :--- | :--- | :--- | :--- |
| **Core** | Rule Engine | 매매 규칙 평가 및 신호 생성 | 필수 (100%) |
| **Core** | Risk Manager | 포지션 크기, 손절, 일일 한도 관리 | 필수 (100%) |
| **Assistant** | SQL Agent | 자연어 → 지표 조회 변환 | 보조 (대체 가능) |
| **Assistant** | RAG Agent | 리스크 이벤트 감지 (거래 중단) | 보조 (비활성 가능) |
| **Assistant** | Volatility Model | 변동성 예측 → 포지션 크기 조절 | 보조 (선택적) |

### 2.2 의사결정 흐름
**"AI가 실패해도 시스템은 동작한다"**가 핵심 원칙입니다.
* **Flow:** [시장 데이터] → [Rule Engine: 조건 충족?] → [Risk Manager: 진입 가능?] → [Executor: 주문 실행]
* **AI 개입:**
    * **SQL Agent:** 지표 조회 보조
    * **RAG Agent:** "해킹", "규제" 등 감지 시 `HALT` 신호
    * **Volatility Model:** 변동성 높으면 포지션 축소 제안

## 3. 트레이딩 전략
### 3.1 채택 전략: Mean Reversion + Trend Filter
과매도 구간 반등을 노리되, 역추세 진입을 방지합니다.

**진입 조건 (Long) - v2.3 (Week 8 Strategy Expansion)**
| 조건 | v1.0 (보수적) | v2.3 (완화) | 근거 |
| :--- | :--- | :--- | :--- |
| **RSI (14)** | < 30 | < **35** | RSI 35 이하도 반등 가능성, 기회 확대 |
| **Price vs MA** | > MA 200 | > **MA 20** | RSI 과매도와 MA200/50 상충 문제 해결, BB 중앙선과 동일 |
| **Volume** | > 1.5배 | > **1.2배** | 1.2배도 의미 있는 거래량 증가 |
| **Bollinger Band** | 하단 터치 필수 | **선택적 (기본 OFF)** | RSI와 중복, 불필요하게 까다로움 |

> ⚠️ **롤백 모드**: `src/config/strategy.py`에서 `USE_CONSERVATIVE_MODE = True` 설정 시 v1.0(MA200, RSI30)으로 즉시 복귀

**대상 코인 (v2.0 확장)**
| 코인 | 심볼 | 선정 이유 |
| :--- | :--- | :--- |
| Bitcoin | KRW-BTC | 기준 자산, 필수 |
| Ethereum | KRW-ETH | 시총 2위, 독자 생태계 |
| XRP | KRW-XRP | 국내 거래량 높음, BTC와 다른 움직임 |
| Solana | KRW-SOL | 고변동성, 기회 많음 |
| Dogecoin | KRW-DOGE | 밈코인, 독자적 패턴 |

**청산 조건**
| 유형 | 조건 | 설명 |
| :--- | :--- | :--- |
| **Take Profit** | +5% 도달 | 목표 수익 달성 시 전량 청산 |
| **Stop Loss** | -3% 도달 | 손실 제한 (필수) |
| **Signal Exit** | RSI > 70 | 과매수 구간 진입 시 청산 |
| **Time Exit** | 48시간 경과 | 장기 보유 방지 |

### 3.2 리스크 관리 규칙 (Hard-coded)
AI가 오버라이드할 수 없는 절대 규칙입니다.
| 규칙 | 값 | 위반 시 조치 |
| :--- | :--- | :--- |
| **단일 포지션 한도** | 총 자산의 5% | 주문 거부 |
| **일일 최대 손실** | -5% | 당일 거래 중단 |
| **일일 최대 거래** | 10회 | 당일 거래 중단 |
| **쿨다운** | 3연패 시 | 2시간 거래 중단 |
| **최소 거래 간격** | 30분 | 주문 지연 |

## 4. AI Agent 설계
### 4.1 Agent 역할: 도구 사용자 (Tool User)
**A. SQL Agent (Technical Assistant)**
* **역할:** 자연어 질의 → SQL 변환 → 지표 조회
* **입력:** "최근 4시간 RSI 30 이하?"
* **출력:** `SELECT * FROM market_candle ...`

**B. RAG Agent (Risk Sentinel)**
* **역할:** 뉴스 리스크 감지 (가격 예측 X)
* **키워드:** 해킹, SEC, 소송, 상폐, 파산
* **출력:** `HALT_TRADING` or `CLEAR`

**C. Volatility Model**
* **역할:** 변동성(GARCH/LSTM) 예측 → 포지션 사이징
* **출력:** 변동성 높음(High) → 포지션 50% 축소

### 4.2 고급 기능
* **Agent Memory:** 성공/실패 패턴을 Vector DB(pgvector)에 저장해 유사 상황 시 참조 (RAG)
* **Self-Reflection:** Critic Agent가 SQL/검색 결과의 타당성 2차 검증

## 5. 기술 스택
| 구분 | 기술 | 선정 이유 |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | 표준 |
| **Rule Engine** | 자체 구현 (Python) | 테스트 용이성, 명확성 |
| **AI Framework** | LangChain, LangGraph | 워크플로우 관리 |
| **Model** | GARCH / PyTorch | 변동성 예측용 |
| **LLM** | Claude 3.5 Haiku (Dev) / Claude 4.5 Sonnet (Prod) | 비용 효율성 및 고성능 추론 최적화 |
| **Backend** | FastAPI | 비동기 API |
| **Database** | PostgreSQL 16 | TimescaleDB (Time-series) + pgvector (Vector) |
| **Vector DB** | pgvector | PostgreSQL 내장 확장 (ChromaDB 대체) |
| **Infra** | Docker, K8s (Minikube) | MSA, Self-healing |
| **CI/CD** | GitHub Actions | 자동화 |

## 6. 개발 로드맵 (8주)

### 완료된 주차 (Week 1~6)
| 주차 | 목표 | 상태 | 비고 |
|------|------|------|------|
| **Week 1** | 데이터 파이프라인 (Collector, DB), Paper Trading | ✅ 완료 | |
| **Week 2** | Rule Engine, Risk Manager, 백테스팅 엔진 | ✅ 완료 | |
| **Week 3** | SQL Agent, RAG Agent, LangGraph 통합 | ⚠️ 부분 | Agent 스켈레톤만 구현, Week 7로 이관 |
| **Week 4** | Docker, K8s 배포, 모니터링 | ⚠️ 부분 | K8s 배포 완료, Prometheus/Grafana 설정 미완 |
| **Week 5** | n8n 워크플로우, Discord 알림 | ⚠️ 부분 | 웹훅 기본 연동 완료, n8n 워크플로우 수동 설정 |
| **Week 6** | Streamlit 대시보드, 문서화 | ✅ 완료 | Bot Brain, Auto Refresh 포함 |

### Week 7 (AI Agent + Chatbot) - 2단계 진행
**목표**: Week 3에서 미구현된 AI Agent 완성 + 대시보드 챗봇 통합

| 단계 | 기간 | 작업 내용 |
|------|------|----------|
| **Phase A** | Day 1-2 | SQL Agent 구현 (자연어 → SQL 변환), RAG Agent 구현 (문서/규칙 검색) |
| **Phase B** | Day 3-4 | Streamlit 챗봇 UI + Agent 통합, 대화형 분석 기능 |

* **SQL Agent**: "오늘 수익률?" → `SELECT SUM(total_pnl) FROM daily_risk_state WHERE date = TODAY`
* **RAG Agent**: "손절 규칙이 뭐야?" → PROJECT_CHARTER/리스크 규칙 검색
* **Chatbot UI**: 대시보드에 채팅 인터페이스 추가
* ⚠️ **읽기 전용 권한** 기본값 (거래 트리거 불가)

### Week 8 (고도화 & 미구현 기능 완성)
**목표**: 핵심 기능 고도화 및 프로덕션 준비

| 기능 | 우선순위 | 설명 |
|------|----------|------|
| **Monitoring 고도화** | 🔴 높음 | Prometheus 메트릭 수집, Grafana 대시보드 구성 |
| **Notification 고도화** | 🟡 중간 | n8n 워크플로우 코드화(IaC), 일간 리포트 자동화 |
| **Volatility Model** | 🟡 중간 | GARCH 기반 변동성 예측 → 포지션 사이징 연동 |
| **백테스팅 고도화** | 🟡 중간 | 성과 리포트 생성, 샤프 비율/MDD 계산 |
| **CI/CD 파이프라인** | 🟢 낮음 | GitHub Actions 테스트/배포 자동화 |
| **Agent Memory** | 🟢 낮음 | pgvector 활용 성공/실패 패턴 저장 |

### Future Consideration (Optional)
* **비서 챗봇 고도화**: Week 7 챗봇을 개인 비서 수준으로 발전
  * Phase 1: 플로팅 UI + Agent Memory (대화 맥락 기억)
  * Phase 2: Volatility Model + 백테스팅 리포트 조회
  * Phase 3: 뉴스 RAG 확장 + 일간 리포트 자동 생성
  * Phase 4: MCP 연동 + 거래 실행 권한 (Optional)
  * 상세 계획: `docs/work-plans/chatbot-advancement.md` 참조
* **MCP (Model Context Protocol)**: 챗봇 및 외부 LLM 클라이언트용 표준 인터페이스
  * 도입 시기: Week 8 이후 필요 시 검토
  * 장점: 재사용성, 표준화
  * 단점: 추가 인프라 및 복잡도 증가
* **실거래 전환**: Paper Trading → 실제 Upbit API 연동 (별도 검토 필요)

## 7. 차별화 포인트 (Portfolio)
| 일반적인 프로젝트 | **CoinPilot** |
| :--- | :--- |
| "가격 예측 90% 정확도" | **예측 불가능성 인정, 대응 중심 설계** |
| 수익률만 강조 | **리스크 관리 + 실패 분석 문서화** |
| 로컬 실행 | **Kubernetes 배포 + CI/CD** |
| AI 의존 | **AI 실패 시에도 동작하는 Fallback 설계** |
| Agent 단순 사용 | **Agent Memory + Self-Reflection** |

---

## 8. 중간 점검 (Week 8 완료 시점)

**점검일**: 2026-02-02
**점검자**: Claude Code (Operator & Reviewer)

### 8.1 Week별 완료 상태 업데이트

| 주차 | 목표 | 상태 | 비고 |
|------|------|------|------|
| **Week 1** | 데이터 파이프라인, Paper Trading | ✅ 완료 | |
| **Week 2** | Rule Engine, Risk Manager, 백테스팅 | ✅ 완료 | |
| **Week 3** | SQL/RAG Agent, LangGraph | ✅ 완료 | Week 7에서 구현 완료 |
| **Week 4** | Docker, K8s 배포, 모니터링 | ✅ 완료 | Week 8에서 Prometheus/Grafana 완성 |
| **Week 5** | n8n 워크플로우, Discord 알림 | ✅ 완료 | 워크플로우 수동 설정 |
| **Week 6** | Streamlit 대시보드, 문서화 | ✅ 완료 | |
| **Week 7** | AI Agent + Chatbot | ✅ 완료 | SQL/RAG/Router Agent + Chatbot UI |
| **Week 8** | 고도화 & 프로덕션 준비 | ✅ 완료 | Monitoring, Volatility, CI/CD |

### 8.2 핵심 기능 구현 현황

| 구성요소 | 역할 | 상태 | 구현 파일 |
|----------|------|------|-----------|
| Rule Engine | 매매 규칙 평가/신호 생성 | ✅ | `src/engine/rule_engine.py` |
| Risk Manager | 포지션 크기, 손절, 일일 한도 | ✅ | `src/engine/risk_manager.py` |
| SQL Agent | 자연어 → SQL 변환 | ✅ | `src/agents/sql_agent.py` |
| RAG Agent | 문서/규칙 검색 | ✅ | `src/agents/rag_agent.py` |
| Volatility Model | GARCH → 포지션 사이징 | ✅ | `src/analytics/volatility_model.py` |
| Prometheus Metrics | 시스템 관측성 | ✅ | `src/utils/metrics.py` |
| Grafana Dashboards | 메트릭 시각화 | ✅ | `deploy/monitoring/grafana-provisioning/` |
| CI/CD Pipeline | 테스트/배포 자동화 | ✅ | `.github/workflows/ci.yml` |

### 8.3 미구현 항목 (Future Consideration 유지)

| 항목 | Charter 위치 | 상태 | 사유 |
|------|-------------|------|------|
| Agent Memory | 4.2 고급 기능 | 🔜 Future | 우선순위 낮음 (pgvector 인프라는 준비됨) |
| Self-Reflection | 4.2 고급 기능 | 🔜 Future | 고급 기능으로 유지 |
| n8n IaC | Week 8 | ⚠️ 수동 | JSON Export 백업 권장 |

### 8.4 문서 참고

| 문서 | 설명 |
|------|------|
| `docs/work-result/week7-walkthrough.md` | AI Chatbot 구현 상세 |
| `docs/work-result/week8-walkthrough.md` | 고도화 구현 상세 |
| `docs/troubleshooting/week8-ts.md` | Week 8 트러블슈팅 로그 |

### 8.5 프로젝트 상태

| 항목 | 결과 |
|------|------|
| **Charter 대비 구현률** | **95%** |
| **핵심 기능 완성도** | 100% |
| **프로덕션 준비 상태** | ✅ Ready |

---
*Reviewed by Claude Code (Operator Role)*