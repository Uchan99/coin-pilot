# 32. 프로젝트 전주기 Runbook 문서화 계획

**작성일**: 2026-03-14  
**작성자**: Codex  
**상태**: Approved  
**관련 계획 문서**: 없음  
**승인 정보**: 사용자 승인 / 2026-03-14 / "이번에 생성한 파일로 말 그대로 우리 프로젝트 전부를 다 이해할 수 있도록 진행해줘."

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 사용자가 "이 프로젝트의 기획부터 현재 운영, 추후 개발 예정 사항까지를 한 번에 공부할 수 있는 수준의 상세 runbook" 작성을 요청했다.
  - 현재 저장소에는 개별 작업 계획/결과/트러블슈팅 문서는 많지만, 전체 시스템을 초보자 관점까지 포함해 종합 설명하는 최신 통합 문서는 부족하다.
  - `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`처럼 특정 운영 주제 문서는 존재하나, 전략/데이터/AI/아키텍처/운영/향후 로드맵을 모두 묶은 "프로젝트 전체 해설서"는 없다.
- 왜 즉시 대응이 필요한지:
  - 현재 문서 구조만으로는 신규 참여자나 비개발자가 전체 맥락을 따라가기 어렵다.
  - 향후 기능 변경이나 운영 이슈가 생겨도 기준 설명 문서가 없으면 이해 비용이 계속 누적된다.

## 1. 문제 요약
- 증상:
  - 프로젝트 전반을 설명하는 문서가 여러 파일에 분산돼 있어 학습 순서가 명확하지 않다.
  - 설계 이유, 대안 비교, 코드 위치, 기술 스택 설명, 쉬운 설명이 한 세트로 정리돼 있지 않다.
  - 기획 의도와 현재 운영 현실, 남은 과제가 하나의 서사로 연결되지 않는다.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 신규 유지보수자 온보딩 속도 저하
  - 리스크: 설계 의도 오해로 잘못된 수정/운영 판단 가능
  - 데이터: 어떤 데이터가 어디서 생성/소비되는지 추적 비용 증가
  - 비용: 문서 탐색/설명/인수인계 반복 공수 증가
- 재현 조건:
  - 저장소를 처음 읽는 사람, 비개발자, 또는 오래 쉬었다가 복귀한 운영자가 전체 구조를 이해하려 할 때

## 2. 원인 분석
- 가설:
  1. 작업 단위 문서는 충실하지만, 프로젝트 전체를 재구성하는 상위 레벨 문서 체계가 부족하다.
  2. 코드/문서/운영 스크립트/배포 구성이 빠르게 확장되면서 설명이 기능 중심으로 분절됐다.
  3. "왜 이 설계를 택했는가"와 "초보자에게 어떻게 설명할 것인가"가 문서 작성 기본 규칙으로 강제되지 않았다.
- 조사 과정(예정):
  - `docs/PROJECT_CHARTER.md`, `README.md`, `docs/checklists/remaining_work_master_checklist.md`, `docs/work-plans/`, `docs/work-result/`, `docs/troubleshooting/`, `docs/runbooks/`를 전수 확인한다.
  - `src/`, `scripts/`, `config/`, `deploy/`, `tests/`를 기준으로 시스템 구성 요소를 도메인별로 분류한다.
  - 실제 코드와 문서 설명이 일치하는지 파일 단위로 대조한다.
- Root cause:
  - "프로젝트 전체 설명을 위한 상위 runbook 세트"와 "문서 완성도 검증 절차"가 아직 공식 산출물로 존재하지 않는다.

## 3. 대응 전략
- 단기 대응:
  - 저장소 전체를 재검토해 현재 기준의 통합 runbook 세트를 우선 작성하고, 최종 산출물은 개인 학습용 비공개 문서로 `docs/portfolio/study/` 아래에 정리한다.
- 근본 해결:
  - 기획 배경, 아키텍처, 데이터 흐름, 전략/리스크, AI/에이전트, 배포/운영, 테스트/검증, 향후 로드맵을 분리된 문서 세트로 구조화한다.
  - 각 문서에 "핵심 요약 / 쉬운 설명 / 선행지식 / 설계 이유 / 대안 비교 / 코드 위치 / 운영 기준 / 남은 과제"를 공통 섹션으로 넣는다.
- 안전장치(가드레일/차단/timeout 등):
  - 실제 구현 전, plan 승인 후에만 문서 작성에 착수한다.
  - 문서 작성 후에는 저장소 전체를 다시 스캔해 누락 파일/누락 주제를 coverage checklist로 검증한다.
  - 코드에 없는 사실은 쓰지 않고, 불확실한 내용은 가정/제약/향후 확인 항목으로 분리한다.

## 4. 구현/수정 내용
- 변경 파일(예정):
  1. `docs/portfolio/study/32_project_runbook_index.md`
  2. `docs/portfolio/study/32_product_planning_and_evolution_runbook.md`
  3. `docs/portfolio/study/32_system_architecture_and_code_map_runbook.md`
  4. `docs/portfolio/study/32_trading_strategy_risk_and_execution_runbook.md`
  5. `docs/portfolio/study/32_ai_agents_data_and_tech_stack_runbook.md`
  6. `docs/portfolio/study/32_deployment_operations_monitoring_runbook.md`
  7. `docs/portfolio/study/32_testing_verification_and_future_roadmap_runbook.md`
  8. `docs/portfolio/study/32_file_inventory_and_reference_map_runbook.md`
  9. `docs/work-result/32_project_end_to_end_runbook_documentation_result.md`
