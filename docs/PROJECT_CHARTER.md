# CoinPilot Project Plan v3.3
**Kubernetes 기반 자율 가상화폐 매매 AI 에이전트**
*(Rule-Based Core + AI-Assisted Decision System)*

## Operating Rules (Documentation Workflow)

0) Source of Truth
- 본 문서는 프로젝트 운영의 Source of Truth이다.
- 작업 수행/모니터링 과정에서 “정의/정책/운영 규칙/범위” 변경이 필요해지면:
  - 반드시 본 문서를 수정하고
  - Changelog에 날짜/사유/영향/관련 문서(Plan/Result/Troubleshooting)를 기록한다.

1) Work docs are mandatory (Plan → Code → Result)
- Start every task by reading this charter.
- Create a work plan before coding:
  - docs/work-plans/<NN>_<topic>_plan.md
- After implementation, write a work result:
  - docs/work-result/<NN>_<topic>_result.md
  - Phase 단위 구현인 경우 Phase 2+는 동일 Result 파일 하단에 이어서 기록한다.

2) Troubleshooting is mandatory for incidents
- 모니터링/운영/버그/장애가 발생하면:
  - docs/troubleshooting/<NN>_<topic>.md 로 별도 기록한다.
- 트러블슈팅 과정에서 계획 변경/코드 수정/검증 절차 변경이 생기면:
  - 해당 plan/result 문서도 함께 갱신하고, 필요 시 Charter도 갱신한다.

3) Traceability (문서 간 연결은 필수)
- Result는 반드시 해당 Plan을 링크한다.
- Troubleshooting은 관련 Plan/Result를 링크한다.
- Plan이 사고/이슈에서 시작된 경우 Troubleshooting을 링크한다.

4) Architecture decision must be explicit
- Plan/Result에 “왜 이 아키텍처인가 + 대안(가능하면 3개) + 이점/트레이드오프/완화”를 명시한다.
- Result에는 실제 관측된 효과(좋았던 점/아쉬웠던 점/계획 대비 변경점)를 요약한다.

5) Korean comments for non-trivial code are required
- 비단순 로직(전략/수식/캐시/동시성/예외 처리/리스크 제어 등)은
  - 한국어 주석으로 intent/why, invariants, edge cases, failure modes를 충분히 설명한다.

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

### 2.2 의사결정 흐름 (v3.3 업데이트)
**"AI가 실패해도 시스템은 동작한다"**가 핵심 원칙입니다.

**매매 실행 Flow (현재 운영 기준):**
```
[시장 데이터] → [레짐 감지 (1시간 주기)] → [Rule Engine: 레짐별 조건 충족?]
  → [Risk Manager: 진입 가능?] → [AI Pre-filter/Guardrails]
  → [AI Analyst: 신호 신뢰성 검증] → [AI Guardian: 리스크 검토]
  → [Executor: 주문 실행]
```

* **AI 검증 2단계:**
    * **Market Analyst:** Rule Engine 통과 신호의 기술적 신뢰성 판단 (CONFIRM/REJECT, confidence < 60 시 강제 REJECT)
    * **Risk Guardian:** 거시적 리스크 및 심리 상태 검토 (SAFE/WARNING)
    * AI Timeout(40초) 또는 에러 시 → 보수적으로 REJECT (Fallback 설계)
* **AI 호출 보호 장치:**
    * 심볼별 REJECT 쿨다운(5/10/15분)
    * 시간/일 호출 상한
    * 크레딧 부족/연속 에러 시 글로벌 블록
* **보조 Agent:**
    * **SQL Agent:** 자연어 질의 → SQL 변환 → 지표 조회
    * **RAG Agent:** 문서/규칙 검색, 리스크 이벤트 감지
    * **Volatility Model:** GARCH 기반 변동성 예측 → 포지션 사이징

## 3. 트레이딩 전략
### 3.1 채택 전략: Adaptive Mean Reversion (v3.3)
마켓 레짐(BULL/SIDEWAYS/BEAR)을 감지하고 각 상황에 맞는 진입/청산 조건을 동적으로 적용합니다.
과매도 구간 반등을 노리되, Rule Engine은 느슨한 필터로 후보를 생성하고 AI Agent가 엄격하게 2차 판단합니다.

