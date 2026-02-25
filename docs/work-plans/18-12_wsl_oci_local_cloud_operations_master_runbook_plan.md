# 18-12. WSL/OCI 로컬-클라우드 통합 운영 Runbook 작성 계획

**작성일**: 2026-02-25  
**작성자**: Codex (GPT-5)  
**상태**: Fixed  
**관련 계획 문서**: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`  

---

## 0. 트리거(Why started)
- 사용자가 "지금까지 작업한 내용(WSL vs OCI, 로컬 vs 클라우드, 운영/복구 흐름)을 한 번에 이해 가능한 runbook"을 요청함.
- 실제 운영 중 WSL/OCI 컨텍스트 혼선이 재발했기 때문에, 단일 통합 문서가 필요함.

## 1. 문제 요약
- 증상:
  - 문서가 분산되어 있어 초보자가 운영 컨텍스트를 놓치기 쉬움
  - 로컬 포트(`localhost`) 기준으로 WSL/OCI 대상을 혼동할 수 있음
- 영향 범위:
  - 운영 실수(잘못된 인스턴스 수정/테스트), 장애 대응 시간 증가
- 재현 조건:
  - 동일 사용자가 WSL 로컬 테스트와 OCI 운영을 병행할 때

## 2. 원인 분석
- Root cause:
  - "환경 모델(어디서 무엇을 실행/접속/복구하는지)"에 대한 단일 관점(runbook)이 부재

## 3. 대응 전략
- 단기:
  - 기존 runbook 내용을 통합한 마스터 가이드 신규 작성
- 근본:
  - 프로젝트 차터에 신규 runbook 링크와 변경 이력 추가
- 안전장치:
  - 포트/볼륨/백업/알람/재부팅 복구를 단계별 체크리스트로 고정

## 4. 구현/수정 내용
- 신규 문서:
  - `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
- 수정 문서:
  - `docs/PROJECT_CHARTER.md` (참조 링크 + changelog)
- 산출 문서:
  - `docs/work-result/18-12_wsl_oci_local_cloud_operations_master_runbook_result.md`

## 5. 검증 기준
1. 초보자 기준으로 "WSL/OCI 차이"와 "어떤 터미널에서 어떤 명령을 치는지"가 분리 설명되어야 함
2. 운영 체크리스트(기동/백업/모니터링/복구)가 명령 기반으로 재현 가능해야 함
3. 기존 관련 runbook(18 A-to-Z, auto retry, data migration)과 상호 링크되어야 함

## 6. 롤백
- 문서 작업이므로 롤백은 해당 파일 revert로 충분

## 7. 문서 반영
- Result 문서 작성 및 Plan 링크 연결
- Charter 참조 목록/변경 이력 반영

## 8. 아키텍처 선택/대안/트레이드오프
- 선택: "마스터 runbook + 기존 전문 runbook 링크" 2계층 구조
- 대안:
  1. 기존 문서 각각 개별 업데이트만 수행
  2. 하나의 거대 문서로 완전 통합(기존 문서 폐기)
  3. 마스터 runbook 신설 + 기존 문서 유지(채택)
- 채택 근거:
  - 1은 탐색 비용이 높음
  - 2는 유지보수 비용이 커짐
  - 3은 입문/운영 동시 만족 + 변경 영향 최소

## 9. 계획 변경 이력
- 2026-02-25: 초안 작성
- 2026-02-25: 구현 완료.
  - 신규: `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
  - 수정: `docs/PROJECT_CHARTER.md`
  - 결과 문서: `docs/work-result/18-12_wsl_oci_local_cloud_operations_master_runbook_result.md`
