# 18-02. AI 모델 404 및 Discord 알림 누락 트러블슈팅 / 핫픽스

작성일: 2026-02-23
상태: Verified
우선순위: P0
관련 문서:
- Plan: `docs/work-plans/18-02_ai_model_404_and_notification_reliability_plan.md`
- Result: `docs/work-result/18-02_ai_model_404_and_notification_reliability_result.md`
- Charter update 필요: NO

---

## 1. 트리거(왜 시작했나)
- 모니터링/로그/사용자 리포트로 관측된 내용:
  - AI Decision이 연속 REJECT(404 model not found)
  - REJECT Discord 알림 누락
- 긴급도/영향:
  - 전략 실행 관측성 저하 + 판단 품질 저하로 P0 대응

---

## 2. 증상/영향
- 증상:
  - `model: claude-3-5-haiku-20241022` not_found_error
  - `Notification attempt N error: All connection attempts failed`
- 영향(리스크/데이터/비용/운영):
  - AI 분석 경로 사실상 비활성
  - 장애 탐지 지연
- 발생 조건/재현 조건:
  - bot env의 `LLM_MODEL`, `N8N_URL` 오설정

---

## 3. 재현/관측 정보
- 핵심 로그/에러 메시지:
  - `Analyst output validation failed: ... model: claude-3-5-haiku-20241022`
  - `Notification attempt 1 error: All connection attempts failed`
- 추가 관측:
  - bot 컨테이너 env: `N8N_URL=http://localhost:5678`
  - Anthropic models list에 `claude-3-5-haiku-20241022` 없음

---

## 4. 원인 분석
- Root cause(결론):
  1) Anthropic 계정에서 미지원 모델 ID 사용
  2) 컨테이너 내부 localhost 사용으로 n8n 연결 실패

---

## 5. 해결 전략
- 단기 핫픽스:
  - `.env`의 `LLM_MODEL`, `N8N_URL` 교정
- 근본 해결:
  - compose/.env.example 기본값 교정
  - notification 전송 fallback 및 진단 로그 강화

---

## 6. 수정 내용
- 변경 요약:
  - 모델 기본값 및 n8n endpoint 정렬
  - webhook 전송 신뢰성 보강
- 변경 파일:
  - `src/common/notification.py`
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `deploy/cloud/oci/.env.example`
  - `deploy/cloud/oci/.env`
- DB/스키마 변경(있다면):
  - 없음
- 롤백 방법(필수):
  - 코드/환경 변수 이전값으로 복원 후 bot 재시작

---

## 7. 검증
- 실행 명령/절차:
  - `docker inspect coinpilot-bot` env 확인
  - webhook 수동 호출
  - bot 로그에서 404/connection failed 소멸 확인
- 결과:
  - `LLM_MODEL` 가용성 확인: `MODEL_AVAILABLE=True`
  - bot notifier 경로 확인: `NOTIFY_OK True`
  - n8n execution 최신 `AI Decision Notification` 상태 `success`

---

## 8. 재발 방지
- 가드레일:
  - 모델/웹훅 endpoint 오설정 시 로그로 즉시 식별 가능하게 유지
- 문서 반영:
  - plan/result/troubleshooting 상호 링크 유지

---

## 9. References
- `docs/work-plans/18-02_ai_model_404_and_notification_reliability_plan.md`
