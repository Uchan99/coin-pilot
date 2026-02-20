# 17. AI 트레이딩 비서(챗봇) 고도화 계획

**작성일**: 2026-02-19  
**상태**: Completed (Phase 0~5, 뉴스는 RSS-Only 경로 반영)  
**우선순위**: P1 (운영 생산성/의사결정 보조 강화)

---

## 1. 배경 및 문제 정의

현재 챗봇은 `SQL 조회 / 문서 검색 / 일반 대화` 중심의 기본 라우팅 구조이며, 다음 한계가 있다.

1. UI 한계: 챗봇이 별도 페이지(`06_chatbot.py`)에 있어 대시보드 확인 중 병행 사용이 불편함
2. 기능 한계: 단순 조회형 응답 비중이 높아, "시장 해석"/"전략 장단점 분석" 같은 고차원 질의 대응이 약함
3. 데이터 결합 부족: 문서 RAG, 거래 성과, 리스크 상태, 뉴스 컨텍스트를 통합 분석하는 오케스트레이션 부재
4. 비용/안정성 리스크: 고도화 시 LLM 호출량 급증 가능성

목표는 챗봇을 **조회 도구**에서 **AI 트레이딩 비서**로 전환하는 것이다.

---

## 2. 목표

### 2.1 기능 목표

1. 모든 대시보드 페이지에서 우하단 Floating Assistant로 대화 가능
2. 아래 고차원 질의를 안정적으로 처리
   - "현재 비트코인 시장 어떻게 봐?"
   - "최근 매매기록 기준으로 전략 장단점 분석해줘"
   - "지금 레짐에서 주의할 리스크가 뭐야?"
3. 내부 데이터 + 문서 RAG + 뉴스 요약을 결합한 분석형 답변 제공
4. 비용/호출량 가드레일 내에서 운영

### 2.2 정량 목표

1. 주요 질의군 응답 성공률 95% 이상
2. 평균 응답 지연 P95 8초 이하
3. 1회 대화당 평균 LLM 호출 수 2회 이하
4. 환각/근거 부족 답변 비율 10% 이하 (내부 점검 기준)

---

## 2.3 기술 스택 선택 이유 및 대안 비교

### 선택 기술
- Streamlit 기반 Floating Assistant UI
- LangGraph Router 확장(의도 분류 + 도구 조합)
- PostgreSQL/기존 Analytics + PGVector RAG 재사용
- 뉴스는 실시간 호출 대신 배치 수집/요약/점수화

### 선택 이유
1. 기존 코드베이스와 정합성이 높아 점진적 고도화가 가능
2. 멀티 에이전트/멀티 툴 조합을 LangGraph에서 명시적으로 제어 가능
3. 실시간 뉴스 호출을 피하고 배치형 구조를 사용해 비용/안정성 리스크를 낮춤

### 대안 비교
1. 단일 LLM 프롬프트로 모든 질의 처리
- 장점: 구현 단순
- 단점: 응답 일관성/근거성/비용 통제가 어려움

2. 실시간 웹 검색 기반 뉴스 QA
- 장점: 최신성 높음
- 단점: 호출비용/지연/노이즈 증가, 운영 예측 가능성 저하

3. 별도 프론트 SPA 구축 후 챗 UI 분리
- 장점: UI 자유도 높음
- 단점: 현재 Streamlit 기반 운영과 이원화되어 개발 부담 증가

---

## 3. 아키텍처 방향

### 3.1 UI 레이어

- 기존 `06_chatbot.py`는 유지(독립 페이지)
- 공통 Helper(`src/dashboard/components/floating_chat.py`)를 만들어 각 페이지 하단에 삽입
- 우하단 Floating 버튼 + 패널(열기/닫기) 구조
- 대화 이력은 `st.session_state` 기반 공통 키로 페이지 간 유지

### 3.2 Assistant Orchestrator 레이어

기존 단일 분기 Router를 "의도 분류 + 도구 조합" 형태로 확장.

핵심 도구:
1. `portfolio_tool`: 포지션/잔고/PnL/거래이력 요약
2. `strategy_review_tool`: 최근 N건 거래 성과/exit_reason/레짐별 통계 분석
3. `market_outlook_tool`: 시장 지표 + 레짐 + (선택) 뉴스 리스크 점수 결합
4. `knowledge_tool`: 문서 RAG 조회(룰/아키텍처/정책)