- 구현 범위(예정):
  1. 저장소 전수 인벤토리 작성
  2. 코드/문서/운영 기준 간 정합성 확인
  3. 다중 runbook 초안 작성
  4. 쉬운 설명/선행지식/대안 비교/코드 위치 보강
  5. 전수 재검토 및 누락 점검
- DB 변경(있다면):
  - 없음
- 주의점:
  - 이 작업은 문서화 중심이지만, 코드 사실과 다른 설명을 만들지 않기 위해 실제 파일을 근거로 작성해야 한다.
  - 문서 분량이 많아질 수 있으므로 한 파일에 과도하게 몰지 않고 주제별로 분리한다.
  - 특정 과거 계획이 현재 운영과 다를 경우, "기획 당시 의도"와 "현재 운영 기준"을 명확히 구분한다.

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  1. 비개발자/신규 참여자가 `docs/portfolio/study/32_project_runbook_index.md`부터 읽어 전체 구조를 따라갈 수 있어야 한다.
  2. 각 핵심 도메인(기획, 전략, AI, 데이터, 배포, 운영, 테스트, 로드맵)에 대해 "무엇/왜/어디 코드/어떻게 운영"이 모두 문서화돼 있어야 한다.
  3. 설계 선택마다 대안 비교와 채택 이유가 포함돼 있어야 한다.
- 회귀 테스트:
  - runbook에 적은 코드 경로/스크립트/설정명이 실제 저장소와 일치해야 한다.
  - 기존 Charter/README/checklist와 충돌하는 설명이 없어야 한다.
- 운영 체크:
  - 문서 완성 후 `rg` 기반 coverage 검증으로 핵심 디렉터리와 주요 문서가 빠지지 않았는지 점검한다.
  - 결과 문서에 검증 명령과 확인 기준을 남긴다.

## 6. 롤백
- 코드 롤백:
  - 신규 runbook/result/checklist 변경 revert
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 승인 후 구현 시 `docs/work-result/32_project_end_to_end_runbook_documentation_result.md` 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 현재는 정책 변경이 아니라 문서 보강 작업이므로 Charter 변경은 기본적으로 불필요
  - 다만 조사 과정에서 Charter와 현재 운영 기준 간 불일치가 발견되면 changelog와 함께 반영 여부를 별도로 명시

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1. runbook 간 공통 섹션 템플릿 표준화 검토
  2. 향후 main 작업 완료 시 관련 runbook 동기화 체크리스트 추가 여부 검토
  3. README와 runbook index 간 역할 분리 기준 정립

## 9. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **단일 초장문서가 아니라 주제별 분리 runbook 세트 + 인덱스 문서 + 전수 검증 절차**
- 고려 대안:
  1. 모든 내용을 하나의 거대 Markdown 파일에 몰아넣는다.
  2. 현재 work-plan/work-result/troubleshooting 문서를 그대로 참고하라고 안내하고 별도 통합 문서를 만들지 않는다.
  3. 주제별 runbook 세트로 나누고, 인덱스 문서로 학습 순서를 제공한다. (채택 예정)
- 대안 비교:
  1. 단일 초장문서:
     - 장점: 파일 수가 적다.
     - 단점: 탐색성과 유지보수성이 급격히 떨어지고, 특정 주제 수정 시 충돌이 커진다.
  2. 기존 문서 참고 방식:
     - 장점: 추가 작성량이 적다.
     - 단점: 사용자가 원하는 "쉽고 체계적인 전체 설명" 요구를 충족하지 못한다.
  3. 주제별 runbook 세트:
     - 장점: 학습 순서, 유지보수, 교차 검증, 향후 갱신이 가장 쉽다.
     - 단점: 초기 작성 공수가 크고, 문서 간 링크 관리가 필요하다.

## 10. 실행 단계(예정)
1. 저장소 전수 인벤토리와 현재 운영 기준 문서 수집
2. 도메인 분류표 작성
3. runbook 세트 초안 작성
4. 쉬운 설명/선행지식/대안 비교/코드 위치 보강
5. 저장소 재스캔 및 coverage 검증
6. result 문서 작성 및 checklist 상태 갱신

## 11. 변경 이력
- 2026-03-14: 사용자 요청에 따라 신규 main 계획 생성. 현재 상태는 `Approval Pending`.
- 2026-03-14: 사용자 승인 후 범위를 "프로젝트 전체를 이해할 수 있는 수준의 종합 runbook 세트"로 확정하고 구현 착수.
- 2026-03-14: 저장소 전체 추적 가능성을 높이기 위해 `32_file_inventory_and_reference_map_runbook.md` appendix를 추가하기로 범위를 확장했다.
- 2026-03-14: `docs/runbooks/`가 기본 ignore 대상임을 확인해, 32번 runbook 세트만 선택적으로 버전 관리되도록 `.gitignore` 예외 규칙을 추가하기로 했다.
- 2026-03-15: 사용자 요청에 따라 산출물 성격을 "공식 공개 runbook"에서 "개인 학습용 비공개 study 문서"로 재정의했다. 최종 위치를 `docs/portfolio/study/32_*`로 변경하고, `docs/runbooks/`는 다시 완전 ignore 정책으로 유지한다.