**레짐 감지 (1시간 주기)**
| 레짐 | 조건 | 설명 |
| :--- | :--- | :--- |
| **BULL** | MA50 > MA200 + 2% | 상승장 (골든크로스) |
| **SIDEWAYS** | \|MA50 - MA200\| ≤ 2% | 횡보장 |
| **BEAR** | MA50 < MA200 - 2% | 하락장 (데드크로스) |
| **UNKNOWN** | 데이터 부족 | 신규 거래 보류 |

**진입 조건 (Long) - v3.3 (레짐 기반 적응형)**
| 조건 | BULL | SIDEWAYS | BEAR |
| :--- | :--- | :--- | :--- |
| **RSI (14)** | < 50 | < 48 | < 42 |
| **RSI (7) Trigger** | < 42 | < 40 | < 30 |
| **RSI (7) Recover** | ≥ 42 | ≥ 42 | ≥ 30 |
| **RSI (7) 반등폭** | ≥ 2pt | ≥ 3pt | ≥ 2pt |
| **MA 조건** | MA20 돌파 | MA20 근접 (98.5%) | MA20 근접(97%) or 돌파 |
| **거래량 상한** | ≥ 1.0배 | - | - |
| **거래량 하한** | - | ≥ 0.4배 | ≥ 0.2배 |
| **BB 하단 방어** | - | 가격 > BB 하단 | 가격 > BB 하단 |
| **BB 터치 회복** | - | 필수 (연속 유지 조건 포함) | - |
| **거래량 급증 체크** | - | - | 2배 이상 시 보류 |
| **포지션 비중** | 100% | 80% | 50% |

> 설정 파일: `config/strategy_v3.yaml`, 기본값: `src/config/strategy.py`
> 롤백: YAML 값을 이전으로 복원 후 재배포

**대상 코인**
| 코인 | 심볼 | 선정 이유 |
| :--- | :--- | :--- |
| Bitcoin | KRW-BTC | 기준 자산, 필수 |
| Ethereum | KRW-ETH | 시총 2위, 독자 생태계 |
| XRP | KRW-XRP | 국내 거래량 높음, BTC와 다른 움직임 |
| Solana | KRW-SOL | 고변동성, 기회 많음 |
| Dogecoin | KRW-DOGE | 밈코인, 독자적 패턴 |

**청산 조건 (레짐별 차등)**
| 유형 | BULL | SIDEWAYS | BEAR |
| :--- | :--- | :--- | :--- |
| **Take Profit** | +5% | +3% | +3% |
| **Stop Loss** | -3% | -4% | -5% |
| **Trailing Stop** | 1% 활성, 3% 하락 시 | 1% 활성, 2.5% 하락 시 | 1% 활성, 2% 하락 시 |
| **RSI 과매수** | RSI > 75 (수익 1%+) | RSI > 70 (수익 1%+) | RSI > 70 (수익 0.5%+) |
| **Time Limit** | 72시간 | 48시간 | 24시간 |

> 레짐 변경 시 Stop Loss는 타이트한(작은) 값 유지 정책 적용

### 3.2 리스크 관리 규칙 (Hard-coded)
AI가 오버라이드할 수 없는 절대 규칙입니다.
| 규칙 | 값 | 위반 시 조치 |
| :--- | :--- | :--- |
| **단일 포지션 한도** | 총 자산의 5% | 주문 거부 |
| **일일 최대 손실** | -5% | 당일 거래 중단 |
| **일일 최대 신규 진입(BUY)** | 10회 | 당일 신규 진입 중단 |
| **쿨다운** | 3연패 시 | 2시간 거래 중단 |
| **최소 거래 간격** | 30분 | 주문 지연 |

## 4. AI Agent 설계
### 4.1 매매 판단 Agent (LangGraph 워크플로우)

**A. Market Analyst (매매 판단)**
* **역할:** Rule Engine이 포착한 진입 신호의 기술적 신뢰성 검증
* **입력:** 심볼, 지표(RSI, MA, BB, 거래량), 레짐 정보
* **출력:** CONFIRM/REJECT + confidence(0-100) + 추론 근거
* **정책:** confidence < 60 → 강제 REJECT
* **구현:** `src/agents/analyst.py`

