# 29-01. BULL 레짐 Rule Funnel 관측성 강화 + 주기 점검 자동화 계획

**작성일**: 2026-03-07  
**작성자**: Codex  
**상태**: Approved  
**관련 계획 문서**: `docs/work-plans/29_regime_transition_strategy_evaluation_and_hotfix_plan.md`, `docs/work-plans/30_strategy_feedback_automation_spec_first_plan.md`, `docs/work-plans/31_oci_ops_monitoring_cron_automation_and_gap_hardening_plan.md`  
**승인 정보**: 승인 / 2026-03-08 / 사용자 승인 후 구현 착수

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 최근 72시간 기준 레짐 노출은 BULL이 우세하나, AI decision 호출은 SIDEWAYS가 더 많음.
  - 실제 집계:
    - `agent_decisions`: SIDEWAYS 58건, BULL 27건
    - `regime_history`(1h 포인트 합): BULL 235, SIDEWAYS 155
    - 노출 대비 AI 호출률: BULL 0.115, SIDEWAYS 0.374(약 3.25배)
  - `Entry Signal Detected` 로그는 72h 기준 9건 확인됨.
- 왜 즉시 대응이 필요한지:
  - 현재 DB에는 "Rule Engine 통과 이벤트"가 없어(BULL/SIDEWAYS/BEAR별) 병목 구간을 정확히 분해할 수 없다.
  - 29번의 핫픽스 의사결정 신뢰도를 높이려면, Rule -> Risk -> AI 각 단계의 레짐별 퍼널 계측이 필요하다.

## 1. 문제 요약
- 증상:
  - "BULL인데 AI decision이 적다"는 관측이 실제 데이터로 확인됨.
  - 그러나 해당 감소가 Rule 통과 부족인지, Risk/AI guardrail 단계 차단인지 분리 진단이 어렵다.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 전략 튜닝 병목 지점 식별 정확도 저하
  - 리스크: 잘못된 원인 추정으로 파라미터를 오조정할 위험
  - 데이터: DB에는 AI 결과는 있으나 Rule pass 이력 부재
  - 비용: 수동 조사 반복으로 의사결정 지연
- 재현 조건:
  - 레짐 전환이 잦거나 BULL 추세 지속 중 진입 기회가 적다고 체감되는 구간

## 2. 원인 분석
- 가설:
  1) BULL 진입 조건(`crossover` + `volume_ratio >= 1.0`)이 상대적으로 엄격해 Rule pass가 적다.
  2) Rule pass는 발생하지만 Risk/Guardrail/AI에서 추가 차단된다.
  3) 계측 부재로 인해 실제 병목이 구분되지 않는다.
- 조사 과정:
  - 코드/스키마 확인:
    - Rule 통과 시 로그만 출력: `src/bot/main.py` (`Entry Signal Detected`)
    - DB 저장은 AI decision 결과 중심: `agent_decisions`
    - Rule pass 전용 테이블/메트릭 부재
  - 기존 29/30/31 계획 확인:
    - 29: 백테스트/핫픽스 의사결정 중심(주기 자동 실행/자동 수정 없음)
    - 30: 전략 피드백 자동화 Spec(승인형) 계획(미구현)
    - 31: 모니터링 스크립트 cron 자동화 계획(미구현)
- Root cause:
  - "전략 퍼널 관측성(레짐별 Rule pass 포함)"과 "주기 실행 자동화"가 분리되어 있고, 아직 구현되지 않음.

## 3. 목표 / 비목표
### 3.1 목표
1. 레짐별 Rule funnel(`rule_pass`, `risk_reject`, `ai_prefilter_reject`, `ai_guardrail_block`, `ai_confirm`, `ai_reject`)을 정량 계측 가능하게 만든다.
2. 7일(주 1회) 고정 주기의 자동 점검 리포트를 생성해 이상징후를 조기 탐지한다.
3. 자동 수정은 하지 않고, "자동 제안 + 수동 승인" 기준을 명확히 한다.

### 3.2 비목표
1. 본 작업에서 무인 자동 전략 수정/배포는 수행하지 않는다.
2. 본 작업에서 FE/BE 이관(22/23)은 다루지 않는다.

## 4. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **DB 퍼널 이벤트 계측 + cron 기반 주기 리포트 + 승인형 제안 워크플로우**

- 고려 대안:
  1) 로그 grep 기반 수동 점검 지속
  2) Rule funnel DB 계측 없이 AI decision만으로 간접 판단
  3) DB 계측 + 주기 리포트 자동화 + 승인형 제안(채택)

- 대안 비교:
  1) 수동 점검:
    - 장점: 구현 없음
    - 단점: 재현성/추적성/정확도 낮음
  2) 간접 판단:
    - 장점: 기존 데이터 재사용
    - 단점: Rule 단계 병목을 분리하지 못함
  3) 채택안:
    - 장점: 원인 분해 정확도↑, 29 핫픽스 판단 품질↑, 운영 반복성↑
    - 단점: 이벤트 스키마/스크립트/운영 크론 구성 비용 필요

## 5. 구현/수정 내용 (예정)
### Phase A. 레짐별 Rule Funnel 계측 추가
1. 이벤트 스키마 정의(신규 테이블 또는 기존 감사 테이블 확장):
   - 필수 컬럼: `created_at`, `symbol`, `regime`, `stage`, `result`, `reason`
