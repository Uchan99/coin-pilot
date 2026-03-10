# 99-05. AI Engineer / MLOps 지원용 포트폴리오·자기소개 패키지 결과

작성일: 2026-03-10
작성자: Codex
관련 계획서: `docs/work-plans/99-05_ai_engineer_mlop_portfolio_and_self_intro_pack_plan.md`
상태: Verified
완료 범위: 문서 산출물 7종 + 추적 문서 동기화
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - AI Engineer / MLOps 지원용 포트폴리오 원문 문서 1종 작성
  - 면접/학습용 꼬리질문 해설 문서 1종 작성
  - 전체 시스템 아키텍처 레퍼런스 문서 1종 작성
  - 데이터 플로우 레퍼런스 문서 1종 작성
  - 서비스 플로우 레퍼런스 문서 1종 작성
  - 제출용 1페이지 자기소개 문서 1종 작성
  - AI Engineer / MLOps 직무별 프로젝트 소개문 분리본 1종 작성
  - plan/checklist 상태 동기화
- 목표(요약):
  - 산재한 운영 문서/코드/정량 결과를 지원서에 바로 활용 가능한 형태로 재구성
- 이번 구현이 해결한 문제(한 줄):
  - CoinPilot의 강점을 “운영 가능한 AI 시스템 설계/관측/실험/복구” 관점으로 바로 설명할 수 있는 패키지를 만들었다.
- 해결한 문제의 구체 정의(필수: 증상/영향/재현 조건):
  - 증상: README/result/code는 풍부하지만 지원서용 서사와 직무별 포지셔닝 문서가 없었다.
  - 영향: 자기소개서/포트폴리오 작성 시 같은 자료를 반복 탐색해야 했고, 수익률 중심 또는 기능 나열형 서술로 흐를 위험이 있었다.
  - 재현 조건: AI Engineer / MLOps 지원용 프로젝트 설명을 새로 작성하려는 상황
- 기존 방식/상태(Before) 기준선 요약(필수):
  - 운영 원문 문서 다수는 존재했지만, 지원서용 재구성 문서는 0개였다.

---

## 2. 구현 내용(핵심 위주)
### 2.1 포트폴리오/자기소개 원문 문서 작성
- 파일/모듈:
  - `docs/portfolio/ai_engineer_mlop_self_intro_and_project_showcase.md`
- 변경 내용:
  - 프로젝트 한 줄 소개, 자기소개서용 서술 예시, AI Engineer/MLOps 포지셔닝, 기술 스택 선택 이유, 정량 근거 표, 실거래 서술 가이드, 강한 문장 예시를 구조화
- 효과/의미:
  - 사용자가 좋은 부분만 골라 즉시 지원서/포트폴리오에 재사용할 수 있는 원문을 확보했다.

### 2.2 면접/학습용 해설 문서 작성
- 파일/모듈:
  - `docs/portfolio/ai_engineer_mlop_interview_study_guide.md`
- 변경 내용:
  - 꼬리질문 예상 답변, 쉬운 비유, 왜 해당 스택을 썼는지, 어떤 대안을 버렸는지, 면접에서 피해야 할 표현, 외워야 할 정량 수치를 정리
- 효과/의미:
  - 지원서용 문장을 “내가 진짜 이해하고 말할 수 있는 설명”으로 바꾸는 학습 자료를 제공했다.

### 2.3 추적 문서 동기화
- 파일/모듈:
  - `docs/work-plans/99-05_ai_engineer_mlop_portfolio_and_self_intro_pack_plan.md`
  - `docs/checklists/remaining_work_master_checklist.md`
- 변경 내용:
  - 승인 정보/결과 링크/상태를 동기화
- 효과/의미:
  - 메타 문서 작업도 repo 운영 규칙과 같은 방식으로 추적 가능하게 했다.

