# 32. 프로젝트 전주기 Runbook 문서화 결과

작성일: 2026-03-14  
최종 수정일: 2026-03-15  
작성자: Codex  
관련 계획서: `docs/work-plans/32_project_end_to_end_runbook_documentation_plan.md`  
상태: Done  
완료 범위: 저장소 전수 검토 기반 private study 문서 8종 + README/체크리스트/ignore 정책 정리 + coverage 검증  
관련 트러블슈팅: 없음

---

## 0. 해결한 문제 정의

- 증상:
  - 프로젝트의 기획 의도, 현재 설계, 운영 방식, 기술 선택 이유, 장애와 해결 경험이 여러 문서에 흩어져 있었다.
  - 신규 유지보수자나 비개발자가 전체 구조를 이해하려면 `README`, `PROJECT_CHARTER`, 수십 개의 `work-result`, `troubleshooting` 문서를 따로 읽어야 했다.
  - "왜 이렇게 만들었는가"와 "어려움을 어떻게 해결했는가"를 한 번에 따라갈 수 있는 최신 통합 문서가 없었다.
- 영향:
  - 온보딩 시간이 길어지고, 설계 의도 오해 가능성이 컸다.
  - 코드/운영/문서의 전체 그림을 빠르게 이해하기 어려웠다.
  - 포트폴리오/인수인계/운영 설명 시 반복 설명 비용이 컸다.
- 재현 조건:
  - 저장소를 처음 읽는 사람, 비개발자, 오래 쉬었다가 돌아온 유지보수자가 프로젝트 전체를 이해하려고 할 때
- Root cause:
  - 작업 단위 문서는 풍부했지만, 이를 다시 묶어 주는 상위 runbook 세트와 전수 coverage 검증 문서가 없었다.

---

## 1. 구현 내용

### 1.1 생성한 runbook 세트
1. `docs/portfolio/study/32_project_runbook_index.md`
2. `docs/portfolio/study/32_product_planning_and_evolution_runbook.md`
3. `docs/portfolio/study/32_system_architecture_and_code_map_runbook.md`
4. `docs/portfolio/study/32_trading_strategy_risk_and_execution_runbook.md`
5. `docs/portfolio/study/32_ai_agents_data_and_tech_stack_runbook.md`
6. `docs/portfolio/study/32_deployment_operations_monitoring_runbook.md`
7. `docs/portfolio/study/32_testing_verification_and_future_roadmap_runbook.md`
8. `docs/portfolio/study/32_file_inventory_and_reference_map_runbook.md`

### 1.2 문서별 핵심 역할
- 인덱스:
  - 읽는 순서와 핵심 개념, 학습 경로 제공
- 기획/변천사:
  - Week 1~8부터 현재 운영 구조까지 서사 정리
- 시스템 구조/코드 맵:
  - 디렉터리/파일 책임과 런타임 흐름 설명
- 전략/리스크/실행:
  - 레짐, 진입/청산, 사이징, 리스크 관리자 설명
- AI/데이터/기술 스택:
  - AI 계층, 데이터 모델, 기술 선택 이유와 대안 비교 설명
- 배포/운영/모니터링:
  - OCI Compose, 모니터링, 백업, 원격 접근, 장애 대응 설명
- 테스트/검증/로드맵:
  - 테스트 체계, CI, 남은 과제, 향후 방향 설명
- 파일 인벤토리:
  - 폴더/파일 단위 참조 맵 제공

### 1.3 함께 반영한 문서
- `.gitignore`
  - `docs/runbooks/` 전체 ignore 정책을 다시 완전 복원하고, 개인 학습용 문서는 기존 ignore 대상인 `docs/portfolio/` 아래로 이동
- `README.md`
  - private study 문서를 공식 공개 문서처럼 보이게 하던 32번 runbook 안내 제거
- `docs/checklists/remaining_work_master_checklist.md`
  - 32 상태 `done`은 유지하되, 산출물 성격을 `개인 학습용 비공개 문서`로 명시
- `docs/work-plans/32_project_end_to_end_runbook_documentation_plan.md`
  - private study 경로 및 공개/비공개 기준 변경 이력 반영

