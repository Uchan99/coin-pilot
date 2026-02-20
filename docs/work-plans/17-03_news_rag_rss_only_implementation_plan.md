# 17-03. 뉴스 RAG RSS-Only 구현 계획 (Phase 4A + 4B)

**작성일**: 2026-02-20  
**상태**: Completed (2026-02-20)  
**우선순위**: P1 (챗봇/리스크 컨텍스트 강화)

**연계 문서**
- 상위 계획: `docs/work-plans/17_chatbot_trading_assistant_upgrade_plan.md`
- 관련 결과: `docs/work-result/17_chatbot_trading_assistant_upgrade_result.md`

---

## 1. 배경 및 목적

17번 계획의 미구현 항목(Phase 4A/4B 뉴스 RAG)을 `RSS Only` 전략으로 구현한다.

핵심 방향:
1. 유료 뉴스 API(CoinGecko Basic $35/mo 등) 없이 RSS 수집만 사용
2. 실시간 검색형이 아니라 배치형(수집 → 요약/점수화 → 조회)
3. 챗봇 시장 해석/행동 제안에 뉴스 리스크 점수를 반영

---

## 2. 아키텍처 선택 및 대안 비교

### 선택안 (채택)
- 소스: RSS 다중 피드
- 저장: PostgreSQL 테이블 3종 (`news_articles`, `news_summaries`, `news_risk_scores`)
- 처리: Bot Scheduler 주기 작업 2개
  - `news_ingest_rss_job` (수집/정규화/중복제거)
  - `news_summarize_and_score_job` (심볼별 요약/위험점수)
- 조회: 챗봇 `market_outlook_tool`에서 최신 점수/요약 조회

### 대안 1
- CoinGecko/CryptoPanic API 사용
- 장점: 구조화 메타데이터 품질 높음
- 단점: 고정비 증가(월 구독), 현재 요구사항과 불일치

### 대안 2
- 질의 시점 실시간 웹 검색
- 장점: 최신성 높음
- 단점: 지연/비용/노이즈 증가, 운영 예측 불가

### 대안 3
- 뉴스 미반영 유지
- 장점: 구현비용 최소
- 단점: 시장 이벤트 리스크 감지 부재

### 선택안 장점/트레이드오프/완화
- 장점: 비용 최소화, 구현 단순성, 운영 예측 가능성
- 트레이드오프: RSS 메타데이터 품질 편차/노이즈
- 완화:
  1. 해시 기반 dedupe
  2. 키워드 기반 심볼 매핑 + 리스크 스코어링
  3. 데이터 부족 시 명시적 fallback

---

## 3. 구현 범위

### 3.1 데이터 스키마

1. `news_articles`
- 원문 메타 + 정규화 결과 + 리스크 힌트 저장
- 중복 방지: `content_hash` unique

2. `news_summaries`
- 심볼/시간창별 요약 텍스트 + 핵심 포인트

3. `news_risk_scores`
- 심볼/시간창별 위험 점수(0~100), 레벨(LOW/MEDIUM/HIGH), 근거 드라이버

### 3.2 RSS 파이프라인 모듈

신규 파일: `src/agents/news/rss_news_pipeline.py`

구성:
1. RSS/Atom 파싱 (표준 라이브러리 기반)
2. 기사 정규화 (title/link/content/published_at)
3. 심볼 추출 (키워드 매핑)
4. 기사 단위 위험 신호 점수화
5. DB 적재 (upsert/dedupe)
6. 심볼별 요약 + 위험점수 집계

### 3.3 스케줄러 연동

파일: `src/bot/main.py`

추가 job:
1. `news_ingest_rss_job` (10분 간격)
2. `news_summarize_and_score_job` (30분 간격)

### 3.4 챗봇 조회 경로 반영

파일: `src/agents/tools/market_outlook_tool.py`, `src/agents/router.py`

변경:
1. 시장 브리핑 응답에 `news_risk_score`, `news_risk_level`, `news_summary` 반영
2. action recommendation에서 뉴스 고위험(HIGH)일 때 보수적 판단 강화

---

## 4. 비용/운영 정책 (RSS Only)

### 4.1 비용
1. 뉴스 소스 API 고정비: $0 (RSS Only)
2. 필수 추가 비용: 없음
3. 선택 비용:
- 추후 LLM 요약 도입 시 토큰 비용 발생 가능 (본 구현은 규칙 기반 요약 우선)

### 4.2 운영 리스크
1. 피드 장애/형식 변경
- 대응: 다중 피드 + 파싱 예외 내성
2. 노이즈 기사
- 대응: 키워드 스코어 + 최근 기사 수 제한
3. 심볼 매핑 누락
- 대응: 매핑 사전 확장 가능 구조

---

## 5. 변경 파일 계획

신규:
1. `migrations/v3_3_0_news_rss_only.sql`
2. `src/agents/news/__init__.py`
3. `src/agents/news/rss_news_pipeline.py`
4. `tests/agents/test_rss_news_pipeline.py`

수정:
1. `src/common/models.py`
2. `src/bot/main.py`
3. `src/agents/tools/market_outlook_tool.py`
4. `src/agents/router.py`

문서:
1. `docs/work-result/17-03_news_rag_rss_only_implementation_result.md`
2. `docs/work-plans/17_chatbot_trading_assistant_upgrade_plan.md` (진행 로그 링크)

---

## 6. 검증 계획

1. 문법 검증
```bash
python3 -m py_compile src/agents/news/rss_news_pipeline.py src/agents/tools/market_outlook_tool.py src/agents/router.py src/bot/main.py src/common/models.py tests/agents/test_rss_news_pipeline.py
```

2. 테스트
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_rss_news_pipeline.py tests/agents/test_router_intent.py
```

3. 수동 확인
1. RSS ingest job 실행 후 `news_articles` 적재 확인
2. summarize job 실행 후 `news_risk_scores`/`news_summaries` 적재 확인
3. 시장 브리핑 질의 시 뉴스 점수/요약 노출 확인

---

## 7. 롤백

1. 스케줄러 job 비활성화
2. `market_outlook_tool` 뉴스 조회 로직 제거
3. 마이그레이션 테이블은 데이터 보존 후 미사용 상태로 둘 수 있음

---

## 8. 산출물

1. RSS 기반 뉴스 수집/요약/리스크 점수 파이프라인
2. 챗봇 시장 브리핑/행동 제안의 뉴스 리스크 반영
3. 테스트 + 결과 문서

---

## 9. 변경 이력

### 2026-02-20

1. RSS/Atom 파서 + 심볼 추출 + 키워드 위험점수 로직 구현 완료
2. 뉴스 테이블 3종 마이그레이션(`v3_3_0_news_rss_only.sql`) 추가 완료
3. Bot scheduler에 ingest/summary job 연동 완료
4. 챗봇 시장 브리핑/행동 제안에 뉴스 리스크 반영 완료
