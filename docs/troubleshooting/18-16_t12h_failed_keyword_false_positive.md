# 18-16. T+12h failed 키워드 오탐 트러블슈팅 / 핫픽스

작성일: 2026-02-26  
상태: Fixed  
우선순위: P1  
관련 문서:
- Plan: `docs/work-plans/18-16_t12h_failed_keyword_false_positive_filter_plan.md`
- Result: `docs/work-result/18-16_t12h_failed_keyword_false_positive_filter_result.md`
- Charter update 필요: YES

---

## 1. 트리거(왜 시작했나)
- 모니터링 자동화 스크립트의 T+12h 단계가 반복적으로 FAIL을 반환했다.
- 사용자 제공 로그에서 실제 장애 징후 없이 `failed_feeds=0` 라인만 탐지되는 것이 확인됐다.

---

## 2. 증상/영향
- 증상:
  - `scripts/ops/check_24h_monitoring.sh t12h` 결과 `FAIL: 1`
  - 실패 사유: "bot 배치 로그에서 실패 키워드 감지"
- 영향(리스크/데이터/비용/운영):
  - 운영 오탐 증가로 경보 피로(alert fatigue) 유발
  - 실제 장애와 비장애의 구분 신뢰도 하락
- 발생 조건/재현 조건:
  - bot 로그에 `failed_feeds=0`가 포함된 시점

---

## 3. 재현/관측 정보
- 재현 절차:
  1) `scripts/ops/check_24h_monitoring.sh t12h` 실행
  2) bot 로그에서 매칭 라인 확인
- 입력/데이터:
  - `[Scheduler] RSS ingest done. inserted=2, skipped=112, failed_feeds=0`
- 핵심 로그/에러 메시지:
  - T+12h 단계에서 "실패 키워드 감지" 출력
- 관련 지표/대시보드(있다면):
  - 없음

---

## 4. 원인 분석
- 가설 목록:
  1) `scheduler.*failed` 정규식이 `failed_feeds=0`를 포괄 매칭
  2) 실제 `rss ingest job failed:` 로그 존재
  3) traceback/critical 존재
- 조사 과정(무엇을 확인했는지):
  - T+12h 실패 패턴 확인
  - 실제 로그 매칭 결과 확인
  - 샘플 문자열로 regex 매칭 테스트 수행
- Root cause(결론):
  - 실패 키워드 패턴이 지나치게 넓어 정상 completion 로그를 실패로 오탐

---

## 5. 해결 전략
- 단기 핫픽스:
  - `scheduler.*failed` → `scheduler.*failed:`로 좁혀 실패 문맥만 감지
  - RSS 실패 패턴도 `rss (ingest|summarize) job failed:`로 명시화
- 근본 해결:
  - "문자열 포함"이 아닌 "실패 로그 포맷" 기준으로 탐지 정책 유지
- 안전장치(feature flag, rate limit, timeout/cooldown, circuit breaker 등):
  - traceback/critical 탐지는 그대로 유지해 치명 오류 누락 방지

---

## 6. 수정 내용
- 변경 요약:
  - T+12h 실패 정규식을 오탐 방지형으로 보정
- 변경 파일:
  - `scripts/ops/check_24h_monitoring.sh`
- DB/스키마 변경(있다면):
  - 없음
- 롤백 방법(필수):
  - 해당 파일 정규식을 이전 패턴으로 되돌리고 스크립트 재실행

---

## 7. 검증
- 실행 명령/절차:
  - `bash -n scripts/ops/check_24h_monitoring.sh`
  - `printf '%s\n' '[Scheduler] RSS ingest done. inserted=2, skipped=112, failed_feeds=0' | grep -Eiq "traceback|critical|rss (ingest|summarize) job failed:|daily report .*failed|scheduler.*failed:"; echo $?`
  - `printf '%s\n' '[Scheduler] RSS ingest job failed: timeout while fetching feed' | grep -Eiq "traceback|critical|rss (ingest|summarize) job failed:|daily report .*failed|scheduler.*failed:"; echo $?`
- 결과:
  - 문법 검증 통과
  - 정상 로그(`failed_feeds=0`) 미매칭(1)
  - 실제 실패 로그(`job failed:`) 매칭(0)

- 운영 확인 체크:
  1) OCI에서 `scripts/ops/check_24h_monitoring.sh t12h` 재실행
  2) FAIL 발생 시 매칭 라인을 함께 출력해 진짜 실패 여부 확인

---

## 8. 재발 방지
- 가드레일(테스트/알림/검증 스크립트/권한/필터/타임아웃 등):
  - 실패 탐지 패턴은 필드명(`failed_*`)이 아닌 실패 문장(`failed:`)을 기준으로 유지
- 문서 반영:
  - plan/result 업데이트 여부: YES
  - troubleshooting 링크 추가 여부: YES
  - PROJECT_CHARTER.md 변경(있다면): 8.5 문서 참고/8.9 변경 이력에 18-16 반영

---

## 9. References
- `docs/work-plans/18-16_t12h_failed_keyword_false_positive_filter_plan.md`
- `scripts/ops/check_24h_monitoring.sh`
- `docs/work-result/18-16_t12h_failed_keyword_false_positive_filter_result.md`

## 10. 배운점
- 트러블 슈팅은 "경보가 왜 울렸는지"를 로그 문맥 단위로 증명하는 과정이 중요하다.
- 포트폴리오에는 "오탐 원인 재현 → 필터 수정 → 회귀 검증"의 폐루프를 강조하면 운영 신뢰성 개선 역량을 명확히 보여줄 수 있다.
- 규칙 기반 모니터링에서 정규식 범위 설계와 샘플 기반 검증 능력이 향상됐다.
