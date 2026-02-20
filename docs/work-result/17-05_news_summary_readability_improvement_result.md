# 17-05. 뉴스 요약 가독성 개선 결과

**작성일**: 2026-02-20  
**작성자**: Codex (GPT-5)  
**관련 계획서**: `docs/work-plans/17-05_news_summary_readability_improvement_plan.md`

---

## 1. 구현 요약

사용자 피드백("기사를 봐도 무슨 내용인지 알기 어렵다")을 반영해 뉴스 요약 출력을 한국어 이슈 중심으로 개선했다.

핵심 변경:
1. 기사 제목 나열형 요약 제거
2. 카테고리 기반 한국어 요약 생성
3. 기존 영어 중심 요약 데이터도 조회 시 한국어 해석 fallback 적용

---

## 2. 변경 내용

1. `src/agents/news/rss_news_pipeline.py`
- `ISSUE_TOPICS` 카테고리 사전 추가
  - 거시/정책, 규제/법률, 거래소/보안, 기관/ETF, 프로젝트/기술
- `_build_summary()` 로직 변경
  - 기존: 상위 영문 헤드라인 3개 나열
  - 변경: `핵심 이슈는 A, B, C 중심` 형태의 한국어 설명
- `risk_drivers`를 한국어 라벨로 정규화
- `key_points`도 카테고리 통계 문장으로 생성

2. `src/agents/tools/market_outlook_tool.py`
- 드라이버 기반 한국어 해석기 추가
- DB의 기존 요약이 영문 나열이어도, 조회 시 한국어 요약 문장 우선 반환

3. `tests/agents/test_rss_news_pipeline.py`
- 요약 가독성 테스트 추가
  - 영문 헤드라인 원문이 summary_text에 그대로 노출되지 않는지 검증

---

## 3. 아키텍처 결정 기록

### 선택 이유
- LLM 번역/요약 없이도 즉시 적용 가능하고 비용 증가가 없다.
- 규칙 기반 요약은 표현 다양성은 낮지만, 운영 예측 가능성과 안정성이 높다.

### 고려한 대안
1. LLM 기반 번역/요약
- 장점: 자연스러운 문장
- 단점: 비용/지연 증가

2. 기존 제목 나열 유지
- 장점: 구현 비용 없음
- 단점: 사용자 이해도 낮음

### 트레이드오프
- 규칙 기반은 문장 자연스러움이 제한적이지만, 비용 0과 재현성을 얻는다.

---

## 4. 검증

```bash
python3 -m py_compile src/agents/news/rss_news_pipeline.py src/agents/tools/market_outlook_tool.py tests/agents/test_rss_news_pipeline.py
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_rss_news_pipeline.py
```

결과:
- `6 passed`

추가 회귀:
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_router_intent.py tests/agents/test_sell_timing_tool.py tests/agents/test_sql_agent_safety.py tests/common/test_async_utils.py
```

결과:
- `16 passed`

---

## 5. 적용 후 기대 효과

1. 브리핑에서 "무슨 이슈인지"를 한국어로 즉시 파악 가능
2. 영문 기사 제목 나열로 인한 이해도 저하 완화
3. 기존 DB 데이터에도 fallback 해석이 적용되어 즉시 체감 가능

---

## 6. 운영 적용 시 참고

현재 배포 컨테이너에 본 변경이 반영되려면 재빌드/재배포가 필요하다.

1. bot 이미지 재빌드/적용
2. dashboard 이미지 재빌드/적용
3. 뉴스 summarize job 1회 수동 실행(선택)