### 3.3 데이터 레이어

- DB 실시간 조회: 포지션/거래이력/리스크 상태
- Analytics 집계: 15번 결과(post-exit 포함) 연계
- 문서 RAG: 기존 PGVector 활용
- 뉴스: 실시간 호출이 아니라 배치 수집/요약/점수화 후 조회형 사용

### 3.4 공통 LLM/런타임/보안 원칙

1. LLM 경로 통합: 챗봇 LLM 초기화 경로를 `factory.py` 기반으로 통합하고, 모델 선택은 `LLM_MODE` 정책과 정렬  
2. Streamlit 비동기 실행 안정화: `asyncio.run()` 직접 호출 대신 공용 실행 헬퍼(동기 래퍼) 사용  
3. SQL 안전성 강화: 프롬프트 의존이 아닌 read-only 커넥션 + DML 정규식 필터를 이중 적용

---

## 4. 구현 범위

## Phase 0. 선행 정합성/보안 정비 (P0, Release Step A-0)

### 4.0 목표
- 본격 기능 개발 전, 모델 경로/이벤트 루프/SQL 보안의 구조적 리스크 제거

### 4.0.1 LLM 모델 경로 통합
- 챗봇 라우터/도구 LLM 생성을 `src/agents/factory.py` 경유로 통합
- `src/agents/config.py`의 구형 기본값(`claude-3-haiku-*`) 의존 제거
- 기본 모델은 `LLM_MODE=dev` 기준 Haiku 4.5 계열, 고난도 요청 시 승격 정책은 Phase 5에서 적용

### 4.0.2 Streamlit 비동기 실행 전략 확정
- `06_chatbot.py` 및 Floating Chat에서 `asyncio.run()` 제거
- 공용 동기 래퍼(예: `run_async_safely`)를 두고 루프 상태에 따라 안전 실행
- 필요 시 `nest_asyncio`는 fallback으로만 사용(기본 경로 아님)

### 4.0.3 SQL Agent 보안 강화
- SQL DB 연결을 read-only 트랜잭션 모드로 고정(가능한 범위에서 DB 권한/세션 설정 병행)
- 쿼리 실행 직전 DML/DDL 차단 정규식 필터 적용 (`INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE` 등)
- 위반 시 실행하지 않고 안전 오류 응답 반환

### 4.0 완료 기준
- 챗봇이 Bot과 동일 계열 모델 정책으로 동작
- 이벤트 루프 충돌 오류 재현 테스트 0건
- DML 문 입력 시 DB 변경 없이 차단 로그만 기록

---

## Phase 1. Floating Chat UX (P1, Release Step A)

### 4.1 목표
- 챗봇을 우하단에서 전 페이지 공통으로 사용 가능하게 전환

### 4.2 변경 내용
- `src/dashboard/components/floating_chat.py` 신규
  - Floating 버튼
  - 열림 상태 패널
  - 최근 메시지 렌더
  - 입력창/전송
- `src/dashboard/pages/*.py` 공통 삽입
- `06_chatbot.py`는 상세 모드(풀 페이지)로 유지

### 4.3 완료 기준
- Overview/Risk/History/System 등 임의 페이지에서 이동 후에도 대화 컨텍스트 유지
- 패널 open/close 정상 동작

---

## Phase 2. 분석형 질의 라우팅 확장 (P0, Release Step B)

### 4.4 목표
- "단순 조회"를 넘어 "분석/평가/제안" 질의를 처리

### 4.5 의도(Intent) 확장
기존:
- `db_query`, `doc_search`, `general_chat`

확장:
- `market_outlook`
- `strategy_review`
- `risk_diagnosis`
- `action_recommendation` (실행 권고는 제안만, 자동 매매 없음)

### 4.6 도구 실행 방식
- 의도별로 고정된 Tool Chain 실행
- `process_chat()`의 그래프 인스턴스는 싱글톤 캐시로 재사용(매 요청 compile 금지)
- 예시:
  - `market_outlook`: 시장지표 조회 -> 레짐/모멘텀 요약 -> (옵션)뉴스 리스크 결합 -> 답변
  - `strategy_review`: 최근 거래 집계 -> 승률/MDD/exit_reason 분석 -> 강점/약점/개선안 제시

