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

**진입 조건 (Long)**
| 조건 | 기준 | 근거 |
| :--- | :--- | :--- |
| **RSI (14)** | < 30 | 과매도 구간 진입 |
| **Price vs MA(200)** | > MA 200 | 장기 상승 추세 확인 (필터) |
| **Volume** | > 20일 평균의 1.5배 | 의미 있는 매도 압력 확인 |
| **Bollinger Band** | 하단 밴드 터치 | 통계적 극단값 도달 |

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

## 6. 개발 로드맵 (6주)
* **Week 1 (Foundation):** 데이터 파이프라인 (Collector, DB), Paper Trading 로직 ✅
* **Week 2 (Core Logic):** Rule Engine, Risk Manager, 백테스팅 엔진 ✅
* **Week 3 (AI Integration):** SQL Agent, RAG Agent, LangGraph 통합 ✅
* **Week 4 (Infra):** Docker, K8s 배포, 모니터링 (Prometheus/Grafana) ✅
* **Week 5 (Notification):** n8n 워크플로우 자동화, Discord 알림 시스템
  * 거래 체결 알림 (Trade Executed)
  * 리스크 경고 알림 (Risk Alert)
  * 일간 리포트 발송 (Daily Report)
* **Week 6 (Polish):** 대시보드 고도화(Streamlit), 문서화(실패 분석), 최종 테스트

## 7. 차별화 포인트 (Portfolio)
| 일반적인 프로젝트 | **CoinPilot** |
| :--- | :--- |
| "가격 예측 90% 정확도" | **예측 불가능성 인정, 대응 중심 설계** |
| 수익률만 강조 | **리스크 관리 + 실패 분석 문서화** |
| 로컬 실행 | **Kubernetes 배포 + CI/CD** |
| AI 의존 | **AI 실패 시에도 동작하는 Fallback 설계** |
| Agent 단순 사용 | **Agent Memory + Self-Reflection** |