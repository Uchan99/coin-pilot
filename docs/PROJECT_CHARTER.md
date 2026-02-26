# CoinPilot Project Plan v3.3
**Compose 운영 + K8s 검증 기반 자율 가상화폐 매매 AI 에이전트**
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
  - Independent work: docs/work-plans/<NN>_<topic>_plan.md
  - Epic subtask: docs/work-plans/<EPIC>-<subNN>_<topic>_plan.md
- Plan 작성 후 사용자 승인(approval)을 반드시 받는다.
  - 승인 전 상태는 `Approval Pending`으로 관리한다.
  - 승인 전에는 구현/배포/마이그레이션을 진행하지 않는다.
  - 단, 긴급 장애 완화가 필요한 경우 사유/시각/사후 승인 기록을 plan/result에 남긴다.
- After implementation, write a work result:
  - Independent work: docs/work-result/<NN>_<topic>_result.md
  - Epic subtask: docs/work-result/<EPIC>-<subNN>_<topic>_result.md
  - Phase 단위 구현인 경우 Phase 2+는 동일 Result 파일 하단에 이어서 기록한다.

2) Troubleshooting is mandatory for incidents
- 모니터링/운영/버그/장애가 발생하면:
  - Independent: docs/troubleshooting/<NN>_<topic>.md
  - Epic subtask: docs/troubleshooting/<EPIC>-<subNN>_<topic>.md
  - 위 두 형식 중 하나로 별도 기록한다.
- 트러블슈팅 과정에서 계획 변경/코드 수정/검증 절차 변경이 생기면:
  - 해당 plan/result 문서도 함께 갱신하고, 필요 시 Charter도 갱신한다.

2.1) Numbering policy (required)
- 최상위 번호(`<NN>`)는 독립 작업 스트림에만 사용한다.
- 기존 에픽의 파생 작업은 `<EPIC>-<subNN>` 형식을 사용한다. (예: `17-01_...`, `17-02_...`)
- 에픽 파생 작업에 신규 최상위 번호를 부여하지 않는다.

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

