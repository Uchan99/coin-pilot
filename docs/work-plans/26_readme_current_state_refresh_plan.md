# 26. README 최신 운영 상태 반영 개편 계획

**작성일**: 2026-03-02  
**작성자**: Codex  
**상태**: Verified  
**관련 계획 문서**: `docs/work-plans/25_remaining_work_master_checklist_and_agents_workflow_update_plan.md`  
**관련 결과 문서**: `docs/work-result/26_readme_current_state_refresh_result.md`  
**승인 정보**: 사용자 / 2026-03-02 / "진행해줘."

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 루트 `README.md`가 초기 버전(v3.0) 기준으로 남아 있어 현재 운영 구조(OCI Compose 중심, Discord 모바일 조회 봇, 문서 체계)와 불일치.
- 왜 즉시 대응이 필요했는지:
  - 신규/복귀 사용자가 README 기준으로 잘못된 실행 경로를 따를 가능성이 높고, 현재 프로젝트 신뢰성/재현성이 저하됨.

## 1. 문제 요약
- 증상:
  - 서비스 구조, 실행 방법, 리스크 정책, 문서 링크가 최신 상태와 다름.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 잘못된 명령/경로 안내
  - 리스크: 운영 실수 가능성 증가
  - 데이터: 직접 훼손은 없으나 운영 문서 정합성 저하
  - 비용: 온보딩/운영 커뮤니케이션 비용 증가
- 재현 조건:
  - README만 보고 신규 환경 구성 시도 시 즉시 재현

## 2. 원인 분석
- 가설:
  - 구현 속도 대비 루트 README 유지보수가 지연됨.
- 조사 과정:
  - `README.md`, `docs/PROJECT_CHARTER.md`, `docs/checklists/remaining_work_master_checklist.md`, `deploy/cloud/oci/docker-compose.prod.yml` 비교.
- Root cause:
  - README에 문서 동기화 루틴이 없었고, 현재 운영 기준(OCI/Compose/문서 게이트/모니터링 스크립트)이 반영되지 못함.

## 3. 대응 전략
- 단기 핫픽스:
  - README를 최신 기준으로 전면 교체(과장/이모지 최소화, 실행 명령 정확화).
- 근본 해결:
  - README에 “Source of Truth는 PROJECT_CHARTER”와 “운영 우선 문서 경로”를 명시해 드리프트를 줄임.
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 실행 명령은 실제 현재 파일 경로/서비스명 기준으로만 기재.
  - “실행 전 점검” 절차와 “운영 검증 명령”을 포함.

## 4. 구현/수정 내용
- 변경 파일:
  - `README.md` (전면 개편)
  - `docs/work-result/26_readme_current_state_refresh_result.md` (구현 후 작성)
  - 필요 시 `docs/PROJECT_CHARTER.md` changelog(README 운영 기준을 정책으로 올릴 경우)
- DB 변경(있다면):
  - 없음
- 주의점:
  - AI 생성물 느낌을 줄이기 위해 과장 문구/불필요 장식 제거.
  - 실제 존재하지 않는 디렉터리/모듈명(`src/api`, `src/assistant`) 표기 금지.

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - README 기준 실행 절차가 현재 OCI/Compose 구조와 일치해야 함.
- 회귀 테스트:
  - 문서 작업이므로 코드 회귀는 없지만, 명령/경로 오탈자 점검 필수.
- 운영 체크:
  - README에 기재한 핵심 명령(`compose ps`, `check_24h_monitoring.sh`)이 실제 파일/서비스와 맞는지 확인.

## 6. 롤백
- 코드 롤백:
  - README 이전 버전으로 git revert 가능.
- 데이터/스키마 롤백:
  - 없음.

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획 문서 작성 후 승인 대기.
  - 구현 완료 후 결과 문서 작성.
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - README 운영 원칙을 Charter changelog에 남길지 구현 시점에 판단.

## 8. 아키텍처/문서 설계 결정 (대안 비교)
- 대안 1: README 최소 수정(몇 줄만 최신화)
  - 장점: 빠름
  - 단점: 구조적 불일치 지속, 다시 드리프트
- 대안 2: README 전면 개편(채택)
  - 장점: 현재 운영/문서 체계를 일관되게 반영
  - 단점: 작성량 증가, 검토 필요
- 대안 3: README를 축소하고 문서 링크만 제공
  - 장점: 유지보수 부담 감소
  - 단점: 첫 진입자 가이드 부족

- 최종 선택:
  - **대안 2(전면 개편)** 채택.
- 선택 이유:
  - 현재 프로젝트는 운영 절차가 복합적이므로 README에서 최소한의 실행/운영/문서 지도를 직접 제공해야 실사용 품질이 확보됨.

## 9. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1. main 계획 완료 시 README 동기화 필요 여부를 체크리스트 점검 항목으로 추가 검토
  2. README 변경 이력 섹션(요약) 운영 여부 검토

---

## Plan 변경 이력
- 2026-03-02: 사용자 승인 반영(`Approval Pending` -> `Approved`), 구현 착수.
- 2026-03-02: README 개편 구현/검증 완료, 결과 문서 및 체크리스트 상태(`done`) 반영.
