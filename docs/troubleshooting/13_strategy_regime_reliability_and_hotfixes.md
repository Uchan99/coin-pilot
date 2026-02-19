# 13. 전략 레짐 신뢰성 및 운영 핫픽스 트러블슈팅

**작성일**: 2026-02-19  
**작성자**: Codex (GPT-5)  
**상태**: 해결 완료 (Resolved)  
**관련 결과 문서**: `docs/work-result/13_strategy_regime_phase1_implementation_result.md`
**관련 계획 문서**: `docs/work-plans/13_strategy_regime_reliability_plan.md`

---

## 0. 계획 수립 트리거 (Why 13 Started)

`13` 계획은 신규 기능 개발보다, 운영 중 드러난 신뢰성 이슈를 복구하기 위한 트러블슈팅에서 시작되었다.

주요 트리거:
1. Rule Engine 단계에서 진입 후보가 비정상적으로 적거나(초기) 특정 구간에서 과도하게 많아짐(후기)  
2. AI 호출량 급증으로 크레딧 소진 및 연쇄 에러 발생  
3. 모델 모드/직렬화/응답 파싱 등 운영 장애가 복합적으로 겹쳐 관측 신뢰도 저하  
4. 대시보드/상태 스트림 불일치로 운영자 판단 비용 증가

따라서 `13`은 "전략 개선"이 아니라, **실운영 안정성 복구 + 재발 방지 체계 확립**을 목표로 한 트러블슈팅 프로젝트로 정의되었다.

---

## 1. 개요

`13` 작업 동안 운영 모니터링에서 확인된 주요 장애/품질 이슈와, 실제 적용한 핫픽스 내용을 기록한다.

핵심 축:
1. 전략 레짐 신호 품질 회복 (Rule Engine 중심)
2. AI 호출량/에러 안정화
3. 대시보드 런타임 에러 복구
4. SELL 경로 상태 일관성 보강

---

## 2. 주요 이슈와 조치

### 2.1 AI 호출 과다 및 크레딧 소진

**증상**
- SIDEWAYS 구간에서 Rule 통과 비율이 높아 AI Decision이 과다 발생.
- Anthropic 크레딧 소진 후 AI 에러 누적.

**원인**
- SIDEWAYS 진입 조건이 운영 구간 대비 완화되어 후보가 과도하게 생성됨.
- AI 호출 가드레일이 충분히 강하지 않았음.

**조치**
- SIDEWAYS 룰 강화:
  - `rsi_7_recover` 상향, `min_rsi_7_bounce_pct` 상향
  - `ma_proximity_pct` 상향, `volume_min_ratio` 상향
  - `bb_recovery_sustain_candles` 도입
- AI Guardrails 도입:
  - 심볼별 REJECT 단계형 쿨다운(5/10/15분)
  - 시간/일 예산 상한
  - low-credit / error-streak 글로벌 블록

**결과**
- 불필요한 AI 호출이 감소하고, 호출 실패 시 보수적 차단 경로 확보.

---

### 2.2 LLM 모드/모델 불일치

**증상**
- `LLM_MODE=dev` 의도였으나 Sonnet이 계속 사용되는 구간 발생.

**원인**
- 배포 환경값/모델 매핑 경로 확인 필요 상태.

**조치**
- `k8s/apps/bot-deployment.yaml`에서 `LLM_MODE=dev` 반영.
- 모델 선택 매핑 로직 정리(`src/agents/factory.py`).
- Pod 내부 실측으로 모델명 검증.

**결과**
- 최종 검증 시 `claude-haiku-4-5-20251001` 사용 확인.

---

### 2.3 AI 응답 파싱/직렬화 오류

**증상**
- `AnalystDecision.reasoning` 누락 응답으로 validation 에러 발생.
- `Object of type bool_ is not JSON serializable` 에러 발생.

**원인**
- structured output 실패에 대한 fallback 부족.
- numpy/decimal 계열 타입 직렬화 방어 미흡.

**조치**
- Analyst 노드 fallback REJECT 경로 추가(`src/agents/analyst.py`).
- 프롬프트에 필수 필드(`decision/confidence/reasoning`) 요구 강화(`src/agents/prompts.py`).
- 공용 직렬화 유틸 추가(`src/common/json_utils.py`) 및 호출부 적용(`src/bot/main.py`, `src/engine/executor.py`).

**결과**
- 해당 유형 에러 재발 로그가 크게 감소.

---

### 2.4 Dashboard `width="stretch"` TypeError

**증상**
- History/Overview 등에서 `TypeError: 'str' object cannot be interpreted as an integer`.

**원인**
- Streamlit 런타임에서 `width="stretch"` 인자 호환성 문제.

**조치**
- 전 페이지 일괄 치환:
  - `st.dataframe(..., use_container_width=True)`
  - `st.plotly_chart(..., use_container_width=True)`

**결과**
- 대시보드 탭 전반에서 동일 TypeError 해소.

---

### 2.5 SELL 경로 상태 표시 불일치 위험

**증상**
- SELL 직후 동일 루프에서 상태가 보유 중으로 남는 순간 불일치 가능.
- 일부 구간에서 Decimal/float 혼합 연산 예외 가능.

**원인**
- 상태 스트림 생성 시점과 포지션 변수 동기화 부족.
- 상태 메시지 계산 로직 타입 정규화 미흡.

**조치**
- SELL 성공 시 즉시 `pos=None` 처리 및 청산 메시지 명시.
- 상태 계산 시 float 정규화 및 0 나눗셈 방어.

**결과**
- Redis status의 `has_position/pnl_pct/reason` 일관성 개선.

---

## 3. 검증

- 테스트:
  - `13 passed` (SELL 경로/전략/지표 회귀)
  - 관련 가드레일/전략 테스트 통과 이력 확인
- 운영 확인:
  - Pod 내 모델명/환경값 확인
  - 에러 패턴 grep으로 주요 에러 부재 확인
  - 대시보드 탭 렌더링 정상 확인

---

## 4. 잔여 리스크

1. `daily_risk_state.trade_count` 의미 혼재(BUY/SELL 분리 미적용 상태)  
2. post-exit 분석 데이터 부재(매도 후 1h/4h/12h/24h 추적 미구현)

- 1번 항목은 `14` 트러블슈팅/핫픽스로 분리 관리한다.  
- 2번 항목은 `15` 계획(매도 후 사후 분석 강화)으로 분리 관리한다.
