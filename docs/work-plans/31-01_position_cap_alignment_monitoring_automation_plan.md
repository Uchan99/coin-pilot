# 31-01. 주문 사이징/리스크 캡 정렬 invariant 모니터링 자동화 계획

작성일: 2026-03-11  
작성자: Codex  
상태: Deferred (Not Needed for Cron)  
상위 계획 문서: [31_oci_ops_monitoring_cron_automation_and_gap_hardening_plan.md](/home/syt07203/workspace/coin-pilot/docs/work-plans/31_oci_ops_monitoring_cron_automation_and_gap_hardening_plan.md)  
관련 선행 문서: [21-10_position_sizing_and_risk_cap_alignment_plan.md](/home/syt07203/workspace/coin-pilot/docs/work-plans/21-10_position_sizing_and_risk_cap_alignment_plan.md), [21-10_position_sizing_and_risk_cap_alignment_result.md](/home/syt07203/workspace/coin-pilot/docs/work-result/21-10_position_sizing_and_risk_cap_alignment_result.md), [31_oci_ops_monitoring_cron_automation_and_gap_hardening_result.md](/home/syt07203/workspace/coin-pilot/docs/work-result/31_oci_ops_monitoring_cron_automation_and_gap_hardening_result.md)  
관련 트러블슈팅 문서: (필요 시 생성)

---

## 0. 트리거
- `21-10`에서 주문 목표 계산과 RiskManager 하드 캡 검증을 동일 정책으로 정렬했다.
- OCI 재배포 직후 동일 `max_per_order` mismatch 패턴은 재현되지 않았지만, 현재는 운영 표본이 적어 "수정이 유지되는지"를 계속 감시할 필요가 있다.
- 사용자 요청:
  - 해당 모니터링도 cron 자동화에 포함 가능한지 검토
  - 앞으로 모니터링 명령이 안정적으로 동작하면, "모니터링만 남은 invariant"는 cron 편입을 우선 고려하는 운영 원칙을 세우고 싶음

## 0-1. 검토 결론
- 본 하위 계획은 **cron 자동화 구현으로 진행하지 않는다.**
- 이유:
  1. `21-10`은 외부 의존성/시간 경과형 이슈가 아니라 특정 설계 mismatch 수정의 post-deploy 검증에 가깝다.
  2. `21-10` OCI 반영 직후 동일 오류 패턴이 재현되지 않았고, 현재는 운영 표본 추가 확인만 남은 상태다.
  3. 상시 cron에 넣어도 운영자가 즉시 조치할 수 있는 액션이 제한적이고, 표본이 없을 때 `INFO`만 반복될 가능성이 높다.
- 따라서 본 이슈는 `31`의 상시 모니터링 체계로 승격하지 않고, `21-10` 결과 문서에 남긴 수동 재확인 쿼리로 24~72시간 추가 확인 후 종료한다.

## 1. 해결할 문제 정의
- 증상:
  - `21-10` 수정 후에도 향후 코드 경로 변경이나 env/설정 변경으로 주문 목표(`target_invest_amount`)가 동적 하드 캡(`dynamic_max_order_amount`)을 다시 초과할 수 있다.
- 영향:
  - 같은 설계 mismatch가 재발해도 사람이 수동 쿼리를 돌리기 전까지 놓칠 수 있다.
  - Rule Funnel의 `max_per_order` 병목 해석이 다시 오염될 수 있다.
- 재현 조건:
  - 최근 24h `BUY` row에서 `target_amount > dynamic_cap`
  - 또는 post-fix 구간에서 `risk_reject(max_per_order)`가 재발

## 2. 목표
1. `21-10` 정렬 결과를 운영 invariant로 정의한다.
2. 해당 invariant가 상시 cron 대상인지, 배포 후 수동 검증 대상으로 남기는 것이 맞는지 판단한다.
3. 향후 "모니터링만 남은 작업"은 자동으로 cron에 넣지 않고, 상시 감시 가치가 있는지 먼저 판정하는 운영 원칙을 문서화한다.

## 3. 운영 invariant 정의

### Invariant A. post-fix `max_per_order` reject
- 최근 24h `rule_funnel_events`
- 조건:
  - `stage='risk_reject'`
  - `reason_code='max_per_order'`
- 기대값:
  - 운영 표본이 있어도 구조적 mismatch로 인한 reject는 `0`

### Invariant B. BUY sizing trace 정합성
- 최근 24h `trading_history side='BUY'`
- 조건:
  - `signal_info.target_invest_amount > signal_info.dynamic_max_order_amount`
