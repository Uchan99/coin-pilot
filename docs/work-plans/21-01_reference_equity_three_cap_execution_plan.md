# 21-01. 기준자산 고정 + 3중 캡 주문 체계 전환 계획

**작성일**: 2026-02-26  
**작성자**: Codex (GPT-5)  
**상태**: Approved  
**상위 계획 문서**: `docs/work-plans/21_live_trading_transition_1m_krw_plan.md`  
**관련 트러블슈팅 문서**: (없음, 필요 시 생성)  
**승인 정보**: 사용자 승인(2026-02-26, 채팅 확인)  

---

## 0. 트리거(Why started)
- 사용자 요구:
  - 실거래 전환 시 예치금 100만원 기준으로 운용
  - 심볼당 최대 20% 수준의 주문을 원함
  - 필요 시 5개 심볼 합산 100% 홀딩도 허용
  - 잔고 부족 주문(오더 reject) 발생은 피하고 싶음
- 현재 구조:
  - 주문 기준이 `현재 현금 잔고 * max_per_order` 기반이라, 의도한 포지션 설계(20% * 5심볼)와 괴리가 있음.

## 1. 문제 요약
- 증상:
  - 현재 주문 사이징이 잔고 기반이라 누적 진입 시 주문액이 점점 줄어듦.
  - “심볼당 20%” 의도가 실제 체결에서는 “초기 몇만원 단위”로 축소될 수 있음.
- 영향 범위:
  - 전략 일관성 저하, 실거래 기대 동작과 불일치, 운영자 신뢰 저하
- 재현 조건:
  - 예치금 100만원, `max_per_order=0.2` 가정 후 5심볼 순차 진입 시

## 2. 원인 분석
- 가설:
  - 주문 목표값 산정 기준이 “고정 기준자산(reference)”이 아니라 “현재 잔고”이기 때문
- 조사 과정:
  - `src/bot/main.py` 주문 금액 계산부 확인
  - `src/engine/risk_manager.py` 단일 주문/총 노출 검증 기준 확인
- Root cause:
  - 주문 타깃과 리스크 한도 기준이 “운영 의도(고정 기준자산)”와 분리되어 있음

## 3. 대응 전략

### 3.1 최종 선택(채택)
- **기준자산 고정 + 3중 캡(min) 방식**
  - `target_cap = reference_equity * max_per_order * regime_ratio`
  - `cash_cap = available_cash * (1 - fee_buffer)`
  - `exposure_cap = reference_equity * MAX_TOTAL_EXPOSURE - current_exposure`
  - `order_amount = min(target_cap, cash_cap, exposure_cap)`

### 3.2 대안 검토
1. 실시간 총자산 기준(매 순간 equity 연동)
- 장점: 이론적으로 시장가치 반영
- 단점: 평가이익 구간에서 목표 주문액이 커져 현금 부족 충돌 가능

2. 단순 잔고 기준(현 구조 유지)
- 장점: 구현 단순
- 단점: 심볼당 고정 비중 의도와 괴리, 누적 진입 시 과도 축소

3. 목표 비중 리밸런싱 엔진(정교 포트폴리오)
- 장점: 가장 정밀한 자산 배분
- 단점: 구현 복잡도 높고 이번 전환 범위 초과

4. **기준자산 고정 + 3중 캡 (채택)**
- 장점: 사용자 의도 충족 + 잔고 부족 방지 + 최소 변경
- 단점: 기준자산 갱신 정책(예: 일 1회) 의사결정 필요

### 3.3 안전장치
- 주문 직전 `order_amount <= 0` 이면 SKIP 처리
- `fee_buffer` 도입으로 수수료/슬리피지 완충
- 기존 리스크 규칙(일일손실/쿨다운/동시포지션) 유지

## 4. 구현/수정 내용 (예정)
- 변경 파일:
  - `src/bot/main.py`
  - `src/engine/risk_manager.py`
  - `src/config/strategy.py` 또는 `config/strategy_v3.yaml` (운영 파라미터)
- 설정 제안값(100만원 기준):
  - `max_per_order=0.20`
  - `MAX_TOTAL_EXPOSURE=1.00`
  - `MAX_CONCURRENT_POSITIONS=5`
  - `ALLOW_SAME_COIN_DUPLICATE=false`
  - `regime position_size_ratio`: BULL 1.0 / SIDEWAYS 0.9 / BEAR 0.7
- 주의점:
  - Paper/Live 공용 로직으로 설계해 전환 시 코드 재수정 최소화

## 5. 검증 기준
- 재현 케이스:
  - 100만원 기준, 5심볼 연속 진입 시 잔고 부족 없이 주문/스킵 논리 일관성 확인
- 회귀 테스트:
  - 기존 리스크 거부 경로(`Risk Rejected`)와 AI 경로(`PreFilter/Guardrail`) 동작 유지
- 운영 체크:
  - 주문 실패 로그 중 잔고 부족 문구 비율 0에 수렴
  - 대시보드/Discord 시그널 정상

## 6. 롤백
- 코드 롤백:
  - `main`/`risk_manager` 변경 커밋 revert
- 설정 롤백:
  - `max_per_order`, `MAX_TOTAL_EXPOSURE`, `MAX_CONCURRENT_POSITIONS` 이전값 복원

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획 승인 후 구현, 이후 결과 문서 생성 예정
- PROJECT_CHARTER.md 업데이트 필요 여부:
  - 필요(운영 정책/주문 사이징 기준 변경이므로 changelog 반영 예정)

## 8. 후속 조치
- 기준자산(reference_equity) 갱신 정책 확정
  - 옵션 A: 시작 시 1회 고정
  - 옵션 B: 일 단위 고정(권장, **본 구현 채택**)
  - 옵션 C: 수동 리셋 커맨드 제공

## 9. 변경 이력
- 2026-02-26: 초안 작성 (Approval Pending)
- 2026-02-26: 사용자 승인 반영, 구현 단계 착수
- 2026-02-26: 기준자산 갱신 정책 옵션 B(UTC 일 단위 고정) 확정