**B. Risk Guardian (리스크 검토)**
* **역할:** 거시적 리스크 및 투자자 심리 상태 검토
* **입력:** 심볼, 지표, Analyst 결과
* **출력:** SAFE/WARNING
* **구현:** `src/agents/guardian.py`

**워크플로우:** `Analyst → (CONFIRM인 경우만) → Guardian → 최종 결정`
**Timeout:** 40초 (초과 시 보수적으로 REJECT)

### 4.2 보조 Agent (챗봇/조회용)

**A. SQL Agent (Technical Assistant)**
* **역할:** 자연어 질의 → SQL 변환 → 지표 조회
* **구현:** `src/agents/sql_agent.py`

**B. RAG Agent (문서 검색)**
* **역할:** PROJECT_CHARTER, 리스크 규칙 등 문서 검색
* **구현:** `src/agents/rag_agent.py`

**C. Volatility Model**
* **역할:** GARCH 기반 변동성 예측 → 포지션 사이징
* **구현:** `src/analytics/volatility_model.py`

### 4.3 고급 기능 (Future)
* **Agent Memory:** 성공/실패 패턴을 Vector DB(pgvector)에 저장해 유사 상황 시 참조 (인프라 준비 완료, 구현 대기)
* **EvalOps:** AI 판단의 사후 평가 체계 (규칙 기반 → 추후 LLM Judge 확장)
* **Self-Reflection:** Critic Agent가 Analyst 결정의 규칙 준수 여부 2차 검증 (검토 중)
* 관련 계획: `docs/work-plans/15_post_exit_analysis_enhancement_plan.md` 및 후속 AI 개선 계획 문서 참조

## 5. 기술 스택
| 구분 | 기술 | 선정 이유 |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | 표준 |
| **Rule Engine** | 자체 구현 (Python) | 테스트 용이성, 명확성 |
| **AI Framework** | LangChain, LangGraph | 워크플로우 관리 |
| **Model** | GARCH / PyTorch | 변동성 예측용 |
| **LLM** | Claude Haiku 4.5 (Dev) / Claude Sonnet 4.5 (Prod) | 비용 효율성 및 고성능 추론 최적화 |
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
  * 상세 계획: `docs/work-plans/9_chatbot-advancement.md` 참조
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

## 8. 프로젝트 점검

### 8.1 Week별 완료 상태

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

### 8.2 Week 8 이후 진행 사항 (운영 최적화)

| 작업 | 상태 | 날짜 | 구현 보고서 |
|------|:----:|------|-----------|
| v3.0 적응형 전략 (레짐 기반) | ✅ | 2026-02-06 | `docs/work-result/10_coinpilot_v3_implementation_report.md` |
| v3.1 전략 정교화 (Falling Knife 방지, 거래량 필터) | ✅ | 2026-02-07 | `docs/work-result/11_notification_and_timezone_improvements.md` |
| 스케줄러 안정화, AI Reject 알림, KST 변환 | ✅ | 2026-02-07 | 위 문서 참조 |
| Redis TTL 최적화 (레짐 데이터 소실 방지) | ✅ | 2026-02-08 | git commit 참조 |
| Daily Report 스케줄러 복구 | ✅ | 2026-02-11 | `docs/work-result/12_daily_report_fix.md` |
| v3.1 파라미터 튜닝 (RSI/거래량 완화) | ✅ | 2026-02-12 | `docs/work-result/12_strategy_parameter_report.md` |
| `detect_regime()` threshold 버그 수정 | ✅ | 2026-02-12 | 위 문서 참조 |
| 백테스트 코드 v3.1 조건 동기화 | ✅ | 2026-02-12 | 위 문서 참조 |
| 전략 레짐 신뢰성 개선 + 운영 핫픽스(Phase 1~3A) | ✅ | 2026-02-18~19 | `docs/work-result/13_strategy_regime_phase1_implementation_result.md` |
| Trade Count 분리 핫픽스 구현 완료 | ✅ | 2026-02-19 | `docs/work-result/14_trade_count_split_hotfix_result.md` |
| 매도 후 사후 분석 강화(Phase 1~3) 구현 완료 | ✅ | 2026-02-19 | `docs/work-result/15_post_exit_analysis_phase1_implementation_result.md` |