### 4.7 완료 기준
- 대표 질문 10개 시나리오에서 의도 분류/응답 품질 기준 충족
- 그래프 compile 호출이 프로세스 초기 1회(또는 캐시 miss 시)로 제한됨

---

## Phase 3. 전략 리뷰/코칭 기능 (P0, Release Step C)

### 4.8 목표
- 사용자 질문에 대해 거래내역 기반 진단 리포트 생성

### 4.9 구현 내용
- `src/agents/tools/strategy_review_tool.py` 신규
  - 최근 N일 거래 성과 요약
  - 레짐별 성과 분해(BULL/SIDEWAYS/BEAR)
  - exit_reason별 성과
  - 연속 손실/과매수 진입 빈도 등 리스크 패턴
- PnL 계산 경로 명시
  - 기본안: BUY/SELL 매칭으로 `realized_pnl` 계산(Python 후처리)
  - 확장안: 성능/일관성 필요 시 `trading_history.realized_pnl` 컬럼 추가를 별도 마이그레이션으로 검토
- "장점/약점/즉시 개선 3가지" 포맷으로 응답 템플릿 표준화

### 4.10 완료 기준
- "내 전략 장단점 알려줘" 질의에서 근거 숫자 포함 답변 반환

---

## Phase 4A. 뉴스 RAG 설계 단계 (P1, Release Step D-Design)

### 4.11 목표
- 구현 전 데이터 소스/스키마/비용을 확정

### 4.12 설계 산출물
- 소스 선정: CryptoPanic/CoinGecko/RSS 등 후보 비교 후 1~2개 확정
- 저장 스키마: `news_articles`, `news_summaries`, `news_risk_scores` 초안
- 임베딩 전략: OpenAI 임베딩 유지 vs 로컬 임베딩(`sentence-transformers`) 비용 비교
- 비용 시뮬레이션: 일일 수집 건수/요약 호출/임베딩 비용 추정

### 4.13 완료 기준
- ADR(Architecture Decision Record) 1건 + 예상 월 비용 범위 + 구현 Go/No-Go 결정

---

## Phase 4B. 뉴스 RAG 구현 단계 (P1, Release Step D)

### 4.14 목표
- 시장 해석 질의에서 외부 이벤트(규제/거시/거래소 이슈) 반영

### 4.15 설계 원칙
- 실시간 뉴스 검색을 매 질의마다 호출하지 않음
- 배치 수집 -> 임베딩/요약 -> 위험점수화 -> 조회형으로 사용

### 4.16 구현 내용
- `news_ingest_job` (주기 수집)
- `news_summary_job` (심볼/테마별 요약)
- `news_risk_score` 저장
- 챗봇은 최신 점수/요약만 조회

### 4.17 완료 기준
- "오늘 BTC 리스크 이슈" 질의에 뉴스 근거 기반 요약 제공
- 호출량 급증 없이 동작

---

## Phase 5. 비용/안전 가드레일 (P0, Release Step B~D 공통)

### 4.18 모델 계층화
- 기본: Haiku
- 승격: 고난도 전략 리뷰 요청 시 Sonnet (조건부)

### 4.19 호출 통제
- 사용자 세션당 요청 쿨다운
- 동일 질의 캐시
- 길이 제한/토큰 예산
- 오류 시 보수적 fallback
- 임베딩 비용 통제: 뉴스 대량 임베딩 구간은 로컬 임베딩 전환 옵션 유지

### 4.20 답변 안전장치
- 투자 권유 고정 문구 및 한계 고지
- "예측 단정" 금지, 시나리오 기반 표현 강제
- 근거 데이터 없으면 "데이터 부족" 명시

---

## 5. 파일/모듈 계획

신규:
- `src/dashboard/components/floating_chat.py`
- `src/agents/tools/portfolio_tool.py`
- `src/agents/tools/market_outlook_tool.py`
- `src/agents/tools/strategy_review_tool.py`
- `src/agents/tools/risk_diagnosis_tool.py`
- `src/agents/news/news_ingest.py` (또는 기존 scheduler 모듈 하위)

