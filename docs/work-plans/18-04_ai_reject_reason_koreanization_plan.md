# 18-04. AI REJECT 사유 문구 한국어화 작업 계획

**작성일**: 2026-02-23  
**작성자**: Codex (GPT-5)  
**상태**: Investigating  
**관련 계획 문서**: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`  

---

## 0. 트리거(Why started)
- Discord AI Decision 메시지에 REJECT 사유가 영어로 노출됨.
- 운영 메시지 가독성/일관성(한국어) 요구와 불일치.

## 1. 문제 요약
- 증상:
  - `Analyst reasoning violated rule boundary after retry ...` 영어 문구 노출
- 영향 범위(기능/리스크/데이터/비용):
  - 기능 영향 없음(가드레일 자체는 정상)
  - 운영 가독성 저하
- 재현 조건:
  - Analyst가 Rule boundary 재위반 시 강제 REJECT 경로

## 2. 원인 분석
- 가설:
  1) analyst node 강제 REJECT reason 문자열 하드코딩
- 조사 과정:
  - `src/agents/analyst.py` 반환 reason 확인
- Root cause:
  - 코드 문자열이 영어로 고정됨

## 3. 대응 전략
- 단기 핫픽스:
  - 영어 reason 문자열을 한국어로 변경
- 근본 해결:
  - 공통 메시지 로컬라이징 정책(선택)
- 안전장치:
  - 판단 로직/가드레일 조건은 그대로 유지

## 4. 구현/수정 내용
- 변경 파일:
  - `src/agents/analyst.py`
- DB 변경(있다면):
  - 없음
- 주의점:
  - 메시지 변경만 수행, 의사결정 로직은 비변경

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - 해당 REJECT 사유가 한국어로 표시되는지 확인
- 회귀 테스트:
  - bot 컨테이너 기동 정상
  - AI decision webhook 전송 정상
- 운영 체크:
  - Discord 메시지 문구 확인

## 6. 롤백
- 코드 롤백:
  - `src/agents/analyst.py` 원복 후 bot 재시작
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획 + 결과 문서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 정책 변경 없음

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) 사용자 노출 메시지 다국어/톤 가이드 정리
