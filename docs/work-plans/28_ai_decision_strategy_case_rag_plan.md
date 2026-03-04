# 28. AI Decision 전략문서/과거사례 기반 RAG 보강 계획

**작성일**: 2026-03-05  
**작성자**: Codex  
**상태**: Approval Pending  
**관련 계획 문서**: `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`, `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`  
**승인 정보**: 미승인 (메모 작성만 완료)

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - AI Decision 품질 개선 논의에서 RAG 소스 우선순위(일반 차트 이론 vs 우리 전략/사례)가 불명확했다.
- 왜 즉시 대응이 필요했는지:
  - 구현 전 방향을 고정하지 않으면 비용만 늘고 품질 개선 효과가 불확실해질 수 있다.

## 1. 문제 요약
- 증상:
  - AI Decision 판단 품질 개선 아이디어는 있으나, 어떤 지식원을 우선 연결할지 기준이 없다.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: Analyst/Guardian 판단 일관성
  - 리스크: 일반 이론 문서 과적합/잡음 증가
  - 비용: 불필요한 RAG 토큰 증가 가능성
- 재현 조건:
  - RAG 소스 선정 기준 없이 임의 문서를 주입할 때

## 2. 원인 분석
- 가설:
  - 현재 판단 품질의 병목은 일반 차트 이론 부족이 아니라, 전략 규칙 정합성과 과거 의사결정 사례 활용 부족이다.
- 조사 과정:
  - 최근 운영 논의에서 “전략 문서 + 과거 사례 우선”이 더 실용적이라는 합의 도출.
- Root cause:
  - RAG 소스 계층화 기준(우선순위/검증 지표)이 문서화되지 않음.

## 3. 대응 전략
- 단기 핫픽스:
  - 없음 (계획/기준 확정 단계)
- 근본 해결:
  - RAG 소스를 2계층으로 정의:
    1) 전략/리스크 규칙 문서(정적)
    2) 과거 의사결정 + 결과 사례(동적)
  - 일반 차트 이론/이미지는 보조 소스로만 제한
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - canary A/B로만 실험, 기준 미달 시 즉시 비활성

## 4. 구현/수정 내용 (예정)
- 변경 파일(예정):
  1) `src/agents/analyst.py`, `src/agents/guardian.py` (retrieval context 주입 지점)
  2) `src/agents/rag_agent.py` 또는 신규 모듈(전략/사례 인덱싱 분리)
  3) `scripts/ops/ai_decision_canary_report.sh` 확장(품질 지표 비교)
  4) 결과 문서/트러블슈팅 문서
- DB 변경(있다면):
  - 사례 인덱스 저장 테이블(필요 시)
- 주의점:
  - 판단 경로 지연 증가(토큰/latency) 관리 필요

## 5. 검증 기준 (예정)
- 재현 케이스에서 해결 확인:
  1) parse_fail/timeout 악화 없음
  2) CONFIRM/REJECT 분포 급변 없음
  3) 샘플 확보 후 거래 성과 지표(기대값/drawdown) 악화 없음
- 회귀 테스트:
  - 기존 AI Decision 경로 테스트 + RAG 비활성 fallback 테스트
- 운영 체크:
  - canary 기간(24~72h) 품질/비용 리포트 비교

## 6. 롤백
- 코드 롤백:
  - RAG 주입 기능 revert
- 데이터/스키마 롤백:
  - 인덱스/메타 테이블 비활성 또는 drop

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 승인 후 구현 시 result 문서 별도 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 판단 정책(공식) 변경 시 Charter changelog 반영

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) 전략 문서 변경 시 RAG 인덱스 재생성 절차 자동화
  2) 사례 품질 라벨링 규칙(성공/실패) 표준화