수정:
- `src/agents/factory.py` (챗봇 LLM 경로 통합 시)
- `src/agents/config.py` (구형 기본 모델 경로 정리)
- `src/agents/router.py`
- `src/agents/sql_agent.py` (read-only + DML 필터)
- `src/dashboard/pages/06_chatbot.py`
- `src/dashboard/pages/1_overview.py` 등 주요 페이지(공통 floating 삽입)
- `src/agents/prompts.py` (의도별 응답 템플릿 강화)

문서:
- `docs/work-result/17_chatbot_trading_assistant_upgrade_result.md`
- `docs/PROJECT_CHARTER.md` 반영

---

## 6. 검증 계획

### 6.1 기능 테스트

1. Floating 패널이 페이지 전환 후에도 정상 유지되는지
2. 대표 질의 세트(시장해석/전략리뷰/리스크진단/규칙검색) 응답 품질 점검
3. RAG 미사용 상황에서도 fallback 응답 정상 여부
4. `asyncio` 루프 충돌 오류 미발생 확인

### 6.2 성능/비용 테스트

1. 질의 50건 부하 테스트에서 timeout/오류율 측정
2. 1시간 모니터링 기준 LLM 호출량/크레딧 소모 기록
3. 캐시/쿨다운 적용 전후 비용 비교
4. 그래프 캐시 적용 전후 평균 응답시간 비교

### 6.3 안전성 테스트

1. 근거 없는 단정 표현 금지 여부
2. 데이터 부족 시 안전 문구 출력 여부
3. 실패 시 graceful fallback 메시지 확인
4. DML/DDL 유도 질의 차단 여부(데이터 무변경 검증)

---

## 7. 릴리즈 전략

### 7.1 우선순위-릴리즈 매핑

1. Phase 0 (P0) -> Step A-0
2. Phase 1 (P1) -> Step A
3. Phase 2 (P0) -> Step B
4. Phase 3 (P0) -> Step C
5. Phase 4A (P1) -> Step D-Design
6. Phase 4B (P1) -> Step D
7. Phase 5 (P0) -> Step B~D 공통 가드레일

### 7.2 단계별 배포

1. Step A-0: 모델/루프/SQL 보안 선행 반영
2. Step A: Floating UI만 먼저 배포 (기능 off, 기존 router 사용)
3. Step B: Intent 확장 + Tool 1~2개 활성화
4. Step C: Strategy Review 활성화
5. Step D-Design: 뉴스 소스/스키마/비용 설계 확정
6. Step D: News RAG 활성화 (feature flag)

모든 단계에서 feature flag로 즉시 비활성화 가능하도록 구성.

---

## 8. 리스크 및 대응

1. 라우팅 오분류
- 대응: 키워드 Fast Path + LLM 분류 + 재시도 fallback

2. 비용 급증
- 대응: 모델 계층화, 캐시, 쿨다운, 호출 예산

3. 데이터 품질 부족
- 대응: "불충분 데이터" 명시, 추정치 최소화

4. UI 복잡도 증가
- 대응: 페이지 내 최소 footprint 유지, 상세 기능은 06_chatbot 페이지로 분리

---

## 9. 선행/후행 의존성

선행 권장:
- 14번 (리스크 카운트 분리)
- 15번 Phase 1~2 (전략 리뷰 품질 향상에 필요)
- 16번 (Overview 가독성 개선, 동일 UX 원칙 정렬)

후행:
- 17 완료 후 `week7-chatbot`/`9_chatbot-advancement` 문서 상태 업데이트

---

## 10. 산출물

1. Floating Assistant UI
2. 확장 Router + Tooling
3. 전략 리뷰형 응답 체계
4. (옵션) 뉴스 RAG 배치 연동
5. 결과 문서 + Charter 반영

### 10.1 하위 작업 인덱스 (에픽-서브태스크)

1. `17-01`: `docs/work-plans/17-01_chatbot_consultant_intent_sell_strategy_plan.md`
2. `17-02`: `docs/work-plans/17-02_chatbot_buy_action_intent_fix_plan.md`
3. `17-03`: `docs/work-plans/17-03_news_rag_rss_only_implementation_plan.md`
4. `17-04`: `docs/work-plans/17-04_manifest_image_tag_alignment_plan.md`
5. `17-05`: `docs/work-plans/17-05_news_summary_readability_improvement_plan.md`
6. `17-06`: `docs/work-plans/17-06_latest_single_tag_operation_plan.md`
7. `17-07`: `docs/work-plans/17-07_latest_dual_redeploy_script_plan.md`
8. `17-08`: `docs/work-plans/17-08_phase5_chat_guardrails_and_model_tiering_plan.md`
9. `17-09`: `docs/work-plans/17-09_doc_numbering_conflict_fix_plan.md`

