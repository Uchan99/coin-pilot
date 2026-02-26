# 21-02. LLM 모델(Haiku vs GPT-4o-mini) 실시간 매매/비용 비교 결과

작성일: 2026-02-26
작성자: Codex
관련 계획서: docs/work-plans/21-02_llm_model_haiku_vs_gpt4omini_comparison_plan.md
상태: Verified
완료 범위: Phase 1
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - 현재 코드 기준으로 Haiku, GPT-4o-mini 실제 사용처를 확정했다.
  - 공식 벤더 가격 기준으로 사용량(토큰/호출수)별 비용 계산식을 정리했다.
  - "실시간 매매 판단에서 어떤 모델이 더 좋은가"를 비용/운영 안정성/품질 관점으로 분리해 결론을 제시했다.
- 목표(요약):
  - 모델 선택 의사결정을 감(느낌)이 아니라 코드 경로 + 단가 + 운영 리스크로 판단 가능하게 만든다.
- 이번 구현이 해결한 문제(한 줄):
  - 실시간 모델 선택(Haiku vs GPT-4o-mini)과 API 크레딧 소모를 한 문서에서 즉시 비교할 수 있게 했다.

---

## 2. 구현 내용(핵심 위주)
### 2.1 코드 기준 실제 모델 사용처 확정
- 파일/모듈:
  - `src/agents/factory.py`
  - `src/agents/analyst.py`
  - `src/agents/guardian.py`
  - `src/agents/router.py`
  - `src/agents/sql_agent.py`
  - `src/agents/rag_agent.py`
  - `src/agents/daily_reporter.py`
  - `src/analytics/exit_performance.py`
  - `deploy/cloud/oci/docker-compose.prod.yml`
- 변경 내용:
  - 코드 분석만 수행(동작 변경 없음).
  - 다음을 확정:
    - 실시간 매매 판단 경로(Analyst/Guardian)는 `factory.py` 경유 Anthropic 모델(현재 운영 기본 Haiku) 사용
    - 챗봇/SQL/RAG 생성도 `get_chat_llm()` 경유 Anthropic 사용
    - GPT-4o-mini는 Daily Report/Exit 분석 텍스트 생성에 사용
    - RAG 임베딩은 OpenAI(`text-embedding-3-small`) 사용
- 효과/의미:
  - "현재 어디에 어떤 모델이 붙어 있는지"를 명확히 고정하여 비용 산정의 기준점을 확보함.

### 2.2 공식 단가 기반 비용(크레딧 소모) 비교
- 파일/모듈:
  - 외부 공식 문서 참조(References)
- 변경 내용:
  - 단가 기준(USD / 1M tokens):
    - Claude Haiku 4.5: Input $1.00, Output $5.00
    - GPT-4o-mini: Input $0.15, Output $0.60
  - 계산식:
    - `Cost = (InputTokens/1,000,000 * InputPrice) + (OutputTokens/1,000,000 * OutputPrice)`
- 효과/의미:
  - 토큰 사용량만 알면 월 비용을 즉시 계산할 수 있음.

### 2.3 사용량 시나리오별 비용 예시
- 파일/모듈:
  - 본 문서(산식 기반)
- 변경 내용:
  - Analyst 1회 호출 기준 예시:

| 시나리오 | 입력 토큰 | 출력 토큰 | Haiku 4.5 | GPT-4o-mini |
| :--- | ---: | ---: | ---: | ---: |
| Small | 1,500 | 200 | $0.00250 | $0.000345 |
| Medium | 3,000 | 400 | $0.00500 | $0.000690 |
| Large | 6,000 | 800 | $0.01000 | $0.001380 |

  - 비용 배율(동일 토큰 가정): Haiku 4.5가 GPT-4o-mini 대비 약 **7.25배**.
  - 실시간 루프(Analyst + 일부 Guardian) 예시:
    - 후보 신호 1,000건, Guardian 진입률 20%, Medium 토큰 가정 시
    - 총 호출수 ≈ 1,200회
    - Haiku 4.5: 약 $6.00
    - GPT-4o-mini: 약 $0.828
- 효과/의미:
  - "사용량별 크레딧 소모"를 운영자 관점 숫자로 바로 비교 가능.

