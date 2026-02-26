# 18-16. T+12h failed 키워드 오탐 필터 보정 구현 결과

작성일: 2026-02-26  
작성자: Codex (GPT-5)  
관련 계획서: `docs/work-plans/18-16_t12h_failed_keyword_false_positive_filter_plan.md`  
상태: Verified  
완료 범위: Phase 1~2  
선반영/추가 구현: 있음(Phase 2: 운영 해석 가이드 문서화)  
관련 트러블슈팅(있다면): `docs/troubleshooting/18-16_t12h_failed_keyword_false_positive.md`

---

## 1. 개요
- 구현 범위 요약:
  - T+12h 실패 감지 정규식에서 `failed_feeds=0` 오탐 제거
- 목표(요약):
  - 정상 RSS 완료 로그를 실패로 오판하지 않도록 모니터링 신뢰도 개선
- 이번 구현이 해결한 문제(한 줄):
  - `scheduler.*failed` 포괄 매칭으로 발생한 false positive 제거

---

## 2. 구현 내용(핵심 위주)
### 2.1 T+12h 실패 패턴 보정
- 파일/모듈: `scripts/ops/check_24h_monitoring.sh`
- 변경 내용:
  - 기존:
    - `traceback|critical|rss .*failed|daily report .*failed|scheduler.*failed`
  - 변경:
    - `traceback|critical|rss (ingest|summarize) job failed:|daily report .*failed|scheduler.*failed:`
  - 한국어 주석 추가:
    - `failed_feeds=0` 같은 정상 통계 필드명 제외 의도 명시
- 효과/의미:
  - 정상 completion 로그로 인한 T+12h FAIL 오탐 제거
  - 실제 실패 로그(`job failed:`/`failed:`) 탐지 유지

### 2.2 추적성 문서 반영
- 파일/모듈:
  - `docs/troubleshooting/18-16_t12h_failed_keyword_false_positive.md`
  - `docs/PROJECT_CHARTER.md`
- 변경 내용:
  - incident 원인/검증/재발 방지 내용 문서화
  - Charter 문서 참고/변경 이력에 18-16 추가
- 효과/의미:
  - 운영 이슈의 원인-수정-검증 폐루프 추적 가능

---

## 3. 변경 파일 목록
### 3.1 수정
1) `scripts/ops/check_24h_monitoring.sh`  
2) `docs/PROJECT_CHARTER.md`