---

## 2. 설계 선택과 대안 비교

### 2.1 최종 선택
- **주제별 분리 runbook 세트 + 인덱스 문서 + 파일 인벤토리 appendix**

### 2.2 고려한 대안
1. 모든 내용을 하나의 초장문 문서에 몰아넣는 방식
2. 기존 `work-plan/work-result/troubleshooting`를 그대로 참고하라고만 하는 방식
3. 주제별 문서로 나누고 학습 순서를 제공하는 방식

### 2.3 왜 현재 선택이 더 적합했나
- 한 문서에 다 넣으면 수정/탐색/링크 유지가 어렵다.
- 기존 문서만 참고하게 두면 사용자가 원하는 "쉽고 체계적인 전체 설명"을 충족하지 못한다.
- 주제별 분리 문서는 유지보수와 학습 동선을 동시에 개선한다.

---

## 3. 정량 개선 증빙

### 3.1 측정 기준
- 측정 시각:
  - 2026-03-15
- 측정 대상:
  - 신규 private study 문서 8종
  - `.gitignore`/README/체크리스트/계획서 동기화
- 성공 기준:
  1. `docs/portfolio/study/32_*` 세트가 실제로 존재할 것
  2. 전체 프로젝트 이해를 위한 인덱스/기획/구조/전략/AI/운영/검증/파일맵 문서가 모두 있을 것
  3. 쉬운 설명, 설계 이유, 대안 비교, 코드/파일 참조가 포함될 것
  4. README와 체크리스트가 같은 변경 세트에서 동기화될 것
  5. 개인 학습용 문서가 공개 README에서 직접 링크되지 않고, ignore 정책과 충돌하지 않아야 할 것

### 3.2 측정 명령
```bash
ls docs/portfolio/study/32_* | sort
wc -l docs/portfolio/study/32_*
rg -l "일반인용 쉬운 설명|비개발자용 쉬운 설명|쉬운 설명" docs/portfolio/study/32_* | wc -l
rg -l "대안|대안 비교|고려할 수 있었던 대안" docs/portfolio/study/32_* | wc -l
rg -l "핵심 코드|핵심 참조|핵심 파일|대표 파일|관련 파일" docs/portfolio/study/32_* | wc -l
rg -n "docs/portfolio/study/32_|개인 학습용 비공개|private study" docs/work-plans/32_project_end_to_end_runbook_documentation_plan.md docs/work-result/32_project_end_to_end_runbook_documentation_result.md
git check-ignore -v docs/portfolio/study/32_project_runbook_index.md
git check-ignore -v docs/runbooks
```

### 3.3 Before / After 비교표

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 통합 runbook 문서 수 | 0 | 8 | +8 | 측정 불가(분모 0) |
| 신규 runbook 총 라인 수 | 0 | 2865 | +2865 | 측정 불가(분모 0) |
| 쉬운 설명 포함 문서 수 | 0 | 7 | +7 | 측정 불가(분모 0) |
| 대안/비교 포함 문서 수 | 0 | 4 | +4 | 측정 불가(분모 0) |
| 코드/파일 참조 섹션 포함 문서 수 | 0 | 6 | +6 | 측정 불가(분모 0) |
| README의 32 study 문서 직접 참조 수 | 0 | 0 | 0 | 0.0 |
| ignore 정책과 충돌 없는 private study 문서 수 | 0 | 8 | +8 | 측정 불가(분모 0) |

### 3.4 해석
- 단일 문서 부재 상태에서, 현재는 프로젝트 전체를 설명하는 8개 문서 세트가 생겼다.
- 최소 2865라인 분량으로 프로젝트의 기획, 구조, 전략, AI, 운영, 검증, 파일 맵을 포괄한다.
- 비개발자 설명과 기술적 설명을 동시에 제공하는 구조가 생겼다.

---

## 4. 검증 결과

### 4.1 정적 검증
- 확인 내용:
  - 신규 문서 8개 존재
  - 문서별 핵심 키워드 존재
  - runbook 간 상호 참조 존재
  - `docs/portfolio/study/` 문서가 ignore 대상 안에 머무르면서도 로컬 학습용 경로로 정리됐는지 확인
  - README가 private study 문서를 공개 링크로 노출하지 않는지 확인
