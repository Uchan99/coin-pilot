# 18-15 트러블슈팅: Analyst Rule Boundary 과잉 차단으로 인한 연속 REJECT

작성일: 2026-02-26  
상태: Resolved (Policy Changed)  
관련 계획: `docs/work-plans/18-15_analyst_boundary_audit_mode_plan.md`  
관련 결과: `docs/work-result/18-15_analyst_boundary_audit_mode_result.md`  

---

## 1. 증상
- Discord AI Decision에서 아래 문구가 연속 발생:
  - `분석가 응답이 재시도 후에도 룰 경계를 위반해 보수적으로 REJECT 처리했습니다.`
- 사용자 관측 기준 최근 10건이 동일 경계 위반 경로 REJECT로 누적됨.

## 2. 영향
- 잠재적 유효 신호가 차단되어 진입 기회 손실 가능
- Analyst 경로에서 재시도 호출이 발생해 LLM credit 추가 소모
- 운영자 관점에서 REJECT 사유 다양성이 사라져 디버깅 가치 저하

## 3. 원인
- `src/agents/analyst.py`에서 키워드 기반 경계 검사 후:
  1) 1차 위반 시 재시도
  2) 2차 위반 시 강제 REJECT(`confidence=0`)
- 프롬프트 금지 지시가 있어도 모델이 Rule 항목을 언급하는 경우가 존재.

## 4. 조치
- 정책 전환:
  - 경계 위반 시 강제 REJECT 제거
  - 경계 위반 재시도 제거
  - 경계 위반은 audit 태그로 reasoning/로그에 기록만 수행
- 프롬프트 강화:
  - 금지 항목과 허용 항목을 더 명시적으로 분리

## 5. 검증 포인트
- 경계 단어 포함 응답에서도 즉시 REJECT로 떨어지지 않는지
- Discord/DB reasoning에 boundary audit 태그가 기록되는지
- confidence<60 REJECT, timeout/파싱 실패 REJECT는 기존대로 유지되는지

## 6. 재발 방지
1. boundary audit 비율 모니터링 항목 추가
2. 필요 시 감지 로직을 "단순 언급" vs "임계치 재판단"으로 구분
3. Sonnet 전환 여부는 정책 안정화 후 비용/효율 관측으로 별도 결정