### 8.3 핵심 기능 구현 현황

| 구성요소 | 역할 | 상태 | 구현 파일 |
|----------|------|------|-----------|
| Adaptive Strategy | 레짐 기반 적응형 진입/청산 | ✅ | `src/engine/strategy.py` |
| Regime Detection | MA50/MA200 기반 레짐 감지 | ✅ | `src/common/indicators.py` |
| Trailing Stop | HWM 기반 동적 손절 | ✅ | `src/engine/strategy.py` |
| Market Analyst | AI 진입 신호 검증 (LangGraph) | ✅ | `src/agents/analyst.py` |
| Risk Guardian | AI 리스크 검토 (LangGraph) | ✅ | `src/agents/guardian.py` |
| Agent Runner | AI 워크플로우 실행/DB 로깅 | ✅ | `src/agents/runner.py` |
| Risk Manager | 포지션 크기, 손절, 일일 한도 | ✅ | `src/engine/risk_manager.py` |
| SQL Agent | 자연어 → SQL 변환 | ✅ | `src/agents/sql_agent.py` |
| RAG Agent | 문서/규칙 검색 | ✅ | `src/agents/rag_agent.py` |
| Daily Reporter | 일간 리포트 LLM 생성 → Discord | ✅ | `src/agents/daily_reporter.py` |
| Post-Exit Tracker | 매도 후 1h/4h/12h/24h 가격 추적 | ✅ | `src/analytics/post_exit_tracker.py` |
| Exit Performance Analyzer | 주간 집계/튜닝 제안 생성 | ✅ | `src/analytics/exit_performance.py` |
| Exit Analysis Dashboard | 매도 성과 시각화/제안 확인 | ✅ | `src/dashboard/pages/07_exit_analysis.py` |
| Volatility Model | GARCH → 포지션 사이징 | ✅ | `src/analytics/volatility_model.py` |
| Prometheus Metrics | 시스템 관측성 | ✅ | `src/utils/metrics.py` |
| Grafana Dashboards | 메트릭 시각화 | ✅ | `deploy/monitoring/grafana-provisioning/` |
| CI/CD Pipeline | 테스트/배포 자동화 | ✅ | `.github/workflows/ci.yml` |
| Backtest v3 | 레짐 기반 전략 백테스트 | ✅ | `scripts/backtest_v3.py` |

### 8.4 미구현 항목 (Future Consideration)

| 항목 | Charter 위치 | 상태 | 사유 |
|------|-------------|------|------|
| Agent Memory (Episodic) | 4.3 고급 기능 | 🔜 Future | pgvector 인프라 준비됨, 거래 데이터 축적 후 구현 |
| EvalOps (AI 판단 평가) | 4.3 고급 기능 | 🔜 Future | 거래 데이터 축적 필요 |
| Self-Reflection (Critic) | 4.3 고급 기능 | 🔜 Future | 기존 Rule Engine/Risk Manager와 중복 검토 필요 |
| MCP | Future Consideration | 🔜 보류 | 월 50건+ 거래, 외부 연동 필요성 발생 시 재검토 |
| n8n IaC | Week 8 | ⚠️ 수동 | JSON Export 백업 권장 |
| Phase 2 레짐 MA 조정 | 전략 튜닝 | 📋 계획 | Phase 1 모니터링 후 Option B (MA 30/100) 검토 |

### 8.5 문서 참고