### 3.2 리스크 관리 규칙 (Config-driven, Non-AI Override)
AI가 오버라이드할 수 없는 절대 규칙이며, 운영 설정(YAML)으로 관리합니다.
| 규칙 | 값 | 위반 시 조치 |
| :--- | :--- | :--- |
| **단일 포지션 한도** | 기준자산(reference equity)의 20% | 주문 거부 |
| **전체 노출 한도** | 기준자산의 100% | 신규 진입 거부 |
| **동시 보유 포지션 수** | 최대 5개 | 신규 진입 거부 |
| **동일 코인 중복 진입** | 비허용 | 신규 진입 거부 |
| **일일 최대 손실** | -3% | 당일 거래 중단 |
| **일일 최대 신규 진입(BUY)** | 6회 | 당일 신규 진입 중단 |
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
| **Infra** | Docker Compose (운영), K8s/Minikube (검증) | 비용 효율 운영 + K8s 확장성 준비 |
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
| 클라우드 마이그레이션 실행 산출물(Compose/Backup/Runbook) 구축 | ✅ | 2026-02-21 | `docs/work-result/18_cloud_migration_cost_optimized_result.md` |

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
| `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md` | 18번 클라우드 마이그레이션 계획(진행 중) |
| `docs/work-plans/18-13_oci_24h_monitoring_checklist_plan.md` | 18-13 OCI 24시간 집중 모니터링 점검표 정식화 계획 |
| `docs/work-plans/18-14_oci_24h_monitoring_script_automation_plan.md` | 18-14 OCI 24시간 모니터링 스크립트 자동화 계획 |
| `docs/work-plans/18-15_analyst_boundary_audit_mode_plan.md` | 18-15 Analyst Rule Boundary 정책을 강제차단에서 audit 기록 모드로 전환하는 계획 |
| `docs/work-plans/18-16_t12h_failed_keyword_false_positive_filter_plan.md` | 18-16 T+12h 배치 실패 키워드 오탐(`failed_feeds=0`) 제거 계획 |
| `docs/work-plans/20_oci_paid_tier_security_and_cost_guardrails_plan.md` | 20번 유료 전환 대비 보안/과금 가드레일 강화 계획 |
| `docs/work-plans/21-01_reference_equity_three_cap_execution_plan.md` | 21-01 기준자산 고정 + 3중 캡 주문 체계 전환 계획 |
| `docs/work-plans/19-01_plan_approval_gate_workflow_update_plan.md` | 19-01 Plan 승인 게이트 워크플로우 정책 개정 계획 |
| `docs/work-result/18-13_oci_24h_monitoring_checklist_result.md` | 18-13 OCI 24시간 집중 모니터링 점검표 반영 결과 |
| `docs/work-result/18-14_oci_24h_monitoring_script_automation_result.md` | 18-14 OCI 24시간 모니터링 스크립트 자동화 결과 |
| `docs/work-result/18-15_analyst_boundary_audit_mode_result.md` | 18-15 Analyst Boundary audit 모드 전환 구현 결과 |
| `docs/work-result/18-16_t12h_failed_keyword_false_positive_filter_result.md` | 18-16 T+12h 배치 실패 키워드 오탐 필터 보정 결과 |
| `docs/work-result/21-01_reference_equity_three_cap_execution_result.md` | 21-01 기준자산/3중 캡 구현 결과 |
| `docs/work-result/19-01_plan_approval_gate_workflow_update_result.md` | 19-01 승인 게이트 정책 반영 결과 |
| `docs/troubleshooting/13_strategy_regime_reliability_and_hotfixes.md` | 13번 트러블슈팅 기록 |
| `docs/troubleshooting/14_trade_count_split_hotfix.md` | 14번 트러블슈팅 기록 |
| `docs/troubleshooting/prometheus_grafana_monitoring_runbook.md` | Prometheus/Grafana 점검 및 활용 Runbook |
| `docs/runbooks/18_data_migration_runbook.md` | Minikube → OCI 데이터 이관 절차 Runbook |
| `docs/runbooks/18_oci_a1_flex_auto_retry_runbook.md` | OCI A1.Flex 용량 부족 자동 재시도 생성 Runbook |
| `docs/runbooks/18_oci_a1_flex_a_to_z_guide.md` | OCI CLI 인증부터 재부팅 재개까지 학생용 A~Z 가이드 |
| `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md` | WSL/OCI 로컬-클라우드 통합 운영 마스터 Runbook |
| `docs/troubleshooting/18_oci_a1_flex_capacity_and_throttle_retry.md` | OCI A1 재시도 중 429 스로틀링 종료 이슈 대응 기록 |
| `docs/troubleshooting/18-15_analyst_rule_boundary_false_rejects.md` | Analyst boundary 과잉 차단으로 인한 연속 REJECT 이슈 대응 기록 |
| `docs/troubleshooting/18-16_t12h_failed_keyword_false_positive.md` | 18-16 T+12h 실패 키워드 오탐으로 인한 모니터링 FAIL 이슈 대응 기록 |
| `docs/work-plans/18-01_compose_system_health_schema_alignment_plan.md` | 18-01 Compose System/스키마 정합성 복구 계획 |
| `docs/work-result/18-01_compose_system_health_schema_alignment_result.md` | 18-01 Compose System/데이터 복구 구현 결과 |
| `docs/troubleshooting/18-01_system_health_agent_decisions_and_data_sync.md` | 18-01 System 오류 및 데이터 공백 복구 트러블슈팅 |
| `docs/work-result/18_cloud_migration_cost_optimized_result.md` | 18번 실행 산출물 구현 결과 |
| `docs/work-result/20_oci_paid_tier_security_and_cost_guardrails_result.md` | 20번 보안/과금 가드레일 강화 구현 결과 |
| `docs/work-plans/20-01_project_wide_security_hardening_plan.md` | 20-01 전역 보안 하드닝(Compose/DB/CI) 하위 계획 |
| `docs/work-result/20-01_project_wide_security_hardening_result.md` | 20-01 전역 보안 하드닝 구현 결과 |
| `docs/runbooks/20-01_oci_runtime_security_verification_checklist.md` | 20-01 OCI VM 런타임 보안 검증 체크리스트 |

### 8.6 프로젝트 상태

