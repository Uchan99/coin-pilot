# 17-05. 뉴스 요약 가독성 개선 계획 (한국어 이슈 요약화)

**작성일**: 2026-02-20  
**상태**: Completed (2026-02-20)  
**우선순위**: P1

---

## 1. 문제

현재 뉴스 요약이 영어 기사 제목 나열 형태라 사용자 관점에서 "무슨 내용인지" 파악이 어렵다.

예시:
- `주요 이슈: <영문 헤드라인 3개>`

---

## 2. 목표

1. 요약 문장을 "한국어 이슈 중심"으로 변환
2. 기사 제목 나열 대신 카테고리/리스크 해석 제공
3. 기존 데이터(영문 요약)도 조회 시 한국어 해석 fallback 제공

---

## 3. 아키텍처/대안

### 선택안
- 키워드 기반 주제 추출 → 한국어 카테고리 요약 생성
- 조회 시점(`market_outlook_tool`)에서 드라이버 기반 해석 문장 생성

### 대안 1
- LLM 번역/요약 즉시 적용
- 장점: 자연스러운 문장
- 단점: 비용/지연 증가

### 대안 2
- 기존 제목 나열 유지
- 장점: 구현 없음
- 단점: 사용자 경험 저하 지속

### 트레이드오프
- 규칙 기반 문장은 LLM보다 유연성이 낮음
- 대신 비용 0, 예측 가능성, 즉시 적용이 가능

---

## 4. 구현 범위

1. `src/agents/news/rss_news_pipeline.py`
- 주제 카테고리 추출 로직 추가
- `_build_summary`를 한국어 이슈 요약 중심으로 변경

2. `src/agents/tools/market_outlook_tool.py`
- `drivers` 기반 한국어 해석 문장 생성
- 기존 DB 요약이 영어 나열이어도 한국어 해석 우선 출력

3. 테스트
- `tests/agents/test_rss_news_pipeline.py`에 요약 가독성 검증 케이스 추가

---

## 5. 검증

```bash
python3 -m py_compile src/agents/news/rss_news_pipeline.py src/agents/tools/market_outlook_tool.py tests/agents/test_rss_news_pipeline.py
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_rss_news_pipeline.py
```

---

## 6. 산출물

1. 한국어 중심 뉴스 요약 로직
2. 결과 문서: `docs/work-result/17-05_news_summary_readability_improvement_result.md`

---

## 7. 변경 이력

### 2026-02-20

1. `rss_news_pipeline.py` 요약 로직을 주제/카테고리 중심 한국어 문장으로 개선
2. `market_outlook_tool.py`에 드라이버 기반 한국어 해석 fallback 추가
3. 요약 가독성 테스트 추가 및 통과
