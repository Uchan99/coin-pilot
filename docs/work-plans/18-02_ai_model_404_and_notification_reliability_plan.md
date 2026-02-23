# 18-02. AI 모델 404 및 Discord 알림 누락 복구 작업 계획

**작성일**: 2026-02-23  
**작성자**: Codex (GPT-5)  
**상태**: Verified  
**관련 계획 문서**: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`  

---

## 0. 트리거(Why started)
- 운영 로그에서 `model: claude-3-5-haiku-20241022` 404로 AI 판단이 연속 REJECT됨.
- 동일 시점에 REJECT Discord 알림이 일부/다수 누락됨.
- 거래 판단 신뢰성과 운영 관측성(알림)이 동시에 깨져 즉시 대응이 필요함.

## 1. 문제 요약
- 증상:
  - AI Analyst 단계에서 모델 not found(404) 발생
  - REJECT 이벤트가 Discord에 전송되지 않음
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: AI 의사결정 품질 저하(사실상 전량 REJECT)
  - 운영: 이상 상황 알림 누락으로 대응 지연
- 재현 조건:
  - `LLM_MODEL=claude-3-5-haiku-20241022`
  - bot 컨테이너 `N8N_URL=http://localhost:5678`

## 2. 원인 분석
- 가설:
  1) Anthropic 계정 기준 사용 가능한 모델 목록과 env 모델 ID 불일치
  2) bot 컨테이너에서 localhost를 n8n endpoint로 사용해 연결 실패
- 조사 과정:
  - bot env/로그 확인
  - Anthropic `/v1/models` 조회로 사용 가능 모델 식별
- Root cause:
  - 모델 ID가 현재 계정에서 미지원(404)
  - 컨테이너 내부 localhost 오설정으로 webhook 연결 실패

## 3. 대응 전략
- 단기 핫픽스:
  - 운영 `.env`의 `LLM_MODEL`, `N8N_URL` 즉시 교정
- 근본 해결:
  - compose 기본값/예시값을 현재 유효 모델 기준으로 정정
  - notification 전송 경로에 컨테이너 환경 fallback 추가
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - webhook 전송 시 endpoint/오류 원인 로그를 명확히 남겨 재발 시 즉시 식별

## 4. 구현/수정 내용
- 변경 파일:
  - `src/common/notification.py`
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `deploy/cloud/oci/.env.example`
  - `deploy/cloud/oci/.env`(운영 런타임 값)
- DB 변경(있다면):
  - 없음
- 주의점:
  - bot 재시작 전후 env 값 차이 확인 필요

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - AI 판단 로그에서 404 소멸
  - REJECT/CONFIRM 이벤트 Discord 수신
- 회귀 테스트:
  - n8n webhook 5종(trade/risk/daily/ai/weekly) 호출 성공
- 운영 체크:
  - bot env에 `N8N_URL=http://n8n:5678`
  - bot env에 유효 `LLM_MODEL` 반영

## 6. 롤백
- 코드 롤백:
  - 해당 파일 revert 후 bot 재배포
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획 + 결과 문서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 원칙 변경 없음(불필요)

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) startup preflight에 Anthropic 모델 가용성 점검 옵션 추가 검토
  2) n8n endpoint localhost 오설정 탐지 경고 추가 검토

## 9. 변경 이력
- 2026-02-23:
  - 계획 수립 시점에는 AI 404 + 알림 누락을 1차 범위로 정의.
  - 구현 중 compose 이미지 핀 고정에 따른 데이터 호환 이슈(Timescale/Redis) 발견.
  - 운영 연속성 유지를 위해 DB/Redis 이미지 버전 정합성 복구를 동일 작업 범위에 포함.
