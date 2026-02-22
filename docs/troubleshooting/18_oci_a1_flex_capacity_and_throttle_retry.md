# 18. OCI A1.Flex Capacity/Throttle 재시도 이슈

작성일: 2026-02-22  
상태: Resolved (스크립트 반영 완료)  
관련 계획서: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`  
관련 결과서: `docs/work-result/18_cloud_migration_cost_optimized_result.md`  
관련 Runbook: `docs/runbooks/18_oci_a1_flex_auto_retry_runbook.md`

---

## 1) 증상
- `scripts/cloud/oci_retry_launch_a1_flex.sh` 장시간 실행 중,
  - `500 InternalError / Out of host capacity`는 재시도됨
  - 이후 `429 TooManyRequests` 발생 시 `non-retryable launch failure`로 즉시 종료됨

로그 예시(요약):
- `code: InternalError, message: Out of host capacity` -> retry
- `code: TooManyRequests, message: Too many requests for the user` -> exit

## 2) 원인
- 재시도 분기 함수가 capacity 계열(`Out of capacity`, `Out of host capacity`)만 포함
- `429 TooManyRequests`는 비재시도 오류로 분류되어 종료

코드 위치:
- `scripts/cloud/oci_retry_launch_a1_flex.sh`의
  - `is_retryable_capacity_error()`
  - 메인 루프의 `non-retryable launch failure` 분기

## 3) 대응 방안 검토
1. 현행 유지(429 즉시 종료)
- 장점: 스크립트 단순
- 단점: 장시간 자동화가 중단되어 수동 재실행 필요

2. 429도 고정 600초 재시도
- 장점: 구현 간단
- 단점: API 스로틀 상황에서 충분히 회복되지 않을 수 있음

3. 429 전용 백오프 재시도(채택)
- 장점: 스로틀 상황에서 점진적으로 요청 빈도를 낮춰 재성공 확률 증가
- 단점: 총 대기 시간이 길어질 수 있음

## 4) 적용 내용
- `TooManyRequests(429)` 판별 함수 추가: `is_retryable_throttle_error()`
- 429 발생 시 지수 백오프 + 지터 적용:
  - `THROTTLE_RETRY_BASE_SECONDS` (기본 900초)
  - `THROTTLE_RETRY_MAX_SECONDS` (기본 3600초)
  - `THROTTLE_JITTER_MAX_SECONDS` (기본 120초)
- capacity 오류 발생 시 throttle 연속 카운터 초기화
- 운영 문서/환경 예시 업데이트:
  - `scripts/cloud/oci_retry.env.example`
  - `docs/runbooks/18_oci_a1_flex_auto_retry_runbook.md`

## 5) 검증 방법
```bash
bash -n scripts/cloud/oci_retry_launch_a1_flex.sh
bash -n scripts/cloud/run_oci_retry_from_env.sh
```

실행 중 확인 포인트:
- 429 발생 시 아래 로그가 출력되며 종료하지 않고 대기 후 재시도
  - `[WARN] retryable throttle error detected(429); sleeping ...`

## 6) 남은 리스크
1. Chuncheon A1.Free host capacity 자체 부족은 계속 발생 가능
2. OCI 측 API 정책 변경 시 429/메시지 패턴 변경 가능
3. 과도한 병렬 실행(동시에 여러 retry 프로세스) 시 스로틀 빈도 증가 가능

완화:
1. retry 프로세스는 계정당 1개만 실행
2. Discord 알림으로 장시간 상태 모니터링
3. 필요 시 `THROTTLE_RETRY_MAX_SECONDS`를 상향