- 기대값:
  - `0`

### 판정 정책
- `BUY = 0건`, `max_per_order = 0건`
  - `INFO`
  - 표본 부족이지만 이상 징후는 없음
- `BUY >= 1건`, 위반 `0건`
  - `PASS`
- `max_per_order >= 1건` 또는 `target > cap >= 1건`
  - `FAIL`

## 4. 검토 범위

### Phase A. invariant 성격 분류
- `21-10`이 시간 경과형/외부 의존형 운영 이슈인지 판단
- 결론: 해당 없음, 배포 후 정합성 검증 성격이 더 강함

### Phase B. 수동 재확인 쿼리만 유지
- `21-10` 결과 문서에 남긴 쿼리로 24~72시간 범위 재확인
- cron 편입 없이 post-deploy verification 성격으로 관리

### Phase C. 운영 원칙 문서화
- "모니터링만 남은 작업"이라도 아래 조건을 만족할 때만 cron 편입 검토:
  1. 시간이 지나며 상태가 변함
  2. 외부 의존성 영향이 큼
  3. silent failure 가능성이 큼
  4. FAIL 시 운영자가 실제 조치 가능
  5. false positive가 낮음

## 5. 설계 선택 이유

### 채택 방식
- 본 invariant는 cron 자동화에 넣지 않고, 배포 후 수동 검증으로 유지한다.

### 고려한 대안
1. 별도 스크립트 `check_position_cap_alignment.sh` 생성
2. 기존 `check_24h_monitoring.sh`에 통합
3. DB trigger 또는 SQL materialized view 기반 감시

### 대안 비교
1. 별도 스크립트
- 장점:
  - 책임 분리가 명확하다.
- 단점:
  - cron job/로그 파일/운영 표준이 또 늘어난다.

2. 기존 모니터링 스크립트 통합
- 장점:
  - 이미 운영 중인 `31` 자동화 체계를 그대로 재사용할 수 있다.
  - 로그/실패 기준/cron 운영 경로가 한 곳으로 모인다.
- 단점:
  - 스크립트가 조금 더 길어진다.

3. DB trigger/view 기반
- 장점:
  - 실시간 감시에 가깝다.
- 단점:
  - 현재 운영 구조 대비 과하다.
  - DB 종속성이 커진다.

## 6. 정량 검토 기준
- 성공 기준:
  1. post-fix 운영 구간에서 `max_per_order` 신규 reject가 없을 것
  2. `BUY` 표본이 존재할 때 `target_amount > dynamic_cap` 위반이 `0건`이어야 할 것
  3. 위 조건이 충족되면 cron 편입 없이 수동 검증으로 종료할 것
- 실패 기준:
  1. post-fix 구간에서 동일 mismatch 패턴이 재발
  2. 운영 표본이 쌓여도 invariant가 반복적으로 깨짐

## 7. How to verify
OCI 수동 재확인:
```bash
docker inspect -f '{{.State.StartedAt}}' coinpilot-bot
docker exec -u postgres coinpilot-db psql -d coinpilot -c "
SELECT created_at, symbol, reason_code, reason
FROM rule_funnel_events
WHERE created_at >= TIMESTAMPTZ '<bot started_at>'
  AND stage = 'risk_reject'
  AND reason_code = 'max_per_order'
ORDER BY created_at DESC;
"
```

기대 체크:
- post-fix 구간 신규 `max_per_order` reject가 없으면 정상
- BUY 표본이 쌓이면 `target_amount <= dynamic_cap`를 추가 확인

## 8. 리스크 / 가정 / 미확정 사항
- 리스크:
  - 현재 post-fix 표본이 적어 단기적으로는 "정상"과 "표본 없음"이 같이 나타날 수 있다.
  - 과거 row와 post-fix row를 혼동하지 않도록 최근 24h 기준으로만 판정해야 한다.
- 가정:
  - `signal_info.dynamic_max_order_amount`와 `signal_info.target_invest_amount`가 BUY 경로에 정상 저장된다.
- 미확정:
  - 향후 유사 invariant가 누적될 때 별도 runbook 섹션으로 묶을지 여부

## 9. 변경 이력
- 2026-03-11: 사용자 요청으로 신규 하위 계획 생성. 초기 상태는 `Approval Pending`.
- 2026-03-12: cron 자동화 필요성을 재검토한 결과, `21-10`은 상시 감시보다 배포 후 수동 검증 성격이 더 강하다고 판단해 `Deferred (Not Needed for Cron)`로 전환.