### 2.4 아키텍처 / 데이터 플로우 / 서비스 플로우 레퍼런스 문서 작성
- 파일/모듈:
  - `docs/portfolio/coinpilot_system_architecture_reference.md`
  - `docs/portfolio/coinpilot_data_flow_reference.md`
  - `docs/portfolio/coinpilot_service_flow_reference.md`
- 변경 내용:
  - 실제 코드 경로(`collector`, `bot`, `agents`, `analytics`, `dashboard`, `mobile`, `discord_bot`, `notification`, `compose`)를 2~3회 교차 확인한 뒤, 포트폴리오 부록으로 제출 가능한 기술 문서 3종을 작성했다.
  - 현재 구현 상태와 "Upbit 실거래 연동 가정"을 분리 기술해 과장을 피하면서도 확장 가능성을 설명할 수 있게 정리했다.
- 효과/의미:
  - 사용자가 면접에서 단순 기능 나열이 아니라 시스템 구조, 데이터 저장 경계, read/write 분리, observability 계층, 실거래 전환 경계를 설명할 수 있게 됐다.

### 2.5 제출용 1페이지 자기소개 / 직무별 소개문 작성
- 파일/모듈:
  - `docs/portfolio/ai_engineer_mlop_one_page_self_intro.md`
  - `docs/portfolio/role_specific_project_intro_ai_engineer_vs_mlops.md`
- 변경 내용:
  - 바로 제출 가능한 1페이지 자기소개 초안과, 같은 CoinPilot 프로젝트를 AI Engineer / MLOps 관점으로 나눠 설명하는 분리본을 작성했다.
  - 한 문서 안에서 과도하게 섞였던 메시지를 "공통 서사"와 "직무별 강조점"으로 분리했다.
- 효과/의미:
  - 사용자는 지원 직무에 따라 문장을 다시 처음부터 쓰지 않고, 필요한 버전을 선택해서 바로 재가공할 수 있게 됐다.

---

## 3. 변경 파일 목록
### 3.1 수정
1. `docs/work-plans/99-05_ai_engineer_mlop_portfolio_and_self_intro_pack_plan.md`
2. `docs/checklists/remaining_work_master_checklist.md`
3. `docs/portfolio/ai_engineer_mlop_self_intro_and_project_showcase.md`
4. `docs/portfolio/ai_engineer_mlop_interview_study_guide.md`
5. `docs/portfolio/coinpilot_system_architecture_reference.md`
6. `docs/portfolio/coinpilot_data_flow_reference.md`
7. `docs/portfolio/coinpilot_service_flow_reference.md`

