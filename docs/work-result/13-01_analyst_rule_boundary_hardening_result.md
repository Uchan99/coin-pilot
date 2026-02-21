# 13-01. Analyst Rule Boundary Hardening 구현 결과

작성일: 2026-02-21
작성자: Codex
관련 계획서: `docs/work-plans/13-01_analyst_rule_boundary_hardening_plan.md`
상태: Implemented
완료 범위: Phase 1
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - Analyst 프롬프트/입력에서 Rule Engine 검증 항목 직접 노출 제거.
  - 캔들 패턴 전용 요약 피처 생성 로직 추가.
  - reasoning 경계 위반(RSI/MA/거래량/BB 재검증) 감지 + 1회 재시도 + 재발 시 강제 REJECT 적용.
- 목표(요약):
  - Rule Engine과 AI Analyst 역할 분리의 코드 레벨 강제.
- 이번 구현이 해결한 문제(한 줄):
  - AI REJECT 사유의 Rule Engine 중복 검증 경향을 구조적으로 억제.

---

## 2. 구현 내용(핵심 위주)
### 2.1 Analyst 입력 경로 축소(OHLC + 패턴 요약)
- 파일/모듈:
  - `src/agents/analyst.py`
  - `src/agents/prompts.py`
- 변경 내용:
  - Analyst user prompt에서 RSI/MA/거래량 필드를 제거하고, 패턴 분석 전용 피처 블록으로 교체.
  - `market_context`는 `sanitize_market_context_for_analyst()`로 OHLC만 전달되도록 축소(volume 제외).
  - `extract_candle_pattern_features()`를 추가해 최근 6시간 기준 방향성/연속 양음봉/꼬리비율/변동폭 확장 비율 계산.
- 효과/의미:
  - 모델이 Rule Engine 조건을 다시 판단할 유인을 줄이고 캔들 패턴/이상 징후 분석에 집중하도록 유도.

### 2.2 Analyst 출력 경계 검증 추가
- 파일/모듈:
  - `src/agents/analyst.py`
- 변경 내용:
  - `contains_rule_revalidation_reasoning()`로 reasoning 내 중복 검증 단서 탐지.
  - 위반 시 보정 지시를 붙여 1회 재시도.
  - 재시도 후에도 위반이면 정책 위반으로 보수 REJECT 반환.
- 효과/의미:
  - 단순 프롬프트 의존이 아닌 실행 경계(guardrail)에서 재발을 차단.

### 2.3 회귀 방지 테스트 추가
- 파일/모듈:
  - `tests/agents/test_analyst_rule_boundary.py` (신규)
- 변경 내용:
  - 프롬프트에서 RSI/MA/거래량 텍스트 제거 검증.
  - 경계 위반 키워드 감지 검증.
  - 컨텍스트 sanitize(개수 제한/volume 제거) 검증.
  - 패턴 피처 계산 키/범위 검증.
- 효과/의미:
  - 추후 프롬프트/입력 수정 시 역할 분리 회귀를 빠르게 탐지 가능.

---

## 3. 변경 파일 목록
### 3.1 수정
1) `src/agents/prompts.py`
2) `src/agents/analyst.py`
3) `pytest.ini`

### 3.2 신규
1) `docs/work-plans/13-01_analyst_rule_boundary_hardening_plan.md`
2) `docs/work-result/13-01_analyst_rule_boundary_hardening_result.md`
3) `tests/agents/test_analyst_rule_boundary.py`

### 3.3 삭제(없으면 생략)
- 없음

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점: 코드 롤백만 수행

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `python3 -m compileall -q src tests/agents/test_analyst_rule_boundary.py`
- 결과:
  - 통과.

### 5.2 테스트 검증
- 실행 명령:
  - `pytest -q tests/agents/test_analyst_rule_boundary.py tests/test_bot_reason_consistency.py`
  - `python3 -m pytest -q tests/agents/test_analyst_rule_boundary.py tests/test_bot_reason_consistency.py`
