# 17. AI 트레이딩 비서(챗봇) 고도화 구현 결과

**작성일**: 2026-02-20  
**작성자**: Codex (GPT-5)  
**관련 계획서**: `docs/work-plans/17_chatbot_trading_assistant_upgrade_plan.md`

---

## 1. 구현 범위 요약

이번 구현에서는 계획서 기준으로 **Phase 0 + Phase 1 + Phase 2/3 Core**를 반영했다.

1. Phase 0
- 챗봇 LLM 경로를 `src/agents/factory.py` 정책과 통합
- Streamlit 이벤트 루프 충돌 회피용 공용 래퍼 도입
- SQL Agent에 read-only 세션 + DML/DDL 정규식 차단 이중 가드 적용

2. Phase 1
- `src/dashboard/components/floating_chat.py` 신규 추가
- 대시보드 주요 페이지(`app.py`, `1_overview`, `2_market`, `3_risk`, `4_history`, `5_system`, `07_exit_analysis`)에서 공통 Assistant 사용 가능
- `06_chatbot.py`는 상세 페이지로 유지, 공통 대화 상태/실행기 재사용

3. Phase 2/3 Core
- Router intent 확장: `portfolio_status`, `market_outlook`, `strategy_review`, `risk_diagnosis`, `action_recommendation`
- 도구 모듈 추가:
  - `src/agents/tools/portfolio_tool.py`
  - `src/agents/tools/market_outlook_tool.py`
  - `src/agents/tools/strategy_review_tool.py`
  - `src/agents/tools/risk_diagnosis_tool.py`
- `process_chat()` 그래프 compile 싱글톤 캐시 적용

### 1.1 하위 결과 인덱스 (에픽-서브태스크)

1. `17-01`: `docs/work-result/17-01_chatbot_consultant_intent_sell_strategy_result.md`
2. `17-02`: `docs/work-result/17-02_chatbot_buy_action_intent_fix_result.md`
3. `17-03`: `docs/work-result/17-03_news_rag_rss_only_implementation_result.md`
4. `17-04`: `docs/work-result/17-04_manifest_image_tag_alignment_result.md`
5. `17-05`: `docs/work-result/17-05_news_summary_readability_improvement_result.md`
6. `17-06`: `docs/work-result/17-06_latest_single_tag_operation_result.md`
7. `17-07`: `docs/work-result/17-07_latest_dual_redeploy_script_result.md`
8. `17-08`: `docs/work-result/17-08_phase5_chat_guardrails_and_model_tiering_result.md`
9. `17-09`: `docs/work-result/17-09_doc_numbering_conflict_fix_result.md`

---

## 2. 아키텍처/설계 결정 기록

### 2.1 LLM 경로 통합

선택:
- 챗봇 경로를 `factory.py` 기반(`LLM_MODE`)으로 통합하고, `config.py`는 호환용 기본값만 유지

대안:
1. 기존 `config.py`의 `LLM_MODEL` 단일 경로 유지
2. Router/SQL/RAG별로 개별 모델 환경변수 분리

채택 이유/트레이드오프:
- 장점: Bot/챗봇 모델 정책 일관성 확보, 운영 전환(dev/prod) 단순화
- 단점: 기능별 세밀한 모델 분기 자유도 감소(향후 `model_type` 확장 포인트로 보완)

### 2.2 Streamlit async 실행 전략

선택:
- `src/common/async_utils.py`의 `run_async_safely()` 도입
- 루프 미실행 시 `asyncio.run`, 루프 실행 중이면 별도 스레드/루프 사용

대안:
1. `nest_asyncio` 기본 패치
2. 페이지마다 `run_until_complete` 직접 처리

채택 이유/트레이드오프:
- 장점: 공통 진입점으로 일관성/재사용성 확보, 충돌 위험 감소
- 단점: 스레드 전환 오버헤드(챗봇 요청 단위에서는 허용 가능)

### 2.3 SQL Agent 보안 강화