### 2.4 결론: "실시간은 Haiku가 더 좋은가?"에 대한 판정
- 결론 요약:
  - **비용만 보면 GPT-4o-mini가 명확히 유리**하다.
  - **품질/안정성은 현재 코드와 프롬프트 튜닝 기준으로 Haiku 경로에 맞춰져 있어 단정 비교 불가**.
  - 따라서 "Haiku가 무조건 더 좋다"는 결론은 아님.
- 운영 권장:
  - 즉시 전면 교체보다, 10~20% 트래픽 카나리로 비교 후 결정.
  - 비교 지표:
    - 구조화 출력 파싱 실패율
    - BoundaryAudit 비율
    - 최종 CONFIRM/REJECT 분포 왜곡 여부
    - 평균 응답 지연, 타임아웃율, 일일 비용

---

## 3. 변경 파일 목록
### 3.1 수정
1) `docs/work-plans/21-02_llm_model_haiku_vs_gpt4omini_comparison_plan.md` (상태/승인정보 반영)

### 3.2 신규
1) `docs/work-result/21-02_llm_model_haiku_vs_gpt4omini_comparison_result.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점: 없음

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `rg -n "gpt-4o-mini|ChatOpenAI|get_analyst_llm|get_guardian_llm|get_chat_llm|OpenAIEmbeddings" src`
  - `nl -ba src/agents/factory.py | sed -n '1,80p'`
  - `nl -ba deploy/cloud/oci/docker-compose.prod.yml | sed -n '70,90p'`
- 결과:
  - 실시간 경로는 `factory.py` 기반 Anthropic 모델 경로임을 확인
  - GPT-4o-mini는 Daily/Exit 분석 경로에 국한됨을 확인

### 5.2 테스트 검증
- 실행 명령:
  - 없음(문서 작업)
- 결과:
  - 코드 동작 변경 없음

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법:
  - `docker compose ... exec -T bot python -c "from src.config.strategy import get_config; ..."`
- 결과:
  - 별도 런타임 변경 없음

---

## 6. 배포/운영 확인 체크리스트(필수)
1) 모델 비교 결과 공유 전, `.env`의 `LLM_MODE`, `LLM_MODEL` 실제 운영값 확인  
2) 모델 전환 시 A/B 기간(최소 24h) 동안 파싱 실패율/타임아웃율을 함께 관측  
3) 비용 추정은 반드시 "실측 토큰(입출력)"으로 재계산 후 확정

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 현행: 실시간 의사결정은 Haiku 중심, 배치/리포트는 GPT-4o-mini 유지
  - 비용판단 문서화 후, 전면 전환 대신 카나리 방식 권장
- 고려했던 대안:
  1) 실시간도 GPT-4o-mini로 전면 교체
  2) 현행 Haiku 완전 고정(전환 실험 없음)
  3) 실시간 하이브리드(기본 GPT-4o-mini + 특정 케이스만 Haiku/Sonnet 승격)
- 대안 대비 실제 이점(근거/관측 포함):
  1) 운영 리스크(품질 저하 가능성)와 비용 절감을 동시에 관리 가능
  2) 현재 프롬프트/가드레일 체계를 깨지 않고 비교 가능
  3) 모델 단가 변동 시에도 동일 계산식으로 재평가 가능
- 트레이드오프(단점)와 보완/완화:
  1) 카나리 운영은 관측/분석 작업이 추가됨
  2) 벤더 이원화(OpenAI+Anthropic) 복잡성은 유지됨

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) 해당 없음(코드 변경 없음)
  2) 해당 없음
- 주석에 포함한 핵심 요소:
  - 해당 없음

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - 코드 경로 확인, 공식 단가 수집, 사용량별 비용표 작성 완료
- 변경/추가된 부분(왜 바뀌었는지):
  - 단순 장단점 비교를 넘어 카나리 운영 지표까지 추가하여 실제 전환 의사결정 가능 수준으로 보강
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - "Haiku가 항상 더 낫다"는 결론은 근거 부족
  - 비용만 보면 GPT-4o-mini가 크게 유리
  - 실시간 품질은 A/B(카나리) 실측으로 확정해야 함
- 후속 작업(다음 plan 번호로 넘길 것):
  1) 21-03: 실시간 의사결정 모델 카나리 실험 계획서 작성(10~20% 트래픽)
  2) 21-04: 실측 토큰/비용 수집 대시보드 추가(모델별 비용 관측)

---

## 12. References
- OpenAI API Pricing: https://openai.com/api/pricing/
- OpenAI model page (GPT-4o-mini): https://platform.openai.com/docs/models/gpt-4o-mini
- Anthropic Claude pricing: https://www.anthropic.com/pricing#anthropic-api
- Anthropic models overview: https://docs.claude.com/en/docs/about-claude/models/all-models

---

## 13. (선택) Phase 2+ 선반영/추가 구현 결과
- 추가 변경 요약:
  - 사용자 요청에 따라 `gpt-4o`(4o-mini 상위)와 Claude Sonnet 미만(Haiku 계열)까지 확장 비교를 추가했다.
  - 기존 결론(비용은 mini 우위, 품질은 실측 필요)을 상위 모델 포함 관점으로 재정리했다.
- 추가 변경 파일:
  - `docs/work-result/21-02_llm_model_haiku_vs_gpt4omini_comparison_result.md` (본 파일 섹션 추가)
- 추가 검증 결과:
  - 공식 단가 출처 재확인 후 계산식/예시 값 재산출 완료
- 영향/리스크:
  - 가격 정책 변경 시 표와 예시 값이 변동될 수 있으므로 월 1회 재검토 필요

### 13.1 확장 비교 범위
- OpenAI:
  - `gpt-4o-mini`
  - `gpt-4o` (mini 상위 모델)
- Anthropic (Sonnet 미만 조건 반영):
  - `Claude Haiku 4.5`
  - `Claude 3.5 Haiku` (legacy 경로, 운영 사용 전 가용성 재확인 필요)

### 13.2 단가 비교 (USD / 1M tokens)
| 모델 | Input | Output | 비고 |
| :--- | ---: | ---: | :--- |
| GPT-4o-mini | 0.15 | 0.60 | OpenAI 저비용 기본 |
| Claude Haiku 4.5 | 1.00 | 5.00 | Sonnet 미만 중 최신 Haiku 계열 |
| Claude 3.5 Haiku | 0.80 | 4.00 | Legacy 라인(가용성/정책 확인 필요) |
| GPT-4o | 2.50 | 10.00 | OpenAI 상위 모델 |

### 13.3 1회 호출 예시 비용 (입력 3,000 / 출력 400 tokens)
- 계산식:
  - `Cost = (InputTokens/1,000,000 * InputPrice) + (OutputTokens/1,000,000 * OutputPrice)`
- 결과:
  - GPT-4o-mini: `$0.00069`
  - Claude 3.5 Haiku: `$0.00400` (mini 대비 약 `5.80x`)
  - Claude Haiku 4.5: `$0.00500` (mini 대비 약 `7.25x`)
  - GPT-4o: `$0.01150` (mini 대비 약 `16.67x`)

### 13.4 실시간 매매 경로에 대한 운영 해석
1) 호출량이 많은 실시간 경로(Analyst/Guardian)는 비용 민감도가 매우 크다.  
2) 비용 기준 우선순위는 `gpt-4o-mini` > `Claude 3.5 Haiku` > `Claude Haiku 4.5` > `gpt-4o`.  
3) 품질/안정성 관점에서 상위 모델을 쓰려면 전면 교체보다 "조건부 승격"이 안전하다.
- 권장 승격 규칙 예:
  - 기본: `gpt-4o-mini`
  - 승격: `gpt-4o` (구조화 출력 파싱 실패 재시도, BoundaryAudit 다발 구간, 고위험 심볼 구간)
  - Claude 경로 유지 시: Haiku 4.5를 기본으로 두고 Sonnet 승격은 별도 정책으로 분리

### 13.5 판정(질문에 대한 직접 답변)
- "실시간 매매판단에서 Haiku가 4o-mini보다 더 좋다"는 결론은 **현재 근거로 확정 불가**.
- 비용 관점에서는 **4o-mini가 유의미하게 유리**.
- 실시간 정확도/일관성은 모델별 A/B 실측(파싱 실패율, 타임아웃율, CONFIRM/REJECT 분포, 손익 지표)로 최종 판정해야 한다.

### 13.6 추가 References (Phase 2)
- OpenAI Pricing (official): https://openai.com/api/pricing/
- OpenAI GPT-4o docs: https://platform.openai.com/docs/models/gpt-4o
- Anthropic Pricing (official): https://www.anthropic.com/pricing#anthropic-api
- Anthropic Model Deprecations/availability: https://docs.anthropic.com/en/docs/about-claude/model-deprecations

### 13.7 월간 호출량(신호량) 기준 예상 비용표
- 가정:
  - Analyst 1차 호출 + Guardian 2차 호출 비율 20%
  - 1회 호출 토큰: 입력 3,000 / 출력 400 (13.3의 Medium 시나리오)
  - 월 30일
  - 일일 호출수 계산: `DailyCalls = DailySignals * 1.2`
  - 월간 비용 계산: `MonthlyCost = DailyCalls * 30 * CostPerCall`
- 호출 1회 단가(재사용):
  - GPT-4o-mini: `$0.00069`
  - Claude 3.5 Haiku: `$0.00400`
  - Claude Haiku 4.5: `$0.00500`
  - GPT-4o: `$0.01150`

| 일일 신호량 | 일일 호출수(×1.2) | 월간 호출수 | GPT-4o-mini | Claude 3.5 Haiku | Claude Haiku 4.5 | GPT-4o |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 500 | 600 | 18,000 | $12.42 | $72.00 | $90.00 | $207.00 |
| 1,000 | 1,200 | 36,000 | $24.84 | $144.00 | $180.00 | $414.00 |
| 5,000 | 6,000 | 180,000 | $124.20 | $720.00 | $900.00 | $2,070.00 |

### 13.8 `gpt-4o-mini`를 메인 AI Decision 모델로 바꿀 때 수정사항
- 전제:
  - 현재 `src/agents/factory.py`는 `ChatAnthropic` 단일 경로이다.
  - 따라서 `.env`의 `LLM_MODEL=gpt-4o-mini`만 바꾸면 동작하지 않는다(Anthropic 클라이언트가 OpenAI 모델명을 해석 불가).
- 최소 수정안(권장: AI Decision 경로만 전환):
  1) `src/agents/factory.py`
     - `from langchain_openai import ChatOpenAI` 추가
     - provider 분기 추가(예: `LLM_PROVIDER=anthropic|openai`)
     - `get_analyst_llm()`, `get_guardian_llm()`에서 provider 기반으로 `ChatOpenAI(model="gpt-4o-mini", temperature=0)` 반환 가능하게 구현
  2) `deploy/cloud/oci/docker-compose.prod.yml`
     - bot env에 `LLM_PROVIDER=openai`(또는 Analyst/Guardian 전용 변수) 추가
     - `LLM_MODEL=gpt-4o-mini` 반영
  3) 운영 `.env` (OCI)
     - `OPENAI_API_KEY` 유효성 확인(이미 필수로 요구됨)
     - 필요 시 Anthropic 키는 챗봇/RAG 생성 경로 유지 여부에 따라 보관
  4) 검증
     - bot 시작 로그에서 모델/provider 출력 확인
     - `agent_decisions.model_used` 값이 `gpt-4o-mini`로 기록되는지 확인
     - 24h 동안 파싱 실패율/타임아웃율/CONFIRM 분포 관측

- 구조 대안(트레이드오프):
  - 대안 A: 전역 `get_llm()` provider 전환(단순)
    - 장점: 코드 변경 작음
    - 단점: 챗봇/SQL/RAG 생성 경로까지 같이 바뀌어 영향 범위 큼
  - 대안 B: Analyst/Guardian 전용 provider 분리(권장)
    - 장점: 실시간 의사결정만 타겟 변경 가능
    - 단점: 설정/코드 경로가 1단계 복잡해짐

### 13.9 AI Decision temperature 설정 현황
- 현재 AI Decision 경로:
  - Analyst: `get_analyst_llm()` → `get_llm(..., temperature=0)`  
    (`src/agents/factory.py:55`, `src/agents/factory.py:57`)
  - Guardian: `get_guardian_llm()` → `get_llm(..., temperature=0)`  
    (`src/agents/factory.py:60`, `src/agents/factory.py:62`)
- 참고:
  - 의도 분류기(classifier)도 temperature=0  
    (`src/agents/router.py:430`)
  - 배치 리포트/분석은 별도:
    - DailyReporter: `gpt-4o-mini`, temperature=0.7
    - ExitPerformanceAnalyzer: `gpt-4o-mini`, temperature=0.2