---

## 11. 리뷰 코멘트 반영 이력

### Round 1 (2026-02-19) — Claude Code Review

**검증 범위**: 계획서 전체 + 기존 코드(`router.py`, `sql_agent.py`, `rag_agent.py`, `06_chatbot.py`, `config.py`, `performance.py`, `db_connector.py`)

---

### 반영 결과 요약

1. [major] LLM 모델 경로 이원화: **반영 완료**
- 변경: Phase 0(4.0.1) 신설, `factory.py` 경로 통합 명시
- 위치: `3.4`, `4.0.1`, `5`

2. [major] `asyncio.run()` 루프 충돌 위험: **반영 완료**
- 변경: Phase 0(4.0.2)에 공용 동기 래퍼 전략 명시
- 위치: `3.4`, `4.0.2`, `6.1`

3. [major] SQL Agent 보안(프롬프트 의존): **반영 완료**
- 변경: read-only + DML 정규식 이중 가드 추가
- 위치: `3.4`, `4.0.3`, `6.3`, `5`

4. [major] 뉴스 RAG 소스/비용 미정: **반영 완료**
- 변경: Phase 4를 설계(4A)와 구현(4B)으로 분리
- 위치: `4.11~4.17`, `7.1`, `7.2`

5. [minor] 우선순위와 릴리즈 매핑 부족: **반영 완료**
- 변경: 우선순위-릴리즈 매핑 표기 추가
- 위치: `7.1`

6. [minor] 그래프 매 호출 재생성: **반영 완료**
- 변경: 싱글톤 캐시 정책 추가
- 위치: `4.6`, `4.7`, `6.2`

7. [minor] 임베딩 OpenAI 의존 비용: **반영 완료**
- 변경: 로컬 임베딩 전환 옵션과 비용 비교 명시
- 위치: `4.12`, `4.16`, `4.17`, `4.19(호출 통제)`

8. [minor] strategy_review_tool PnL 경로 불명확: **반영 완료**
- 변경: BUY/SELL 매칭 기반 계산 기본안 + `realized_pnl` 컬럼 확장안 명시
- 위치: `4.9`

---

#### [major] 1. 챗봇 LLM 모델 설정이 Bot과 별도 경로 — 통합 전략 필요

**현상**:
- Bot/AI Agent는 `src/agents/factory.py`의 `LLM_MODE` 환경변수(`dev`=Haiku 4.5, `prod`=Sonnet 4.5)로 모델을 제어
- 챗봇은 `src/agents/config.py`의 `LLM_MODEL` 환경변수(기본값 `claude-3-haiku-20240307`)로 별도 제어
- 즉, **Bot은 Haiku 4.5를 쓰지만 챗봇은 구형 Haiku 3**를 쓰는 이원화 상태

**영향**: 계획서 섹션 4.15의 "모델 계층화(기본 Haiku, 고난도 시 Sonnet 승격)"를 구현할 때, `config.py`의 `LLM_MODEL` 경로를 그대로 쓸지, `factory.py`의 `get_llm()` + `LLM_MODE`로 통합할지 결정이 필요

**권장**: Phase 5(비용/안전 가드레일) 구현 전에, 챗봇 LLM 인스턴스 생성을 `factory.py`로 통합하거나, 최소한 `config.py`의 기본 모델을 `claude-haiku-4-5-20251001`로 갱신하는 선행 작업을 계획에 명시

---

#### [major] 2. `asyncio.run()` in Streamlit — Floating Chat 확장 시 이벤트 루프 충돌 위험

**현상**:
- 현재 `06_chatbot.py`는 `asyncio.run(process_chat(prompt))`로 LangGraph를 호출
- Streamlit은 내부적으로 자체 이벤트 루프를 실행하며, `asyncio.run()`은 새 루프를 생성하므로 중첩 루프 에러(`RuntimeError: This event loop is already running`) 가능성이 있음
- 현재는 단일 페이지에서만 사용하므로 우연히 동작하고 있으나, Floating Chat를 전 페이지에 삽입하면 재현 확률이 높아짐