### 3.2 신규
1) `docs/work-plans/18-16_t12h_failed_keyword_false_positive_filter_plan.md`  
2) `docs/work-result/18-16_t12h_failed_keyword_false_positive_filter_result.md`  
3) `docs/troubleshooting/18-16_t12h_failed_keyword_false_positive.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점: 스크립트 regex를 이전 버전으로 복원

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `bash -n scripts/ops/check_24h_monitoring.sh`
  - `printf '%s\n' '[Scheduler] RSS ingest done. inserted=2, skipped=112, failed_feeds=0' | grep -Eiq "traceback|critical|rss (ingest|summarize) job failed:|daily report .*failed|scheduler.*failed:"; echo $?`
  - `printf '%s\n' '[Scheduler] RSS ingest job failed: timeout while fetching feed' | grep -Eiq "traceback|critical|rss (ingest|summarize) job failed:|daily report .*failed|scheduler.*failed:"; echo $?`
- 결과:
  - 문법 검사 통과
  - 정상 로그 미검출(1)
  - 실패 로그 검출(0)

### 5.2 테스트 검증
- 실행 명령:
  - 없음 (운영 스크립트 변경)
- 결과:
  - 해당 없음

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법(healthcheck, curl, kubectl 등):
  - OCI에서 `scripts/ops/check_24h_monitoring.sh t12h` 실행
- 결과:
  - 운영 환경에서 FAIL/ WARN 수치 재확인 필요(실제 로그 시점 의존)

---

## 6. 배포/운영 확인 체크리스트(필수)
1) `chmod +x /opt/coin-pilot/scripts/ops/check_24h_monitoring.sh`  
2) `/opt/coin-pilot/scripts/ops/check_24h_monitoring.sh t12h`  
3) 필요 시 `/opt/coin-pilot/scripts/ops/check_24h_monitoring.sh all --output /var/log/coinpilot/monitoring-24h.log`

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 실패 탐지를 "포괄 단어 매칭"에서 "실패 문장 포맷 매칭"으로 전환
- 고려했던 대안:
  1) 기존 패턴 유지 + 운영자 수동 해석
  2) 로그 포맷 전체를 JSON 구조화 후 파싱
  3) 현재 regex를 최소 변경으로 보정 (채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1) 1은 오탐 지속으로 자동화 가치 하락
  2) 2는 근본적이나 구현 범위/비용이 큼
  3) 3은 즉시 적용 가능하며 장애 탐지 민감도 유지
- 트레이드오프(단점)와 보완/완화:
  1) 특정 실패 문구 변형 시 미탐 가능성
  2) 장애 패턴 변경 시 정규식 유지보수 필요

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `check_batch_jobs_12h()`의 실패 패턴 의도 설명
  2) `failed_feeds=0` 오탐 방지 이유 명시
- 주석에 포함한 핵심 요소:
  - 의도/왜(why)
  - 실패 문맥 불변조건(`failed:` 기준)
  - 오탐/미탐 트레이드오프

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - T+12h false positive 제거를 위한 regex 보정
  - troubleshooting/result/charter 추적성 문서화
- 변경/추가된 부분(왜 바뀌었는지):
  - 없음
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - T+12h 실패 탐지 오탐 원인을 제거하는 패치 적용 완료
- 후속 작업(다음 plan 번호로 넘길 것):
  1) 운영 로그 샘플 fixture 기반 스크립트 회귀 테스트 도입 검토
  2) 모니터링 스크립트 strict/lenient 모드 분리 검토

---

## 11. 운영 해석 가이드 (Phase 2)
### 11.1 T+ 용어 의미
- `t0`: 즉시 상태 점검(서비스 Up/치명 로그)
- `t1h`: 최근 1시간 관점에서 Prometheus target up 상태 + 알림 라우팅 수동 점검 안내
- `t6h`: 최근 6시간 Entry/AI/Risk 이벤트 흐름 연속성 점검
- `t12h`: 최근 12시간 배치 실패 누적 점검
- `t24h`: 최근 24시간 백업 파일/cron 상태 점검
- `all`: 위 phase를 순차 실행

### 11.2 PASS/WARN/FAIL 해석
- `PASS`: 자동 기준 충족
- `WARN`: 자동 확정이 어려워 운영자 수동 확인 필요(예: Grafana/Discord UI 확인)
- `FAIL`: 기준 위반 감지(실제 장애 또는 오탐 가능)

### 11.3 오탐(False Positive) 정의
- 의미:
  - 실제 장애가 없는데 규칙이 실패로 판정한 상태
- 본 이슈 사례:
  - `failed_feeds=0`(정상 통계 필드) 문자열이 기존 패턴(`scheduler.*failed`)에 매칭되어 FAIL 발생
- 보정 후 기준:
  - `...job failed:` 또는 `...failed:`처럼 실패 문맥이 있는 로그만 FAIL로 판정

### 11.4 실행 시 확인되는 항목 요약
- `t0`:
  - Compose 8개 서비스 상태
  - bot 최근 10분 치명 오류 키워드
- `t1h`:
  - `up{job="coinpilot-core"}` 값 확인
  - Grafana Alert rules / Contact point 테스트 수동 확인 안내
- `t6h`:
  - bot 치명 키워드
  - Entry/AI/Risk 이벤트 발생 건수
- `t12h`:
  - bot 배치 실패 키워드
  - RSS ingest 완료 로그
  - n8n 에러 키워드
- `t24h`:
  - Postgres/Redis/n8n 백업 최신성
  - cron active 상태

---

## 12. References
- `docs/work-plans/18-16_t12h_failed_keyword_false_positive_filter_plan.md`
- `docs/troubleshooting/18-16_t12h_failed_keyword_false_positive.md`
- `scripts/ops/check_24h_monitoring.sh`
