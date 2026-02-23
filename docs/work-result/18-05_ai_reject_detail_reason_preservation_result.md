# 18-05. AI REJECT 상세 Reason 보존 구현 결과

작성일: 2026-02-23
작성자: Codex (GPT-5)
관련 계획서: `docs/work-plans/18-05_ai_reject_detail_reason_preservation_plan.md`
상태: Verified
완료 범위: Phase 1
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): `docs/troubleshooting/18-02_ai_model_404_and_notification_reliability.md`

---

## 1. 개요
- 구현 범위 요약:
  - Rule boundary 강제 REJECT 경로에서 고정 단문으로 덮어쓰던 Reason을 개선해 원본 분석 근거를 함께 전달하도록 변경.
- 목표(요약):
  - REJECT 상황에서도 운영자가 판단 가능한 상세 근거를 보존.
- 이번 구현이 해결한 문제(한 줄):
  - "한 줄 고정 사유" 문제를 제거하고 상세 Reason 가독성을 복구했다.

---

## 2. 구현 내용(핵심 위주)
### 2.1 Rule boundary REJECT 메시지 구성 로직 개선
- 파일/모듈:
  - `src/agents/analyst.py`
- 변경 내용:
  - `build_rule_boundary_reject_reasoning()` helper 추가.
  - 재시도 후 Rule boundary 재위반 시 고정 문구 대신 "정책 사유 + 원본 분석 근거" 병기.
  - 원문 비어 있음/과다 길이(상한) 케이스 처리.
- 효과/의미:
  - 차단 정책은 유지하면서 운영 설명력 회복.

### 2.2 회귀 테스트 추가
- 파일/모듈:
  - `tests/agents/test_analyst_rule_boundary.py`
- 변경 내용:
  - 상세 근거 보존 테스트 추가.
  - 장문 truncation(후략) 테스트 추가.
- 효과/의미:
  - 동일 회귀 재발 방지.

---

## 3. 변경 파일 목록
### 3.1 수정
1) `src/agents/analyst.py`
2) `tests/agents/test_analyst_rule_boundary.py`

### 3.2 신규
1) `docs/work-plans/18-05_ai_reject_detail_reason_preservation_plan.md`
2) `docs/work-result/18-05_ai_reject_detail_reason_preservation_result.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점: 코드 롤백만 필요

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `python3 -m py_compile src/agents/analyst.py`
- 결과:
  - 통과

### 5.2 테스트 검증
- 실행 명령:
  - `./.venv/bin/pytest -q tests/agents/test_analyst_rule_boundary.py`
- 결과:
  - 6 passed / 0 failed

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법(healthcheck, curl, kubectl 등):
  - `docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml up -d --build bot`
- 결과:
  - `coinpilot-bot` 재생성 및 Started 확인

---

## 6. 배포/운영 확인 체크리스트(필수)
1) `bot` 컨테이너 재기동 상태 확인 (`Up`)
2) 다음 AI REJECT 알림에서 `[원본 분석 근거]` 포함 여부 확인
3) Reason이 과도하게 길 경우 `(후략)` 처리 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 기존 REJECT 정책을 유지하고, 메시지 포맷만 확장하여 상세 근거를 보존.
- 고려했던 대안:
  1) 기존 고정 문구 유지
  2) Rule boundary 검사 자체 비활성화
  3) REJECT 시에도 Guardian 강제 실행
- 대안 대비 실제 이점(근거/관측 포함):
  1) 정책 강도 유지(안전성 보존)
  2) 운영 가독성/디버깅 가능성 복구
  3) 최소 변경(영향 범위 축소)으로 빠른 반영
- 트레이드오프(단점)와 보완/완화:
  1) 여전히 REJECT는 발생 가능 -> 정책 문구를 함께 표기해 의도 명확화
  2) Reason 길이 증가 가능 -> 상한(truncation)으로 완화

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `build_rule_boundary_reject_reasoning()` 도입 배경(why)
  2) 길이 상한/빈 문자열 처리 불변조건
- 주석에 포함한 핵심 요소:
  - 의도/왜(why)
  - 불변조건(invariants)
  - 엣지케이스/실패 케이스
  - 대안 대비 판단 근거

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - 상세 Reason 보존, 테스트 추가, 런타임 반영 완료
- 변경/추가된 부분(왜 바뀌었는지):
  - 없음
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - 한 줄 고정 REJECT 사유는 제거되었고, 동일 경로에서도 상세 근거가 함께 전달된다.
- 후속 작업(다음 plan 번호로 넘길 것):
  1) 필요 시 Rule boundary 탐지 조건 정밀화(오탐/과탐 조정)
  2) n8n JSON 템플릿 회귀 검증 스크립트 추가

---

## 12. References
- `docs/work-plans/18-05_ai_reject_detail_reason_preservation_plan.md`
- `src/agents/analyst.py`
- `tests/agents/test_analyst_rule_boundary.py`
