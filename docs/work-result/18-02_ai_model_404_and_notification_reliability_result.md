# 18-02. AI 모델 404 및 Discord 알림 누락 복구 구현 결과

작성일: 2026-02-23
작성자: Codex (GPT-5)
관련 계획서: `docs/work-plans/18-02_ai_model_404_and_notification_reliability_plan.md`
상태: Verified
완료 범위: Phase 1~2
선반영/추가 구현: 있음(운영 데이터 호환 복구 포함)
관련 트러블슈팅(있다면): `docs/troubleshooting/18-02_ai_model_404_and_notification_reliability.md`

---

## 1. 개요
- 구현 범위 요약:
  - Anthropic 404 모델 ID 교정
  - bot -> n8n webhook 연결 실패(`localhost`) 교정
  - NotificationManager 전송 fallback/진단로그 보강
  - 재기동 과정에서 노출된 DB/Redis 데이터 포맷 호환 이슈 복구
- 목표(요약):
  - AI Decision 경로를 정상 복구하고 REJECT/CONFIRM 알림 누락을 제거
- 이번 구현이 해결한 문제(한 줄):
  - 모델 미지원 + 웹훅 경로 오설정으로 동시에 발생한 REJECT 편향/알림 누락을 해소했다.

---

## 2. 구현 내용(핵심 위주)
### 2.1 LLM 모델/웹훅 경로 운영값 교정
- 파일/모듈:
  - `deploy/cloud/oci/.env`
  - `deploy/cloud/oci/.env.example`
  - `deploy/cloud/oci/docker-compose.prod.yml`
- 변경 내용:
  - `LLM_MODEL=claude-haiku-4-5-20251001`로 교체
  - `N8N_URL=http://n8n:5678`로 교체(컨테이너 내부 DNS)
  - compose 기본값도 동일 모델로 정렬
- 효과/의미:
  - Anthropic 404(`not_found_error`) 제거
  - bot webhook 전송의 기본 연결 실패 제거

### 2.2 Notification 전송 신뢰성 보강
- 파일/모듈:
  - `src/common/notification.py`
  - `config/n8n_workflows/ai_decision.json`
- 변경 내용:
  - base URL 후보 리스트(`설정값 -> n8n -> localhost`) fallback
  - 실패 시 endpoint/url 포함 로그 출력으로 원인 추적성 강화
  - AI Decision Discord description 길이 제한을 `500 -> 1500`으로 상향
- 효과/의미:
  - 환경 오설정 시에도 webhook 전송 성공 확률 향상
  - 재발 시 즉시 원인 식별 가능
  - REJECT/CONFIRM 사유 문맥 손실 감소

### 2.3 운영 데이터 호환 복구(추가)
- 파일/모듈:
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `deploy/docker-compose.yml`
- 변경 내용:
  - TimescaleDB 이미지: `2.24.0-pg15`로 정합화
  - Redis 이미지: `8.4.0-alpine`로 정합화
- 효과/의미:
  - 기존 볼륨 데이터와 엔진 버전 불일치로 인한 루프 장애 제거

---

## 3. 변경 파일 목록
### 3.1 수정
1) `src/common/notification.py`
2) `deploy/cloud/oci/.env`
3) `deploy/cloud/oci/.env.example`
4) `deploy/cloud/oci/docker-compose.prod.yml`
5) `deploy/docker-compose.yml`
6) `docs/work-plans/18-02_ai_model_404_and_notification_reliability_plan.md`

### 3.2 신규
1) `docs/work-plans/18-02_ai_model_404_and_notification_reliability_plan.md`
2) `docs/troubleshooting/18-02_ai_model_404_and_notification_reliability.md`
3) `docs/work-result/18-02_ai_model_404_and_notification_reliability_result.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점:
  - 이미지 태그를 낮추면 기존 데이터(AOF/RDB, timescaledb extension)와 호환이 깨질 수 있으므로 주의

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `./scripts/security/preflight_security_check.sh`
- 결과:
  - `PASSED`

### 5.2 테스트 검증
- 실행 명령:
  - `docker inspect coinpilot-bot ...` (N8N_URL/LLM_MODEL 확인)
  - `docker exec coinpilot-bot python -c "... requests.get('https://api.anthropic.com/v1/models') ..."`
  - `docker exec coinpilot-bot python -c "... requests.post(N8N_URL+'/webhook/ai-decision') ..."`
  - `cat <<'PY' | docker exec -i coinpilot-bot python -` (factory llm ainvoke)
  - `cat <<'PY' | docker exec -i coinpilot-bot python -` (notifier.send_webhook)
- 결과:
  - `LLM_MODEL=claude-haiku-4-5-20251001`, `MODEL_AVAILABLE=True`
  - bot -> n8n ai-decision webhook `HTTP 200`
  - LLM direct invoke 응답 `OK`
  - notifier 경로 `NOTIFY_OK True`

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법:
  - n8n execution DB 조회
- 결과:
  - `AI Decision Notification` 최신 실행 `success` 확인(id 60)

---

## 6. 배포/운영 확인 체크리스트(필수)
1) `docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml ps`에서 `db/redis/bot/n8n` Up 확인
2) bot env 값 확인: `N8N_URL=http://n8n:5678`, `LLM_MODEL=claude-haiku-4-5-20251001`
3) Discord에서 AI Decision 테스트 메시지 수신 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 환경값 즉시 수정 + notification 코드 fallback 보강 + 이미지 정합 복구
- 고려했던 대안:
  1) env만 수정하고 코드 변경 없음
  2) 모델 fallback 로직 대규모 추가(모델 목록 자동탐지)
  3) env 수정 + 최소 코드 보강(채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1) 즉시 장애 해소 속도가 가장 빠름
  2) 오설정 재발에도 notifier가 자동 보완
  3) 로그 진단성이 증가해 추후 MTTR 감소
- 트레이드오프(단점)와 보완/완화:
  1) fallback URL이 2개여서 실패 시 시도 횟수 증가
  2) 근본적 모델 정책 자동화는 후속 과제로 분리

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `src/common/notification.py` fallback 구성 의도
  2) localhost 오설정이 컨테이너 환경에서 실패하는 이유
- 주석에 포함한 핵심 요소:
  - 의도/왜(why)
  - 실패 케이스(localhost 오설정)

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - 모델/웹훅 경로 복구 및 검증 완료
- 변경/추가된 부분(왜 바뀌었는지):
  - 실적용 중 DB/Redis 이미지 호환 이슈가 노출되어 정합 복구를 추가 수행
- 계획에서 비효율적/오류였던 점(있다면):
  - 최초 범위에 데이터 엔진 버전 정합 리스크를 충분히 반영하지 못함

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - AI 모델 404와 Discord 알림 누락의 직접 원인은 해소됨
  - 운영 스택(db/redis/bot/n8n)도 정합 상태로 복구됨
- 후속 작업(다음 plan 번호로 넘길 것):
  1) Anthropic 모델 가용성 startup 점검 자동화(선택)
  2) compose 이미지 업그레이드 전 데이터 포맷 호환 점검 체크리스트 고정

---

## 12. References
- `docs/work-plans/18-02_ai_model_404_and_notification_reliability_plan.md`
- `docs/troubleshooting/18-02_ai_model_404_and_notification_reliability.md`