**권장**: Phase 1(Floating Chat) 구현 시 `asyncio.run()` 대신 `asyncio.get_event_loop().run_until_complete()` 또는 `nest_asyncio` 패치를 적용하는 방안을 계획에 포함. 또는 `process_chat()`을 동기 래퍼로 감싸는 구조를 명시

---

#### [major] 3. SQL Agent의 보안 가드레일이 프롬프트 의존 — Tool 확장 시 강화 필요

**현상**:
- `sql_agent.py`의 DML 방지가 프롬프트 지시(`절대 DML 문을 실행하지 마세요`)에만 의존
- `create_sql_agent()`의 `agent_type="tool-calling"` 모드에서 LLM이 프롬프트를 무시하고 DELETE/UPDATE를 생성할 가능성이 원천 차단되지 않음

**영향**: Phase 2에서 `strategy_review_tool`이 복잡한 집계 쿼리를 실행할 때, 실수로 DML이 실행되면 운영 데이터 손상 가능

**권장**:
- `SQLDatabase.from_uri()` 생성 시 read-only 커넥션(PostgreSQL의 `default_transaction_read_only=on`) 사용을 계획에 추가
- 또는 쿼리 실행 전 정규식 기반 DML 필터를 Tool 래퍼 수준에서 적용

---

#### [major] 4. 뉴스 RAG(Phase 4) 데이터 소스/비용 전략 미정

**현상**: 계획서 섹션 4.13에서 `news_ingest_job`(주기 수집)을 언급하지만, 다음이 미정:
- 뉴스 소스 API (CryptoPanic, CoinGecko News, RSS, 자체 스크래핑 등)
- 수집 주기 및 저장 스키마 (`news_articles` 테이블 등)
- 임베딩 모델 (기존 `text-embedding-3-small` 재사용 vs 별도)
- 요약/점수화 LLM 호출 비용 예측

**권장**: Phase 4를 "설계 → 구현" 2단계로 분리하고, 설계 단계에서 데이터 소스 선정 + 비용 시뮬레이션 + 스키마 확정을 먼저 진행. Phase 4가 P1인 점을 감안하면 Phase 2~3 완료 후 별도 계획서로 분리하는 것도 합리적

---

#### [minor] 5. Phase 우선순위 표기 혼선

**현상**:
- Phase 1(Floating Chat)은 P1, Phase 2(분석형 라우팅)는 P0, Phase 3(전략 리뷰)도 P0
- UI(Phase 1)가 완성되지 않아도 Phase 2~3의 백엔드 기능은 기존 `06_chatbot.py`에서 테스트 가능하므로, 우선순위 자체는 합리적이나 "Phase 번호 ≠ 실행 순서"라는 점이 혼란스러울 수 있음

**권장**: 섹션 7(릴리즈 전략)의 Step A~D가 실제 실행 순서를 정의하고 있으므로, 각 Phase 제목에 "(릴리즈 Step B)" 같은 매핑을 추가하면 가독성 향상

---

#### [minor] 6. `process_chat()` 매 호출 시 그래프 재생성

**현상**: `router.py` L131에서 `create_chat_graph()`를 매 호출마다 실행하여 StateGraph를 새로 compile
- 현재 규모에서 성능 이슈는 아니지만, Phase 2에서 노드가 7~8개로 늘어나면 불필요한 오버헤드

**권장**: `runner.py`의 `AgentRunner`처럼 싱글톤 패턴으로 그래프 인스턴스를 캐싱하는 리팩터링을 Phase 2 구현 시 함께 진행

---

#### [minor] 7. 기존 RAG의 임베딩 모델이 OpenAI 의존

**현상**: `rag_agent.py`에서 `OpenAIEmbeddings(model="text-embedding-3-small")`을 사용
- 계획서 섹션 3.3에서 "기존 PGVector 활용"이라고 했으므로 동일 임베딩 모델을 계속 사용할 것으로 보이나, OpenAI 임베딩 API 비용이 추가됨

**권장**: Phase 4(뉴스 RAG)에서 대량 임베딩 시 비용이 늘어날 수 있으므로, 로컬 임베딩 모델(`sentence-transformers` 등)로의 전환 가능성을 비용 섹션에 언급

---

#### [minor] 8. `strategy_review_tool`의 데이터 소스 명확화

