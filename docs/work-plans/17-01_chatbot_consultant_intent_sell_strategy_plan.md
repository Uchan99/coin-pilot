# 17-01. 챗봇 컨설턴트 응답 품질 개선 계획 (의도 분리 + 매도 타이밍 코칭)

**작성일**: 2026-02-20  
**상태**: Completed (2026-02-20)  
**우선순위**: P0 (사용자 신뢰/실사용성 직접 영향)

---

## 1. 배경 및 문제

현재 챗봇은 아래 질문에서 오분류가 발생한다.

1. "지금 보유중인 종목들 언제 매도하는게 좋아보여?"
- 기대: 보유 포지션별 매도 타이밍/경계 가격 제안
- 실제: 포트폴리오 단순 요약 반환

2. "현재 매도 전략이 어떻게돼?"
- 기대: 레짐별 청산 규칙(익절/손절/트레일링/시간 제한) 설명
- 실제: `strategy_review` 경로로 라우팅되어 "SELL 실현손익 데이터 없음" 응답

문제의 핵심은 "전략 설명"과 "전략 성과 리뷰"가 동일 의도로 묶인 라우팅 구조다.

---

## 2. 목표

1. 전략 질문을 `전략 설명`과 `성과 리뷰`로 분리
2. 보유 포지션 기반 `매도 타이밍 코칭` 전용 경로 추가
3. 데이터 부족 시에도 "왜 부족한지 + 대체 가능한 규칙 안내" 반환

---

## 3. 아키텍처 결정

### 3.1 선택안

기존 LangGraph Router에 의도를 추가한다.

- `strategy_policy`: 현재 전략/규칙 설명
- `sell_timing_advice`: 보유 종목별 매도 타이밍 제안

그리고 도구를 분리한다.

- `strategy_policy_tool`: `StrategyConfig` 기준 레짐별 청산 정책 반환
- `sell_timing_tool`: 포지션/현재가/레짐/RSI 기반 매도 시나리오 분석

### 3.2 대안 비교

1. 단일 `strategy_review_tool`에 분기 추가
- 장점: 파일 수 적음
- 단점: 데이터 리뷰/정책 설명/실행 코칭 책임이 섞여 유지보수 어려움

2. LLM 프롬프트만 수정해 의도 구분
- 장점: 구현 속도 빠름
- 단점: 재현성 낮음, 동일 질문에서 결과 흔들림

3. 별도 라우팅 의도 + 전용 도구 분리 (**채택**)
- 장점: 예측 가능한 동작, 테스트 가능한 로직 경계 확보
- 단점: 초기 구현량 증가

### 3.3 트레이드오프 및 완화

- 트레이드오프: 규칙 기반 코칭은 시장 맥락을 완전히 포착하지 못할 수 있음
- 완화: "자동매매 아님/시나리오 기반" 고지 + 임계값(손절/익절/트레일링) 명시

---

## 4. 구현 범위

### Phase A. 라우팅 의도 분리 (P0)

1. Router Intent 확장
- `strategy_policy`
- `sell_timing_advice`

2. Fast-path 키워드 우선순위 조정
- "매도/익절/청산/언제 팔" 계열 질문은 `sell_timing_advice` 우선
- "전략 장단점/성과/리뷰"는 `strategy_review`
- "매도 전략/청산 규칙/현재 전략"은 `strategy_policy`

### Phase B. 전략 정책 설명 도구 (P0)

1. `src/agents/tools/strategy_policy_tool.py` 신규
- 레짐별 exit 설정 추출
- 하드 리스크 한도(일손실/거래횟수/쿨다운) 포함

2. Router node 추가
- 사용자에게 정책 요약을 표준 포맷으로 반환

### Phase C. 매도 타이밍 코칭 도구 (P0)

1. `src/agents/tools/sell_timing_tool.py` 신규
- 보유 포지션 조회
- 심볼별 현재가/RSI/레짐 조회
- 레짐별 exit 기준으로 상태 계산:
  - 손절 구간
  - 익절 구간
  - 트레일링 활성/트리거 여부
  - 시간 제한 근접 여부

2. Router node 추가
- 포지션별 권고: `즉시 점검`, `분할익절 고려`, `홀드/경계가 관찰`

### Phase D. 테스트 및 회귀 검증 (P0)

1. Router intent 테스트 보강
2. `sell_timing_tool` 순수 로직 유닛 테스트 추가
3. 기존 테스트 회귀 확인

---

## 5. 검증 계획

1. 문법 검증
```bash
python3 -m py_compile src/agents/router.py src/agents/tools/strategy_policy_tool.py src/agents/tools/sell_timing_tool.py tests/agents/test_router_intent.py tests/agents/test_sell_timing_tool.py
```

2. 테스트
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_router_intent.py tests/agents/test_sell_timing_tool.py
```

3. 수동 질의 시나리오
- "현재 매도 전략이 어떻게돼?"
- "지금 보유중인 종목들 언제 매도하는게 좋아보여?"
- "최근 매매기록 기준으로 전략 장단점 분석해줘"

---

## 6. 롤백

1. `router.py` 의도 추가 분기 롤백
2. 신규 도구 모듈 제거 후 기존 `strategy_review`/`portfolio_status` 경로 복구

---

## 7. 산출물

1. 코드 변경
- `src/agents/router.py`
- `src/agents/tools/strategy_policy_tool.py` (new)
- `src/agents/tools/sell_timing_tool.py` (new)
- `tests/agents/test_router_intent.py`
- `tests/agents/test_sell_timing_tool.py` (new)

2. 결과 문서
- `docs/work-result/17-01_chatbot_consultant_intent_sell_strategy_result.md`

---

## 8. 변경 이력

### 2026-02-20

1. `strategy_policy` / `sell_timing_advice` 의도 분리 구현 완료
2. `strategy_policy_tool.py` / `sell_timing_tool.py` 신규 구현 완료
3. 라우터 Fast-path 우선순위 조정 완료 (매도 타이밍/전략 설명 우선)
4. 테스트 추가 및 통과 확인 완료
