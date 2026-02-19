# 14. Trade Count 분리 핫픽스 트러블슈팅

**작성일**: 2026-02-19  
**작성자**: Codex (GPT-5)  
**상태**: 진행 예정 (Planned)  
**관련 계획 문서**: `docs/work-plans/14_post_exit_trade_count_split_hotfix.md`

---

## 0. 계획 수립 트리거 (Why 14 Started)

`14`는 신규 기능 확장 과제가 아니라, 운영 모니터링 중 발견된 지표 불일치/리스크 해석 오류를 바로잡기 위한 트러블슈팅 핫픽스로 시작되었다.

주요 트리거:
1. Overview에서 BUY 체결/보유가 확인되는데 Risk 탭 `Trade Count`가 0으로 표시됨  
2. `daily_risk_state.trade_count`가 SELL 경로 중심으로 증가해 실제 "당일 활동량"과 의미가 어긋남  
3. 같은 필드를 리스크 제한과 대시보드 표시에 동시에 사용해 운영 해석 충돌이 발생함

따라서 `14`의 목적은 기능 추가가 아니라, **카운트 정의 분리(buy/sell)로 리스크 정책과 관측 지표의 의미를 일치**시키는 것이다.

---

## 1. 문제 요약

운영 중 다음 불일치가 확인됨:
- Overview에서 보유 포지션(= BUY 체결) 존재
- Risk 탭 `Trade Count`는 `0`

이는 리스크 모니터링 신뢰성을 저하시킬 뿐 아니라, 일일 거래 제한 정책 해석에도 혼선을 만든다.

---

## 2. 원인 분석

1. Risk 탭은 `daily_risk_state.trade_count`를 표시  
2. `trade_count` 증가는 현재 SELL 경로에서만 발생  
3. BUY 성공 시 `daily_risk_state` 카운트 갱신 호출이 없음

결과적으로 `trade_count`가 "총 체결 수"가 아니라 "사실상 청산 수"처럼 동작한다.

---

## 3. 영향 범위

1. 대시보드: 운영자 관점 거래 활동량 왜곡  
2. 리스크 로직: 일일 거래 제한(`MAX_DAILY_TRADES`)이 BUY 기준으로 정확히 작동하지 않을 가능성  
3. 리포트/분석: 거래 건수 해석 불일치

---

## 4. 대응 전략

`trade_count` 단일 지표를 분리:

- `buy_count`: 리스크 제한 기준
- `sell_count`: 청산 추적 지표
- `trade_count`: 하위호환 총 체결 지표(또는 점진적 deprecated)

정책:
- 리스크 제한 체크는 `buy_count` 기준으로 전환
- Risk 탭은 `BUY/SELL/Total`을 동시에 노출

---

## 5. 구현 계획 요약

상세 구현은 계획 문서 기준:
- `docs/work-plans/14_post_exit_trade_count_split_hotfix.md`

핵심 작업:
1. DB 스키마 확장 (`buy_count`, `sell_count`)  
2. RiskManager 업데이트 (`update_after_trade(..., side)`, 제한 기준 전환)  
3. Bot 호출 경로 보정 (BUY 성공 시 카운트 반영)  
4. Risk 탭 UI 개선

---

## 6. 검증 기준

1. BUY 1회 후 `buy_count`/`trade_count` 증가  
2. SELL 1회 후 `sell_count`/`trade_count` 증가  
3. Risk 탭 값과 DB 값 일치  
4. 일일 거래 제한이 BUY 횟수 기준으로 동작

---

## 7. 롤백

1. 코드 롤백: Bot/Dashboard 롤아웃 undo  
2. DB 롤백: 신규 컬럼 제거(긴급 시에만)

---

## 8. 후속 연계

본 핫픽스 완료 후, `15`번(Post-exit 사후 분석 강화)에서
- exit 품질 분석
- 리포트 고도화
- 파라미터 튜닝 제안
으로 확장한다.