**현상**: 계획서에서 "최근 N건 거래 성과"라고 했으나, 현재 `PerformanceAnalytics`는 `equity_curve`(자산 곡선)와 `trades`(PnL 포함 리스트)를 입력으로 받음. 그런데 `trading_history` 테이블에는 `pnl` 컬럼이 없고, PnL은 BUY/SELL 매칭으로 계산해야 함

**권장**: `strategy_review_tool` 구현 시 PnL 계산 로직(BUY avg_price vs SELL price 매칭)을 SQL 집계 또는 Python 후처리 중 어떤 방식으로 할지 명시. 또는 `trading_history`에 `realized_pnl` 컬럼을 추가하는 스키마 변경을 Phase 3 선행 작업으로 고려

---

### 종합 평가

**계획의 방향성은 적절함.** 기존 LangGraph Router 구조를 확장하는 점진적 접근, 뉴스를 배치형으로 처리하는 비용 전략, Feature Flag 기반 단계 릴리즈 모두 합리적.

**구현 착수 전 해결 권장 항목:**
1. 챗봇 LLM 모델 경로 통합 (config.py vs factory.py)
2. asyncio 이벤트 루프 전략 확정
3. SQL Agent read-only 보안 강화
4. Phase 4 뉴스 소스/스키마/비용 설계 분리

**즉시 착수 가능 항목:**
- Phase 2~3 (분석형 라우팅 + 전략 리뷰): 기존 `06_chatbot.py` + `router.py` 확장으로 시작 가능
- Phase 5 (가드레일): 기존 `guardrails.py` 패턴 재사용으로 빠르게 구현 가능

---

## 12. 구현 진행 로그

### 2026-02-20 — Codex 착수/1차 반영

1. Phase 0 반영
- 챗봇 LLM 경로를 `factory.py` 기반으로 통합 (`router.py`, `sql_agent.py`, `rag_agent.py`)
- Streamlit `asyncio.run()` 제거, 공용 동기 래퍼(`src/common/async_utils.py`) 도입
- SQL Agent read-only URL + DML/DDL 정규식 차단(실행 직전 가드) 반영

2. Phase 1 반영
- `src/dashboard/components/floating_chat.py` 신규
- 주요 대시보드 페이지(`app.py`, `1~5`, `07`)에 공통 Assistant 삽입
- `06_chatbot.py`를 상세 모드로 유지하되 공통 대화 상태/실행기 재사용으로 통합

3. Phase 2~3 Core 반영
- Router intent 확장: `market_outlook`, `strategy_review`, `risk_diagnosis`, `action_recommendation`, `portfolio_status`
- Tooling 추가:
  - `portfolio_tool.py`
  - `market_outlook_tool.py`
  - `strategy_review_tool.py` (FIFO 기반 realized PnL)
  - `risk_diagnosis_tool.py`
- 그래프 compile 싱글톤 캐시 적용

4. Deferred
- Phase 4A/4B 뉴스 RAG(소스/스키마/비용 설계 및 구현)는 본 착수 범위에서 제외

### 2026-02-20 — Phase 4 RSS Only 구현 착수/완료

- 관련 상세 계획: `docs/work-plans/17-03_news_rag_rss_only_implementation_plan.md`
- 결정: 유료 뉴스 API는 제외하고 RSS Only로 고정
- 반영 범위:
  1. 뉴스 수집/요약/리스크 점수 테이블 및 배치 파이프라인
  2. 챗봇 시장 브리핑/행동 제안의 뉴스 리스크 반영
- 비고: LLM 기반 뉴스 요약은 비용 정책 확정 전까지 규칙 기반 요약으로 운영

### 2026-02-20 — Phase 5 비용/안전 가드레일 구현 완료

- 관련 상세 계획: `docs/work-plans/17-08_phase5_chat_guardrails_and_model_tiering_plan.md`
- 반영 범위:
  1. 모델 계층화: 고난도 전략 리뷰에 한해 `premium_review` 모델(기본 Sonnet) 조건부 승격
  2. 백엔드 공통 호출 통제: 세션 쿨다운, 동일 질의 캐시(TTL/LRU), 입력/출력 길이 예산
  3. 공통 안전 후처리: 안전 고지문 누락 방지 + 시나리오 해석 문구 강제