2. bot 루프 단계별 기록 포인트 추가:
   - Rule pass, Risk reject, AI prefilter reject, AI guardrail block, AI final decision
3. 운영 리포트 스크립트 추가:
   - `scripts/ops/rule_funnel_regime_report.sh <hours>`

### Phase B. 주기 점검(7일 고정) 자동화 설계
1. 주기 정책(고정):
   - 매주 1회(7일): 주간 비교 + 전략 제안 초안 생성
2. 기존 주간 리포트 경로와의 통합:
   - `weekly_exit_report_job` 경로를 확장해 전략 제안 섹션을 함께 전송
   - 별도 신규 리포트를 추가 생성하지 않고 기존 Discord 주간 리포트 payload를 증분 확장
3. 실행 방식:
   - 1안 권장: 기존 봇 스케줄러 주간 잡 + cron 보조 점검(`31`과 결합)
   - 2안 대체: systemd timer
   - 3안 대체: n8n workflow 스케줄
4. 산출물:
   - `/var/log/coinpilot/ops/rule-funnel-*.log`
   - 요약 CSV/JSON(주간 비교용)

### Phase C. 자동 제안/자동 수정 정책 분리
1. 자동 제안:
   - 이상징후(예: BULL 노출 대비 Rule pass 급감) 탐지 시 파라미터 후보 제시
2. 자동 수정:
   - 기본 금지(승인 전 미적용)
   - 단, 30번 계획의 Tier-A/Tier-B 정책 및 가드레일(주간 cap/Shadow/보류/롤백/재현성/Discord 승인 포맷) 충족 시에만 제한적 허용 검토

## 6. 검증 기준
- 재현 케이스에서 해결 확인:
  1) 레짐별 Rule pass 건수를 DB 쿼리로 직접 조회 가능해야 함
  2) 7일 리포트가 자동 생성되어야 함
- 회귀 테스트:
  - 기존 매매 흐름/주문 로직 결과가 변하지 않아야 함(계측은 부수효과만)
- 운영 체크:
  - 퍼널 단계별 누락률(UNKNOWN/NULL regime) 1% 미만
  - 크론 실행 실패율 0%(최근 7일)

## 7. 롤백
- 코드 롤백:
  - 이벤트 기록 훅 제거, 신규 리포트 스크립트 비활성화
- 데이터/스키마 롤백:
  - 신규 테이블은 유지(읽기 중단) 또는 별도 drop 마이그레이션 수행

## 8. 문서 반영
- work-plan/work-result 업데이트:
  - Plan: 본 문서
  - Result(구현 후): `docs/work-result/29-01_bull_regime_rule_funnel_observability_and_review_automation_result.md`
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 정책(자동 수정 금지/승인형 제안)을 규칙으로 확정할 경우 Charter changelog 반영

## 9. 후속 조치
1. `29`의 전략 평가 결론과 `29-01` 퍼널 지표를 결합해 핫픽스 판단 정확도 개선
2. `31`의 cron 자동화 범위에 `rule_funnel_regime_report`를 포함
3. `30`의 승인형 자동화 스펙과 연동해 "자동 수정 금지, 자동 제안 허용" 정책 고정

## 10. 실행 검증 명령(초안)
1. 레짐별 AI decision:
   - `docker exec -u postgres coinpilot-db psql -d coinpilot -c "SELECT COALESCE(regime,'UNKNOWN'), COUNT(*) FROM agent_decisions WHERE created_at >= now() - interval '72 hours' GROUP BY 1;"`
2. 레짐 노출량:
   - `docker exec -u postgres coinpilot-db psql -d coinpilot -c "SELECT coin_symbol, regime, COUNT(*) FROM regime_history WHERE detected_at >= now() - interval '72 hours' GROUP BY 1,2;"`
3. Rule pass 로그 총량:
   - `docker compose --env-file /opt/coin-pilot/deploy/cloud/oci/.env -f /opt/coin-pilot/deploy/cloud/oci/docker-compose.prod.yml logs --since=72h bot | grep -c 'Entry Signal Detected'`

## 11. 계획 변경 이력
- 2026-03-07: 사용자 요청(29-01 추가, 29 내 주기 점검/자동 수정 가능성 확인)에 따라 신규 계획 생성(Approval Pending).
- 2026-03-07: 사용자 요청에 따라 주기를 `3~7일`에서 `7일 고정`으로 명확화하고, 기존 Weekly Exit Report 경로 확장(증분 통합) 방침을 추가.
- 2026-03-07: 사용자 요청에 따라 30번의 운영 가드레일 6종을 29-01 자동 수정 검토 조건으로 연결.
- 2026-03-08: 사용자 요청에 따라 방금 추가했던 "브랜치 파서 우선" 축소 범위를 제거하고, 원래 승인된 범위(DB 퍼널 계측 + 주간 리포트 증분 통합 + 자동 수정 금지)로 계획을 확정했다.
- 2026-03-08: 사용자 승인 후 상태를 `Approved`로 변경하고 구현 착수를 시작했다.
- 2026-03-09: Weekly Exit Report Discord 포맷 보정 과정에서, 별도 workflow의 기존 운영 형식(`jsonBody = {{ { \"embeds\": [...] } }}`)을 유지하고 `Rule Funnel` 관련 내용만 embed `fields`로 증분 추가하는 것으로 조정했다.