| 항목 | 결과 |
|------|------|
| **Charter 대비 구현률** | **99%** (핵심 기능 100%, 고급 기능 Future) |
| **전략 버전** | v3.3 (레짐 기반 적응형 + 신뢰성/가드레일 강화) |
| **프로덕션 준비 상태** | ✅ Ready (운영 중) |
| **현재 초점** | 18번 클라우드 운영 안정화 후 21번 실거래 전환(100만 KRW) 준비 |

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
| 2026-02-20 | 문서 네이밍 정책에 에픽-서브태스크 체계(`<EPIC>-<subNN>`) 추가, 17번 파생 문서를 17-xx로 정리하는 운영 기준 반영 (관련: `docs/work-plans/19_epic_subtask_doc_structure_refactor_plan.md`) |
| 2026-02-21 | 18번 클라우드 마이그레이션 실행 단계 반영: OCI Compose 산출물, 백업 스크립트, 데이터 이관 runbook, Prometheus/Grafana 운영 체크리스트 추가 |
| 2026-02-22 | Chuncheon A1.Flex `Out of capacity` 대응을 위한 OCI CLI 자동 재시도 스크립트/Runbook 반영 (기존 VCN/Subnet 재사용, 로컬 private key 보관 절차 포함) |
| 2026-02-22 | OCI 초보자용 A~Z 가이드 및 재부팅 후 재개 래퍼 스크립트/환경파일 템플릿 반영 (`run_oci_retry_from_env.sh`, `oci_retry.env.example`) |
| 2026-02-22 | OCI A1 자동 재시도에 `429 TooManyRequests` 백오프 정책(지수+지터) 반영 및 트러블슈팅 문서 추가 |
| 2026-02-23 | 20번 스트림 착수: OCI 유료 전환 대비 보안/과금 가드레일 강화(대시보드 접근 가드, compose fail-fast, n8n webhook secret 검증, preflight 점검 스크립트) |
| 2026-02-23 | 18-01 하위 작업: Compose System Health 오류(`agent_decisions` 누락), n8n 헬스체크 오탐, K8s→Compose 데이터 공백 복구 절차 반영 |
| 2026-02-23 | 운영 문서 동기화: `daily-startup-guide`, `USER_MANUAL`, `Data_Flow`, `DEEP_LEARNING_GUIDE`를 Compose 기본 운영 기준으로 정합화 |
| 2026-02-23 | 20-01 하위 작업: 전역 보안 하드닝 완료(Compose 이미지/포트/필수 env 고정, Docker non-root 전환, DB 비밀번호 폴백 제거, CI Bandit/pip-audit 추가) |
| 2026-02-23 | 20-01 확장 반영: OCI VM 런타임 보안 점검 runbook 추가 + CI `pip-audit` advisory→blocking 상향 |
| 2026-02-25 | 18-11 하위 작업: n8n volume 백업 자동화 스크립트(`scripts/backup/n8n_backup.sh`) 및 cron 운영 절차 추가, WSL/OCI 볼륨 혼선 복구 경험 반영 |
| 2026-02-25 | 18-12 하위 작업: WSL/OCI 로컬-클라우드 통합 운영 마스터 runbook 작성, 포트/볼륨/백업/알람/복구 기준을 단일 문서로 통합 |
| 2026-02-26 | 19-01 정책 반영: 문서 워크플로우에 `Plan 작성 → 사용자 승인 → 구현` 승인 게이트 추가 (긴급 대응은 사후 승인 기록 의무) |
| 2026-02-26 | 21-01 전략 반영: 기준자산(reference equity) 기반 3중 캡 주문 정책, 리스크 한도(20% 주문/100% 총노출/5포지션/일일손실 -3%/일일 BUY 6회)로 100만원 운용 기준 정렬 |
| 2026-02-26 | 18-13 운영 문서 반영: OCI 재배포/설정 변경 직후 적용하는 24시간 집중 모니터링 점검표(T+0m/1h/6h/12h/24h) 추가 |
| 2026-02-26 | 18-14 운영 자동화 반영: 24시간 점검 phase(`t0/t1h/t6h/t12h/t24h`)를 자동 수행하는 스크립트(`scripts/ops/check_24h_monitoring.sh`) 추가 |
| 2026-02-26 | 18-15 AI 정책 조정: Analyst Rule Boundary 경로를 재시도+강제REJECT에서 audit 기록 모드로 전환하고, 프롬프트 제약을 강화하여 과잉 차단/credit 낭비를 완화 |
| 2026-02-26 | 18-16 운영 보정 반영: T+12h 실패 탐지 정규식을 보정해 `failed_feeds=0` 정상 로그 오탐을 제거하고 실제 실패 문맥(`...failed:`/`...job failed:`)만 감지하도록 조정 |

---
*최종 업데이트: 2026-02-26 (18-13/18-14/18-15/18-16/19-01/21-01 반영: 24h 점검표 + 자동화 스크립트 + Boundary audit 모드 + T+12h 오탐 제거 + 승인 게이트 + 기준자산 3중 캡 주문 정책) by Codex (GPT-5)*
