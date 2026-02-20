# 17-03. 뉴스 RAG RSS-Only 구현 결과

**작성일**: 2026-02-20  
**작성자**: Codex (GPT-5)  
**관련 계획서**: `docs/work-plans/17-03_news_rag_rss_only_implementation_plan.md`

---

## 1. 구현 요약

17번 미구현 항목(Phase 4A/4B)을 RSS Only 전략으로 구현했다.

구현된 기능:
1. RSS/Atom 뉴스 수집 배치
2. 심볼 매핑 + 기사 단위 위험 점수화
3. 심볼별 뉴스 요약/위험점수 집계 배치
4. 챗봇 시장 브리핑/행동 제안에 뉴스 리스크 반영

핵심 특징:
- 유료 API 미사용(RSS Only)
- 실시간 검색형이 아닌 배치형
- 데이터 부족 시 안전 fallback 유지

---

## 2. 아키텍처 결정 기록

### 2.1 선택안

- `RSS -> DB(news_articles) -> 집계(news_summaries/news_risk_scores) -> 챗봇 조회`

### 2.2 대안과 비교

1. 유료 API(CoinGecko/CryptoPanic)
- 장점: 메타데이터 품질 높음
- 단점: 고정비 증가, 현재 비용 정책과 불일치

2. 질의 시점 웹 검색
- 장점: 최신성 높음
- 단점: 지연/비용/노이즈/재현성 문제

3. RSS Only (채택)
- 장점: 비용 최소, 운영 단순, 예측 가능
- 단점: 포맷 불균일/노이즈
- 완화: 해시 dedupe + 키워드 점수 + 데이터 부족 fallback

### 2.3 트레이드오프

- LLM 요약 없이 규칙 기반 요약으로 시작했기 때문에 문장 품질은 제한적일 수 있다.
- 대신 비용/안정성 측면에서 안전한 기본선을 확보했다.

---

## 3. 변경 파일

### 3.1 신규

1. `migrations/v3_3_0_news_rss_only.sql`
2. `src/agents/news/__init__.py`
3. `src/agents/news/rss_news_pipeline.py`
4. `tests/agents/test_rss_news_pipeline.py`

### 3.2 수정

1. `src/common/models.py`
- `NewsArticle`, `NewsSummary`, `NewsRiskScore` 모델 추가

2. `src/bot/main.py`
- `news_ingest_job`, `news_summary_job` 스케줄러 추가
- startup 시 뉴스 파이프라인 1회 즉시 실행

3. `src/agents/tools/market_outlook_tool.py`
- 최신 뉴스 리스크 점수/요약 조회 반영
- 마이그레이션 미적용 시 안전 fallback 처리

4. `src/agents/router.py`
- 시장 브리핑에 뉴스 리스크/요약 출력
- action recommendation에서 뉴스 HIGH 리스크 시 보수적 판단 반영

5. `.env.example`
- RSS 소스/주기/윈도우 환경변수 추가

6. `docs/work-plans/17_chatbot_trading_assistant_upgrade_plan.md`
- Phase 4 RSS Only 진행 로그 추가

---

## 4. 비기능 요구 충족

1. 비용 정책
- 뉴스 소스 API 고정비 0 (RSS Only)

2. 안정성
- 파서 예외 시 피드 단위 실패 격리
- 뉴스 테이블 미존재 시 챗봇 기능 전체가 죽지 않도록 fallback

3. 확장성
- RSS 소스는 환경변수(`NEWS_RSS_SOURCES`)로 확장 가능
- 점수 로직은 키워드 사전 확장 가능

---

## 5. 검증

### 5.1 문법 검증

```bash
python3 -m py_compile src/agents/news/rss_news_pipeline.py src/agents/tools/market_outlook_tool.py src/agents/router.py src/bot/main.py src/common/models.py tests/agents/test_rss_news_pipeline.py
```

결과:
- 통과

### 5.2 테스트

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_rss_news_pipeline.py tests/agents/test_router_intent.py tests/agents/test_sell_timing_tool.py tests/agents/test_sql_agent_safety.py tests/common/test_async_utils.py
```

결과:
- `21 passed`

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_guardrails.py tests/test_agents.py
```

결과:
- `6 passed`

---

## 6. 운영 반영 시 확인 방법

1. DB 마이그레이션 적용
```bash
kubectl exec -i -n coin-pilot-ns db-0 -- psql -U postgres -d coinpilot < migrations/v3_3_0_news_rss_only.sql
```

2. bot 재배포 후 스케줄러 로그 확인
```bash
kubectl logs -n coin-pilot-ns -l app=bot --since=30m | grep -E "RSS ingest|RSS summarize|news"
```

3. 테이블 적재 확인
```bash
kubectl exec -n coin-pilot-ns db-0 -- psql -U postgres -d coinpilot -c "SELECT COUNT(*) FROM news_articles;"
kubectl exec -n coin-pilot-ns db-0 -- psql -U postgres -d coinpilot -c "SELECT symbol, risk_score, risk_level, window_end FROM news_risk_scores ORDER BY window_end DESC LIMIT 10;"
```

4. 챗봇 확인 질문
- "BTC 시장 브리핑 해줘"
- "지금 BTC 매수 보류가 맞아?"

기대:
- 브리핑에 뉴스 리스크 점수/요약 노출
- 행동 제안에서 뉴스 HIGH 리스크 시 보류 강화

---

## 7. 남은 과제

1. RSS 소스 품질별 가중치(출처 신뢰도) 추가
2. 키워드 기반 점수의 false positive/negative 튜닝
3. 필요 시 후속 단계에서 LLM 요약을 feature flag로 제한 도입