- 결과:
  - 초기에는 `pytest` 엔트리포인트 실행 시 `src` import 경로 미설정으로 실패.
  - `pytest.ini`에 `pythonpath = .` 반영 후 동일 명령 재실행 결과 통과.
  - 최종 결과: `6 passed`.

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법(healthcheck, curl, kubectl 등):
  - 단위 테스트 통과 후 운영 반영은 미실행.
- 결과:
  - 없음(운영 검증은 후속).

---

## 6. 배포/운영 확인 체크리스트(필수)
1) 런타임 이미지/venv에 `requirements.txt` 반영 후 테스트 재실행.
2) `agent_decisions.reasoning`에서 RSI/MA/거래량/BB 중복 키워드 비율 관측.
3) REJECT 급증 여부(특히 `Analyst reasoning violated rule boundary...`) 모니터링.

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 입력 최소화(OHLC + 패턴 피처) + 출력 경계 검증(재시도 1회) 방식.
- 고려했던 대안:
  1) 프롬프트 문구 강화만 수행(입력 구조 유지).
  2) 모델 상향(Sonnet 고정)으로 추론 품질에 의존.
  3) Critic Agent 추가로 2차 판정.
  4) 입력 축소 + 경계 검증(채택).
- 대안 대비 실제 이점(근거/관측 포함):
  1) 구조적 원인(입력 과노출)을 직접 제거.
  2) 비용 증가 없이 재발 방지력을 확보.
  3) 기존 워크플로우 변경 최소화로 배포 리스크가 낮음.
- 트레이드오프(단점)와 보완/완화:
  1) 키워드 기반 위반 탐지는 오탐/미탐 가능성이 있음.
  2) 재시도 1회로 AI 지연이 소폭 증가할 수 있음.

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `src/agents/analyst.py`의 sanitize/feature 추출 함수 docstring.
  2) `src/agents/analyst.py`의 경계 위반 재시도/강제 REJECT 분기 주석.
- 주석에 포함한 핵심 요소:
  - 의도/왜(why): Rule Engine과 Analyst 역할 분리 강제.
  - 불변조건(invariants): RSI/MA/거래량/BB 재검증 근거 허용 금지.
  - 엣지케이스/실패 케이스: invalid candle 데이터, parsing 실패, 재시도 후 위반 지속.
  - 대안 대비 판단 근거: 문구 강화만으로는 구조적 재발 차단이 어려움.

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - 입력 축소, 경계 검증, 테스트 추가를 모두 수행.
- 변경/추가된 부분(왜 바뀌었는지):
  - 별도 변경 없음.
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음.

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - 코드 레벨에서 Analyst 중복 검증 유인을 줄였고, 위반 시 자동 차단 경로를 추가함.
  - 다만 현재 실행 환경 의존성 부족으로 pytest 기반 런타임 검증은 미완료.
- 후속 작업(다음 plan 번호로 넘길 것):
  1) 배포/CI 환경에서 테스트 실행 후 결과를 본 문서 하단 Phase 2로 보강.
  2) 운영 72h 관측으로 forbidden term 세트 오탐/미탐 조정.

---

## 11. (선택) Phase 2+ 선반영/추가 구현 결과
- Phase 2 (2026-02-21)
  - 추가 변경 요약:
    - `pytest` 단독 실행 시 프로젝트 루트 import 경로를 보장하도록 `pytest.ini` 보완.
  - 추가 변경 파일:
    - `pytest.ini`
  - 추가 검증 결과:
    - `.venv`에서 `pytest -q tests/agents/test_analyst_rule_boundary.py tests/test_bot_reason_consistency.py` 실행
    - `6 passed in 2.22s`
  - 영향/리스크:
    - 테스트 실행 편의성/재현성 개선, 런타임 동작 영향 없음.

---

## 12. References
- 링크:
  - `docs/work-plans/13-01_analyst_rule_boundary_hardening_plan.md`
  - `src/agents/analyst.py`
  - `src/agents/prompts.py`
  - `tests/agents/test_analyst_rule_boundary.py`
