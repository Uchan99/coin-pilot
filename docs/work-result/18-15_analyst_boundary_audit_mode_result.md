# 18-15. Analyst Rule Boundary Audit Mode 전환 결과

작성일: 2026-02-26  
작성자: Codex (GPT-5)  
관련 계획서: `docs/work-plans/18-15_analyst_boundary_audit_mode_plan.md`  
상태: Verified  
완료 범위: Phase 1  
선반영/추가 구현: 없음  
관련 트러블슈팅(있다면): `docs/troubleshooting/18-15_analyst_rule_boundary_false_rejects.md`

---

## 1. 개요
- 구현 범위 요약:
  - Analyst 경계 위반 정책을 `재시도+강제REJECT`에서 `audit 기록` 모드로 전환
  - Analyst 프롬프트의 Rule Engine 재판단 금지 제약 강화
  - Runner 알림 payload에 boundary audit 필드 추가
- 목표(요약):
  - 경계 위반 오탐으로 인한 연속 REJECT와 재시도 credit 낭비를 완화
- 이번 구현이 해결한 문제(한 줄):
  - 경계 위반 문구로 인한 과잉 차단을 제거하고 관측 가능한 audit 로그로 전환

---

## 2. 구현 내용(핵심 위주)
### 2.1 Analyst 경계 정책 전환 (enforce -> audit)
- 파일/모듈: `src/agents/analyst.py`
- 변경 내용:
  - 2회 재시도 루프 제거(단일 호출)
  - 경계 위반 시 강제 REJECT 제거
  - `detect_rule_revalidation_terms()`로 감지 term을 canonical 목록으로 추출
  - `build_rule_boundary_audit_note()`를 reasoning에 부착해 감사 기록 유지
  - `analyst_decision`에 `boundary_violation`, `boundary_terms` 필드 추가
- 효과/의미:
  - 경계 위반 노이즈가 의사결정 하드차단으로 이어지지 않음
  - 동일 케이스 재시도 호출 제거로 비용/지연 감소

### 2.2 프롬프트 제약 강화
- 파일/모듈: `src/agents/prompts.py`
- 변경 내용:
  - Analyst system prompt에 절대 금지 표현 예시 추가
  - Analyst 전용 `ANALYST_REGIME_GUIDANCE` 추가(볼린저/거래량 재유도 문구 제거)
  - `get_analyst_prompt()`에서 Analyst 전용 가이드 사용
- 효과/의미:
  - 모델이 Rule Engine 항목을 재판단하는 유도 요인을 감소

### 2.3 Runner 로그/알림에 boundary audit 전달
- 파일/모듈: `src/agents/runner.py`
- 변경 내용:
  - `analyst_decision`에서 boundary audit 정보 수집
  - `_log_decision`에 `boundary_violation`, `boundary_terms` 파라미터 추가
  - Discord webhook payload(`/webhook/ai-decision`)에 boundary audit 필드 포함
- 효과/의미:
  - 차단 없이도 운영자가 boundary 위반 추세를 추적 가능

### 2.4 단위 테스트 갱신
- 파일/모듈: `tests/agents/test_analyst_rule_boundary.py`
- 변경 내용:
  - 기존 `build_rule_boundary_reject_reasoning` 테스트를 audit note 기준으로 대체
  - canonical term 감지 테스트 추가
- 효과/의미:
  - 정책 전환(enforce -> audit)에 맞는 회귀 보장

---

## 3. 변경 파일 목록
### 3.1 수정
1) `src/agents/analyst.py`  
2) `src/agents/prompts.py`  
3) `src/agents/runner.py`  
4) `tests/agents/test_analyst_rule_boundary.py`  
5) `docs/PROJECT_CHARTER.md`  

### 3.2 신규
1) `docs/work-plans/18-15_analyst_boundary_audit_mode_plan.md`  
2) `docs/troubleshooting/18-15_analyst_rule_boundary_false_rejects.md`  
3) `docs/work-result/18-15_analyst_boundary_audit_mode_result.md`  

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점:
  - 경계 audit 정보는 `reasoning`/webhook payload 레벨로만 추가되어 DB 스키마 영향 없음

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `python3 -m compileall src/agents/analyst.py src/agents/prompts.py src/agents/runner.py`
- 결과:
  - 컴파일 통과

### 5.2 테스트 검증
- 실행 명령:
  - `.venv/bin/pytest -q tests/agents/test_analyst_rule_boundary.py`
  - `.venv/bin/pytest -q tests/test_agents.py`
- 결과:
  - `test_analyst_rule_boundary.py`: 7 passed
  - `test_agents.py`: 3 passed

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법(healthcheck, curl, kubectl 등):
  - bot 로그/Discord AI decision에서 boundary audit 메시지 노출 확인
- 결과:
  - 운영 적용 후 관측 필요(문서화 완료)

---

## 6. 배포/운영 확인 체크리스트(필수)
1) OCI에 최신 코드 배포 후 bot 재기동  
2) `AI Decision` 메시지에서 기존 경계 위반 고정 REJECT 문구 감소 여부 확인  
3) reasoning 내 `[BoundaryAudit]` 태그 발생 비율 관찰(24~72h)  
4) `Trade Approved by AI Agent` 재출현 여부와 REJECT 사유 분포 비교  

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - Prompt 강화 + Boundary audit 기록 + 재시도 제거
- 고려했던 대안:
  1) 기존 정책 유지(재시도+강제REJECT)
  2) 경계 검사 완전 비활성화
  3) 모델 업그레이드(Sonnet)만으로 해결
  4) audit 모드 전환(채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1) credit 낭비를 유발하던 재시도 제거
  2) 차단 없이도 boundary 위반 추세를 관측 가능
  3) 기존 안정장치(confidence/timeout/예외 REJECT)는 유지
- 트레이드오프(단점)와 보완/완화:
  1) Rule Engine 재판단 문구가 일부 남을 수 있음 -> audit 태그로 가시화
  2) 완전 차단이 아니므로 역할 분리 엄격성 약화 -> RiskManager 하드 제한 유지

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `detect_rule_revalidation_terms()` 의도(감사 관측 목적) 설명
  2) 경계 위반 시 차단하지 않고 reasoning에 audit note를 붙이는 정책 설명
- 주석에 포함한 핵심 요소:
  - 의도/왜(why)
  - 실패 모드(오탐으로 인한 과잉 차단)
  - 운영 트레이드오프(차단 vs 관측)

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - 경계 위반 재시도/강제 REJECT 제거
  - audit 기록 유지
  - 프롬프트 제약 강화
- 변경/추가된 부분(왜 바뀌었는지):
  - boundary 정보를 webhook payload까지 전달해 운영 관측성을 강화
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - Boundary 경로는 하드 차단이 아닌 audit 관측 모드로 전환됨
- 후속 작업(다음 plan 번호로 넘길 것):
  1) 48~72시간 동안 boundary audit 비율/REJECT 사유 분포 추적
  2) 필요 시 탐지 로직을 "단순 언급" vs "임계치 재판단"으로 추가 정교화

---

## 12. References
- `docs/work-plans/18-15_analyst_boundary_audit_mode_plan.md`
- `docs/troubleshooting/18-15_analyst_rule_boundary_false_rejects.md`
- `src/agents/analyst.py`
- `src/agents/prompts.py`
- `src/agents/runner.py`
- `tests/agents/test_analyst_rule_boundary.py`