- 결과:
  - 모두 확인 완료

### 4.2 내용 검증
- 검토한 입력:
  - `docs/PROJECT_CHARTER.md`
  - `README.md`
  - 초기 주차 계획 문서
  - 최근 핵심 result/troubleshooting 문서
  - `src/`, `deploy/`, `scripts/`, `tests/` 주요 코드/설정 파일
- 결과:
  - 현재 운영 기준과 코드 위치를 기준으로 설명을 작성했다.
  - 과거 계획과 현재 운영이 다른 부분은 가능한 한 분리해 설명했다.

### 4.3 테스트 검증
- 자동 테스트:
  - 미실행
- 사유:
  - 이번 작업은 코드 동작 변경이 아닌 문서화 작업이다.
- 대체 검증:
  - `rg`, `wc`, `ls`, 문서 상호 참조 및 실제 파일 존재 여부 점검

---

## 5. README / 체크리스트 동기화

### 5.1 README 동기화 여부
- 동기화 완료
- 반영 내용:
  - private study 문서 링크 제거

### 5.2 체크리스트 동기화 여부
- 동기화 완료
- 반영 내용:
  - `32` 상태를 `done`으로 전환
  - result 문서 링크 연결

### 5.3 README 동기화 검증 명령
```bash
rg -n "32_project_runbook_index|32_file_inventory_and_reference_map_runbook|통합 Runbook" README.md
```

### 5.4 Git 추적성 동기화 여부
- 동기화 완료
- 반영 내용:
  - `docs/runbooks/`는 다시 완전 ignore 상태로 복원했다.
  - 32번 문서는 `docs/portfolio/study/` 하위의 개인 학습용 비공개 문서로 이동했다.
- 검증 명령:
```bash
git check-ignore -v docs/portfolio/study/32_project_runbook_index.md
git check-ignore -v docs/runbooks
```

---

## 6. 계획 대비 리뷰

- 계획과 일치한 부분:
  - 저장소 전수 검토
  - 다중 runbook 세트 작성
  - 쉬운 설명/설계 이유/대안 비교/코드 위치 보강
  - coverage 검증
- 계획에서 변경된 부분:
  - 파일 추적성을 높이기 위해 `32_file_inventory_and_reference_map_runbook.md` appendix를 추가했다.
  - 사용자 요청에 따라 산출물을 공식 공개 runbook이 아니라 `docs/portfolio/study/32_*`의 개인 학습용 비공개 문서로 재배치했다.
  - 그에 맞춰 `.gitignore`는 `docs/runbooks/` 완전 ignore로 복원하고, README의 공개 링크는 제거했다.
- 계획 대비 효과:
  - 사용자 요구였던 "생성된 파일들만 확인해도 프로젝트 전체를 이해할 수 있게"라는 목표에 더 가까워졌다.

---

## 7. 남은 리스크 / 한계

- 리스크:
  - 저장소가 계속 변하므로 이 private study 문서 세트도 후속 작업에서 함께 갱신돼야 한다.
- 한계:
  - 모든 파일의 줄 단위 상세 설명까지 넣지는 않았고, 대신 도메인과 파일 묶음 중심으로 정리했다.
  - 네트워크/운영 런타임 실제 재검증은 문서 작업 범위 밖이다.
- 후속 권장:
  1. 주요 main task 완료 시 관련 runbook 업데이트를 결과 문서 체크리스트에 포함
  2. `23` Next.js 이관 이후 UI 관련 runbook 보강
  3. `21-09` 후속 live trading 단계가 진행되면 ledger/reconciliation runbook 추가 확장

---

## 8. 결론

이번 작업으로 CoinPilot는 "개별 작업 문서는 많지만 전체를 한 번에 설명하기 어려운 저장소"에서,  
"기획부터 현재 운영과 향후 과제까지 개인 학습용으로 종합 정리된 study 문서 세트가 있는 저장소"로 한 단계 정리되었다.