| 문서 | 설명 |
|------|------|
| `docs/work-result/week7-walkthrough.md` | AI Chatbot 구현 상세 |
| `docs/work-result/week8-walkthrough.md` | 고도화 구현 상세 |
| `docs/work-result/week8-strategy-expansion.md` | Week 8 전략 확장 |
| `docs/work-result/10_coinpilot_v3_implementation_report.md` | v3.0 적응형 전략 구현 |
| `docs/work-result/11_notification_and_timezone_improvements.md` | v3.1 정교화 및 알림 개선 |
| `docs/work-result/12_daily_report_fix.md` | Daily Report 복구 |
| `docs/work-result/12_strategy_parameter_report.md` | 파라미터 튜닝 구현 |
| `docs/work-result/14_trade_count_split_hotfix_result.md` | 14번 Trade Count 분리 핫픽스 구현 결과 |
| `docs/work-result/15_post_exit_analysis_phase1_implementation_result.md` | 15번 Post-exit 분석 Phase 1~3 구현 결과 |
| `docs/work-plans/12_strategy_parameter_tuning.md` | 파라미터 튜닝 계획 (확정) |
| `docs/work-plans/13_strategy_regime_reliability_plan.md` | 전략 레짐 신뢰성 개선/핫픽스 계획 |
| `docs/work-plans/14_post_exit_trade_count_split_hotfix.md` | Trade Count 분리 핫픽스 계획 |
| `docs/work-plans/15_post_exit_analysis_enhancement_plan.md` | 매도 후 사후 분석 강화 계획 |
| `docs/troubleshooting/13_strategy_regime_reliability_and_hotfixes.md` | 13번 트러블슈팅 기록 |
| `docs/troubleshooting/14_trade_count_split_hotfix.md` | 14번 트러블슈팅 기록 |
| `docs/troubleshooting/prometheus_grafana_monitoring_runbook.md` | Prometheus/Grafana 점검 및 활용 Runbook |

### 8.6 프로젝트 상태

| 항목 | 결과 |
|------|------|
| **Charter 대비 구현률** | **99%** (핵심 기능 100%, 고급 기능 Future) |
| **전략 버전** | v3.3 (레짐 기반 적응형 + 신뢰성/가드레일 강화) |
| **프로덕션 준비 상태** | ✅ Ready (운영 중) |
| **현재 초점** | 16번 Overview 가독성 개선 + 17/18 계획(챗봇 고도화/클라우드 마이그레이션) 준비 |

### 8.7 적용 완료 (14번 핫픽스 반영)

`14_post_exit_trade_count_split_hotfix`를 반영하여, `daily_risk_state`의 거래 카운트 정의를 아래처럼 표준화했다.

| 필드 | 의미 | 증가 시점 | 주 사용처 |
|------|------|----------|----------|
| `buy_count` | 당일 신규 진입 체결 수 | BUY 성공 시 | 일일 거래 제한(`MAX_DAILY_TRADES`) |
| `sell_count` | 당일 청산 체결 수 | SELL 성공 시 | 청산 추적/운영 모니터링 |
| `trade_count` | 총 체결 수(`buy_count + sell_count`) | BUY/SELL 성공 시 | 하위 호환, 대시보드 보조 지표 |

적용 원칙:
1. 리스크 차단 기준은 `buy_count`를 사용한다.
2. 대시보드는 `BUY/SELL/Total`을 분리 노출한다.
3. 향후 리포트/분석은 목적에 맞는 카운트 필드를 명시적으로 사용한다.

### 8.8 Charter 운영 원칙

앞으로 개발 시 아래 원칙으로 `PROJECT_CHARTER.md`를 함께 유지한다.

1. 정책/임계값 변경(예: timeout, confidence, 리스크 한도)은 구현과 같은 날 Charter에 반영한다.
2. 아키텍처 흐름 변경(예: RiskManager ↔ AI 순서)은 Flow 다이어그램/설명 동시 수정한다.
3. 신규 work-plan이 실행 단계로 진입하면 "현재 초점"과 "문서 참고" 섹션에 링크를 추가한다.
4. 트러블슈팅으로 시작된 변경은 관련 troubleshooting 문서를 Charter의 참조 목록에 연결한다.

### 8.9 변경 이력 (요약)

| 날짜 | 변경 요약 |
|------|----------|
| 2026-02-19 | 14번 Trade Count 분리 핫픽스 및 15번 Post-exit 분석 강화(Phase 1~3, 주간 리포트/Exit 분석 대시보드 포함) 완료 상태 반영 |

---
*최종 업데이트: 2026-02-19 (15번 완료 반영) by Codex (GPT-5)*
