# 18-16. T+12h failed 키워드 오탐 필터 보정 계획

**작성일**: 2026-02-26  
**작성자**: Codex (GPT-5)  
**상태**: Approved  
**관련 계획 문서**: `docs/work-plans/18-14_oci_24h_monitoring_script_automation_plan.md`  
**승인 정보**: 사용자 채팅 승인 / 2026-02-26 / "진행해줘."

---

## 0. 트리거(Why started)
- 운영 점검 자동화(`scripts/ops/check_24h_monitoring.sh`) 실행 시 T+12h 단계에서 반복적으로 FAIL이 발생했다.
- 실제 로그 확인 결과, 장애가 아닌 `failed_feeds=0` 정상 문구가 실패 키워드로 오탐지되어 운영 신뢰도를 저하시켰다.

## 1. 문제 요약
- 증상:
  - `check_24h_monitoring.sh t12h`가 "bot 배치 로그에서 실패 키워드 감지"로 FAIL 반환
  - 실제 bot 로그에는 traceback/critical/실패 stack trace 없이 `RSS ingest done ... failed_feeds=0`만 존재
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 모니터링 자동화 신호 신뢰도 저하
  - 리스크: 정상 상태를 장애로 오판하여 불필요한 대응 발생
  - 데이터: 없음
  - 비용: 운영자 점검 시간/피로 증가
- 재현 조건:
  - bot 로그에 `failed_feeds=0`가 포함된 시점에 T+12h 검사 실행

## 2. 원인 분석
- 가설:
  - 실패 키워드 패턴 `scheduler.*failed`가 `failed_feeds=0`를 함께 매칭한다.
- 조사 과정:
  - T+12h 점검 패턴 확인: `traceback|critical|rss .*failed|daily report .*failed|scheduler.*failed`
  - 실제 매칭 라인 확인: `[Scheduler] RSS ingest done. inserted=..., failed_feeds=0`
- Root cause:
  - "실패 문맥"과 "필드명 문자열(failed_feeds)"을 정규식으로 분리하지 않아 false positive 발생

## 3. 대응 전략
- 단기 핫픽스:
  - T+12h 정규식에서 포괄 패턴(`scheduler.*failed`) 제거
  - 실제 실패 로그 포맷(`... job failed:`/`scheduler...failed:`)만 엄격 매칭
- 근본 해결:
  - 실패 탐지 패턴을 "메시지 semantics 기반"으로 좁혀 오탐 방지
  - 결과 문서/트러블슈팅/Charter에 근거와 변경 이력 명시
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 실패 키워드는 stack trace/critical/명시적 failed 문구로 제한
  - 정상 completion 로그(`failed_feeds=0`)는 실패로 해석하지 않음

## 4. 구현/수정 내용
- 변경 파일:
  - `scripts/ops/check_24h_monitoring.sh`
  - `docs/troubleshooting/18-16_t12h_failed_keyword_false_positive.md`
  - `docs/work-result/18-16_t12h_failed_keyword_false_positive_filter_result.md`
  - `docs/PROJECT_CHARTER.md`
- DB 변경(있다면):
  - 없음
- 주의점:
  - 기존 장애 탐지 민감도가 과도하게 낮아지지 않도록 실패 패턴은 `failed:` 문맥을 유지

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - `[Scheduler] RSS ingest done ... failed_feeds=0` 로그가 있어도 T+12h FAIL이 발생하지 않아야 함
- 회귀 테스트:
  - `traceback`, `critical`, `rss ingest job failed:` 등 실제 실패 문구는 여전히 FAIL로 감지되어야 함
- 운영 체크:
  - `scripts/ops/check_24h_monitoring.sh t12h` 재실행 시 SUMMARY FAIL=0 기대

## 6. 롤백
- 코드 롤백:
  - `scripts/ops/check_24h_monitoring.sh`에서 기존 패턴으로 revert
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 18-16 plan/result 및 troubleshooting 신규 생성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 필요 (8.5 문서 참고/8.9 변경 이력에 18-16 반영)

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) 점검 스크립트에 `--strict`/`--lenient` 모드 분리 검토
  2) regex 기반 탐지에 샘플 로그 테스트 케이스(문자열 fixture) 도입 검토

## 9. 아키텍처 선택/대안/트레이드오프
- 최종 선택:
  - 단일 정규식 보정(실패 포맷 고정 + 포괄 매칭 제거)
- 대안:
  1) 현재 포괄 정규식 유지 + 운영자 수동 해석
  2) JSON 구조 로그로 전환 후 키 기반 판단
  3) 정규식 보정으로 실패 문맥만 엄격 매칭 (채택)
- 채택 이유:
  - 1은 오탐을 방치하여 자동화 목적을 훼손
  - 2는 근본적으로 가장 좋지만 로그 포맷/코드 전반 변경이 필요해 범위 과대
  - 3은 즉시 적용 가능하며 현재 운영 리스크를 최소 변경으로 해소

## 10. 계획 변경 이력
- 2026-02-26 (초기): T+12h false positive 제거를 위한 정규식 보정 범위로 승인