선택:
- read-only connection option + 실행 직전 정규식 차단(이중 방어)

대안:
1. 프롬프트 지시만 사용
2. DB 권한만 read-only로 제한

채택 이유/트레이드오프:
- 장점: LLM 오동작/프롬프트 이탈 시에도 실질적 차단 가능
- 단점: 보수적 정규식으로 일부 합법 쿼리 오탐 가능(정책상 안전 우선)

### 2.4 라우팅/도구 구조

선택:
- 의도 분류 + 도구 실행(결정적 로직) 조합
- 전략 리뷰는 FIFO 매칭 기반 실현손익 계산

대안:
1. 단일 LLM 프롬프트로 통합 답변
2. SQL Agent 하나로 모든 질의 처리

채택 이유/트레이드오프:
- 장점: 근거 데이터 경로 명확, 비용 예측/통제 용이
- 단점: 코드 모듈 수 증가, 도구별 유지보수 필요

---

## 3. 주요 변경 파일

1. Core/Agent
- `src/agents/factory.py`
- `src/agents/config.py`
- `src/common/async_utils.py` (신규)
- `src/agents/sql_agent.py`
- `src/agents/rag_agent.py`
- `src/agents/router.py`

2. Tooling
- `src/agents/tools/__init__.py` (신규)
- `src/agents/tools/_db.py` (신규)
- `src/agents/tools/portfolio_tool.py` (신규)
- `src/agents/tools/market_outlook_tool.py` (신규)
- `src/agents/tools/strategy_review_tool.py` (신규)
- `src/agents/tools/risk_diagnosis_tool.py` (신규)

3. Dashboard
- `src/dashboard/components/floating_chat.py` (신규)
- `src/dashboard/pages/06_chatbot.py`
- `src/dashboard/app.py`
- `src/dashboard/pages/1_overview.py`
- `src/dashboard/pages/2_market.py`
- `src/dashboard/pages/3_risk.py`
- `src/dashboard/pages/4_history.py`
- `src/dashboard/pages/5_system.py`
- `src/dashboard/pages/07_exit_analysis.py`

4. Tests
- `tests/agents/test_sql_agent_safety.py` (신규)
- `tests/agents/test_router_intent.py` (신규)
- `tests/common/test_async_utils.py` (신규)

5. Plan update
- `docs/work-plans/17_chatbot_trading_assistant_upgrade_plan.md`

---

## 4. 검증

### 4.1 문법 검증

```bash
python3 -m py_compile src/agents/factory.py src/agents/config.py src/common/async_utils.py src/agents/sql_agent.py src/agents/rag_agent.py src/agents/router.py src/agents/tools/_db.py src/agents/tools/portfolio_tool.py src/agents/tools/market_outlook_tool.py src/agents/tools/strategy_review_tool.py src/agents/tools/risk_diagnosis_tool.py src/dashboard/components/floating_chat.py src/dashboard/pages/06_chatbot.py src/dashboard/pages/1_overview.py src/dashboard/pages/2_market.py src/dashboard/pages/3_risk.py src/dashboard/pages/4_history.py src/dashboard/pages/5_system.py src/dashboard/pages/07_exit_analysis.py tests/agents/test_sql_agent_safety.py tests/agents/test_router_intent.py tests/common/test_async_utils.py
```

결과:
- 통과

### 4.2 신규 테스트

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_sql_agent_safety.py tests/agents/test_router_intent.py tests/common/test_async_utils.py
```

결과:
- `10 passed`

### 4.3 기존 관련 테스트 회귀

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_agents.py tests/agents/test_guardrails.py
```

결과:
- `6 passed`

---

## 5. 후속 반영 현황 (업데이트)

1. Phase 4A/4B (뉴스 RAG, RSS-Only) 완료
- 상세 결과: `docs/work-result/17-03_news_rag_rss_only_implementation_result.md`

2. Phase 5 (비용/안전 가드레일) 완료
- 상세 결과: `docs/work-result/17-08_phase5_chat_guardrails_and_model_tiering_result.md`