### 3.2 신규
1. `docs/portfolio/ai_engineer_mlop_self_intro_and_project_showcase.md`
2. `docs/portfolio/ai_engineer_mlop_interview_study_guide.md`
3. `docs/portfolio/coinpilot_system_architecture_reference.md`
4. `docs/portfolio/coinpilot_data_flow_reference.md`
5. `docs/portfolio/coinpilot_service_flow_reference.md`
6. `docs/portfolio/ai_engineer_mlop_one_page_self_intro.md`
7. `docs/portfolio/role_specific_project_intro_ai_engineer_vs_mlops.md`
8. `docs/work-result/99-05_ai_engineer_mlop_portfolio_and_self_intro_pack_result.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점:
  - 문서 작업이므로 파일 삭제/되돌리기만 수행하면 된다.

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `rg -n "AI Engineer|MLOps|LangChain|LangGraph|RAG|Grafana|Loki|Prometheus|Rule Funnel|Strategy Feedback" docs/portfolio/ai_engineer_mlop_self_intro_and_project_showcase.md`
  - `rg -n "꼬리질문|쉽게 설명|왜|대안|실패|수치" docs/portfolio/ai_engineer_mlop_interview_study_guide.md`
  - `rg -n "아키텍처|LangGraph|Rule Engine|Risk Manager|실거래 가정|Executor" docs/portfolio/coinpilot_system_architecture_reference.md`
  - `rg -n "market_data|trading_history|rule_funnel_events|llm_usage_events|Redis|source of truth" docs/portfolio/coinpilot_data_flow_reference.md`
  - `rg -n "매수|매도|Scheduler|Discord|n8n|실거래" docs/portfolio/coinpilot_service_flow_reference.md`
  - `rg -n "1페이지|자기소개|운영 가능한 AI 시스템|CoinPilot" docs/portfolio/ai_engineer_mlop_one_page_self_intro.md`
  - `rg -n "AI Engineer|MLOps|직무별|프로젝트 소개문" docs/portfolio/role_specific_project_intro_ai_engineer_vs_mlops.md`
- 결과:
  - 요구한 핵심 기술 스택, 꼬리질문 학습 포인트, 구조/데이터/서비스 흐름 문서가 모두 포함됨을 정적 확인 가능

### 5.2 테스트 검증
- 실행 명령:
  - 별도 테스트 없음(문서 작업)
- 결과:
  - 테스트 대상 없음

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법:
  - 문서 파일 직접 열람
- 결과:
  - 운영 반영 대상 없음

### 5.4 정량 개선 증빙(필수)
- 측정 기간/표본:
  - 2026-03-10 기준 repo 문서/코드/결과 문서 전반
- 측정 기준(성공/실패 정의):
  - 성공: 지원서용 원문 문서 1종 + 학습용 문서 1종 + 정량 근거 포함
  - 실패: 기술 스택 선택 이유/정량 수치/직무 포지셔닝 중 하나라도 누락
- 데이터 출처(SQL/로그/대시보드/스크립트):
  - `README.md`, `PROJECT_CHARTER.md`, `21-03/21-04/21-05/21-07/21-08/24/27/29/29-01/30` result 문서, 대표 코드 파일
- 재현 명령:
  - `rg -n "AI Engineer|MLOps|정량|LangGraph|Rule Funnel|Loki" docs/portfolio`
  - `rg -n "아키텍처|데이터 플로우|서비스 플로우|실거래 가정" docs/portfolio`
- Before/After 비교표:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 지원서용 포트폴리오 원문 문서 수 | 0 | 1 | +1 | N/A |
| 면접/학습용 해설 문서 수 | 0 | 1 | +1 | N/A |
| 구조 레퍼런스 문서 수(아키텍처/데이터/서비스) | 0 | 3 | +3 | N/A |
| 제출용 자기소개/직무별 소개문 문서 수 | 0 | 2 | +2 | N/A |
| 직무별 포지셔닝 문서화(AI Engineer/MLOps) | 0 | 2개 관점 명시 | +2 | N/A |
| 정량 근거 표 포함 문서 수 | 0 | 1 | +1 | N/A |

- 정량 측정 불가 시(예외):
  - 불가 사유:
    - 문서 품질의 설득력 자체는 정량화하기 어렵다.
  - 대체 지표:
    - 기술 스택/수치/꼬리질문/직무 포지셔닝 섹션 존재 여부
  - 추후 측정 계획/기한:
    - 실제 지원 후 면접/서류 피드백을 받으면 표현 보강 가능

---

## 6. 배포/운영 확인 체크리스트(필수)
1. `docs/portfolio/ai_engineer_mlop_self_intro_and_project_showcase.md` 존재 확인
2. `docs/portfolio/ai_engineer_mlop_interview_study_guide.md` 존재 확인
3. `docs/portfolio/coinpilot_system_architecture_reference.md` 존재 확인
4. `docs/portfolio/coinpilot_data_flow_reference.md` 존재 확인
5. `docs/portfolio/coinpilot_service_flow_reference.md` 존재 확인
6. `docs/portfolio/ai_engineer_mlop_one_page_self_intro.md` 존재 확인
7. `docs/portfolio/role_specific_project_intro_ai_engineer_vs_mlops.md` 존재 확인
8. `docs/checklists/remaining_work_master_checklist.md`에 99-05 상태/결과 링크 반영 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 지원서용 원문과 면접용 학습 노트를 분리했다.
- 고려했던 대안:
  1. 포트폴리오 문서 1개만 작성
  2. 자기소개 문장만 짧게 정리
  3. 원문 문서 + 학습용 꼬리질문 문서 분리(채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1. 원문 문서는 바로 복사/재가공하기 좋다.
  2. 학습 노트는 암기형이 아니라 이해형 면접 준비에 적합하다.
  3. 과장/오해를 줄이고, 진행 중/완료 항목을 분리해 설명하기 쉬워진다.
- 트레이드오프(단점)와 보완/완화:
  1. 문서 수가 늘어나 관리 비용이 생긴다.
  2. 대신 포트폴리오 제출용과 면접 학습용의 목적이 달라 분리 가치가 더 크다.

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  - 해당 없음(문서 작업)
- 주석에 포함한 핵심 요소:
  - 문서에 기술 선택 이유, 대안, 실패/한계, 정량 근거를 한국어로 상세 정리

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - 포트폴리오 문서 1종 + 학습용 문서 1종 작성
  - 정량 근거와 직무 포지셔닝 포함
  - 실거래 연동을 선행 필수 조건으로 두지 않음
- 변경/추가된 부분(왜 바뀌었는지):
  - 사용자 요청에 따라 `docs/portfolio/` 하위 구조로 산출물을 분리했다.
  - 꼬리질문 답변/쉬운 설명/면접 주의점 섹션을 계획보다 더 강화했다.
  - 추가 요청에 따라 전체 아키텍처, 데이터 플로우, 서비스 플로우 문서를 별도 레퍼런스로 작성했다.
  - 이 과정에서 현재 코드 기준 `PaperTradingExecutor`와 "실거래 Upbit 연동 가정"을 명시적으로 분리해 서술했다.
  - 이어서 제출용 1페이지 자기소개와 직무별 프로젝트 소개문을 별도 문서로 분리해, 서류 제출/면접 준비/직무 맞춤 재사용 경로를 더 명확히 했다.
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - CoinPilot를 AI Engineer / MLOps 포지션에 맞게 설명할 수 있는 문서 패키지와 구조 레퍼런스가 함께 준비됐다.
- 후속 작업(다음 plan 번호로 넘길 것):
  1. 필요 시 백엔드/플랫폼 직무용 파생 버전 추가
  2. 실거래 안정화 후 “실거래 운영 증빙” 부록 추가 가능

---

## 12. References
- [PROJECT_CHARTER.md](/home/syt07203/workspace/coin-pilot/docs/PROJECT_CHARTER.md)
- [README.md](/home/syt07203/workspace/coin-pilot/README.md)
- [DEEP_LEARNING_GUIDE.md](/home/syt07203/workspace/coin-pilot/docs/DEEP_LEARNING_GUIDE.md)
- [21-03 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-03_ai_decision_model_canary_experiment_result.md)
- [21-04 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-04_llm_token_cost_observability_dashboard_result.md)
- [21-05 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md)
- [21-07 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-07_oci_log_observability_loki_promtail_result.md)
- [21-08 result](/home/syt07203/workspace/coin-pilot/docs/work-result/21-08_grafana_loki_log_dashboard_panelization_result.md)
- [24 result](/home/syt07203/workspace/coin-pilot/docs/work-result/24_discord_mobile_chatbot_query_result.md)
- [29-01 result](/home/syt07203/workspace/coin-pilot/docs/work-result/29-01_bull_regime_rule_funnel_observability_and_review_automation_result.md)
- [30 result](/home/syt07203/workspace/coin-pilot/docs/work-result/30_strategy_feedback_automation_spec_first_result.md)
- [coinpilot_system_architecture_reference.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/coinpilot_system_architecture_reference.md)
- [coinpilot_data_flow_reference.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/coinpilot_data_flow_reference.md)
- [coinpilot_service_flow_reference.md](/home/syt07203/workspace/coin-pilot/docs/portfolio/coinpilot_service_flow_reference.md)
