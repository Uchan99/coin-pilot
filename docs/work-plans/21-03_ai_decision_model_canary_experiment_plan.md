# 21-03. AI Decision 모델 카나리 실험(haiku ↔ gpt-4o-mini) 계획

**작성일**: 2026-02-26  
**작성자**: Codex  
**상태**: Approval Pending  
**관련 계획 문서**: `docs/work-plans/21_live_trading_transition_1m_krw_plan.md`, `docs/work-plans/21-02_llm_model_haiku_vs_gpt4omini_comparison_plan.md`  
**관련 결과 문서**: `docs/work-result/21-02_llm_model_haiku_vs_gpt4omini_comparison_result.md`  
**승인 정보**: 승인자 / 승인 시각 / 승인 코멘트  

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - `21-02` 분석 결과, 비용은 `gpt-4o-mini`가 유리하나 실시간 품질은 A/B 실측이 필요하다는 결론이 나옴.
- 왜 즉시 대응이 필요했는지:
  - 실거래 전환 전에 모델 전환 리스크를 paper 운영 구간에서 계량적으로 검증해야 함.

## 1. 문제 요약
- 증상:
  - 현재 AI Decision(Analyst/Guardian)은 Anthropic 단일 경로라 모델 대조 실험이 어려움.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: AI Decision 경로(Analyst/Guardian)
  - 리스크: 모델 전환 시 파싱 실패/의사결정 분포 왜곡 가능성
  - 데이터: `agent_decisions`의 모델별 결과 집계 필요
  - 비용: 일일/월간 LLM 비용 차이 검증 필요
- 재현 조건:
  - 실시간 신호 유입 시 모델 라우팅이 단일 경로로 고정된 상태

## 2. 원인 분석
- 가설:
  - 모델 공급자 분리/카나리 라우팅/관측 지표가 코드 경로에 없어서 실험이 불가능함.
- 조사 과정:
  - `src/agents/factory.py`가 `ChatAnthropic` 단일 경로임을 확인.
  - `agent_decisions.model_used`는 존재하나 모델별 운영 리포트 기준이 문서화되지 않음.
- Root cause:
  - "실험 가능한 라우팅 계층 + 관측 기준 + 운영 롤백 절차"가 부재.

## 3. 대응 전략
- 단기 핫픽스:
  - 없음(기능 추가 중심)
- 근본 해결:
  - AI Decision 경로에 provider/model 분기와 카나리 비율 라우팅을 추가
  - 모델별 품질/비용 지표를 동일 기간 집계하도록 운영 스크립트/문서 보강
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - Kill switch: `AI_CANARY_ENABLED=false` 즉시 원복
  - 카나리 비율 상한: 기본 10%, 최대 20%
  - timeout/파싱 실패 급증 시 자동 카나리 중지 기준 정의

## 4. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **대안 B 채택**: Analyst/Guardian 전용 provider/model 분리 + 비율 카나리 라우팅

- 고려 대안:
  1) 전역 LLM provider를 OpenAI로 일괄 전환
  2) Analyst/Guardian만 분리하고 나머지 경로는 유지 (채택)
  3) Shadow mode(결정은 기존, 신규 모델은 병렬 관측만) 후 2단계 전환

- 대안 비교:
  1) 일괄 전환:
    - 장점: 구현 단순
    - 단점: 영향 범위 과대(챗봇/RAG/SQL 경로까지 변경)
  2) Analyst/Guardian 분리(채택):
    - 장점: 실시간 의사결정 경로만 정밀 제어 가능
    - 단점: 설정 변수 증가, 라우팅 코드 복잡도 소폭 증가
  3) Shadow mode:
    - 장점: 거래 영향 최소화
    - 단점: 비용 2배 수준 증가 + 구현 난이도 상승

## 5. 구현/수정 내용 (예정)
- 변경 파일:
  1) `src/agents/factory.py`
  2) `src/agents/runner.py` (모델/provider 기록 필드 보강 필요 시)
  3) `src/agents/analyst.py` / `src/agents/guardian.py` (라우팅 인자 전달 필요 시)
  4) `deploy/cloud/oci/docker-compose.prod.yml`
  5) `deploy/cloud/oci/.env.example`
  6) `scripts/ops/` (모델별 집계 보조 스크립트 추가 시)
  7) `docs/work-result/21-03_ai_decision_model_canary_experiment_result.md` (신규)

- 설정 변수(초안):
  - `AI_DECISION_PRIMARY_PROVIDER=anthropic`
  - `AI_DECISION_PRIMARY_MODEL=claude-haiku-4-5-20251001`
  - `AI_CANARY_ENABLED=true|false`
  - `AI_CANARY_PROVIDER=openai`
  - `AI_CANARY_MODEL=gpt-4o-mini`
  - `AI_CANARY_PERCENT=10`

- 라우팅 정책(초안):
  - 신호 단위 deterministic hash로 canary 대상 결정(재현 가능성 확보)
  - canary 대상만 `gpt-4o-mini`, 나머지는 기존 Haiku

## 6. 검증 기준
- 재현 케이스에서 해결 확인:
  1) canary=10% 설정 시 `agent_decisions.model_used`에 두 모델이 혼재 기록
  2) canary=0% 또는 disabled 시 기존 모델만 기록
- 회귀 테스트:
  - 기존 AI Decision 타임아웃/파싱 실패율이 임계값 내 유지
- 운영 체크:
  - 모델별 지표(건수/CONFIRM률/REJECT률/timeout/boundary_audit) 24h 비교
  - 모델별 비용 추정(토큰/호출수 기반) 산출

## 7. 성공/중단 기준 (실험 게이트)
- 성공 기준(24h 1차):
  1) 파싱 실패율 악화 없음(기존 대비 +2%p 이내)
  2) timeout 비율 악화 없음(기존 대비 +2%p 이내)
  3) 비용 절감 효과 확인(`gpt-4o-mini` 구간)
- 중단 기준(즉시 롤백):
  1) 오류/timeout 급증
  2) CONFIRM/REJECT 분포 급변(운영 임계 초과)
  3) Discord/DB 기록 누락 발생

## 8. 롤백
- 코드 롤백:
  - 카나리 라우팅 커밋 revert
- 운영 롤백:
  - `AI_CANARY_ENABLED=false` 적용 후 bot 재기동
  - 필요 시 `AI_DECISION_PRIMARY_PROVIDER=anthropic` 강제
- 데이터/스키마 롤백:
  - 스키마 변경 없음(예정)

## 9. 문서 반영
- work-plan/work-result 업데이트:
  - 본 plan 생성 후 승인 대기
  - 구현 완료 후 `docs/work-result/21-03_ai_decision_model_canary_experiment_result.md` 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 기본 정책 변경 시(실시간 기본 모델 교체 확정 시) Charter changelog 반영
  - 카나리 실험 단계는 운영 실험으로 Charter 변경 없이 진행 가능

## 10. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) `21-04` 모델별 토큰/비용 대시보드 구축
  2) 카나리 결과 기반 기본 모델 확정(`anthropic` 유지 vs `openai` 전환)
  3) 필요 시 shadow mode 확장(고위험 심볼만 병렬평가)
