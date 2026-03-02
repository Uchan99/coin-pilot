# 27-01. Bandit 보안 이슈(B314/B104) 및 security artifact 신뢰성 개선 계획

**작성일**: 2026-03-02  
**작성자**: Codex  
**상태**: Verified  
**관련 계획 문서**: `docs/work-plans/27_ci_pipeline_dependency_and_test_env_fix_plan.md`  
**관련 결과 문서**: `docs/work-result/27_ci_pipeline_dependency_and_test_env_fix_result.md`
**관련 트러블슈팅 문서**: `docs/troubleshooting/27-01_bandit_xml_and_bind_all_interfaces_findings.md`
**승인 정보**: 사용자 / 2026-03-02 / "승인해줄게."

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - GitHub Actions `security` job이 Bandit 단계에서 실패.
  - 감지 항목:
    1) `B314` - `xml.etree.ElementTree.fromstring` 사용 (`src/agents/news/rss_news_pipeline.py`)
    2) `B104` - `0.0.0.0` 하드코딩 바인딩 (`src/bot/main.py`)
  - 추가로 artifact 업로드 단계에서 `No files were found ...` 경고 발생.
- 왜 즉시 대응이 필요했는지:
  - CI security 게이트 실패로 main 배포 파이프라인이 차단됨.

## 1. 문제 요약
- 증상:
  - Bandit exit code 1
  - pip-audit report artifact 미생성 경고
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: CI security 실패
  - 리스크: XML 파싱 안전성/보안 정책 준수 미흡 상태
  - 데이터: 없음
  - 비용: CI 반복 실패로 운영 효율 저하
- 재현 조건:
  - 현재 `main` 기준 `CoinPilot CI` 실행 시 재현

## 2. 원인 분석
- 가설:
  1) RSS XML 파싱에 stdlib ElementTree 직접 사용
  2) bot 실행 엔트리포인트에서 all-interface 바인딩 literal 노출
  3) security 단계 실패 시 pip-audit 리포트 파일 미생성
- 조사 과정:
  - Bandit 로그 위치/라인 확인
  - `src/agents/news/rss_news_pipeline.py`, `src/bot/main.py`, `.github/workflows/ci.yml` 확인
- Root cause:
  1) XML 파싱 보안 라이브러리(`defusedxml`) 미사용
  2) 바인딩 주소를 코드 literal로 고정
  3) 리포트 생성 단계의 실패/스킵 시 업로드 경고를 흡수하는 가드 부재

## 3. 대응 전략
- 단기 핫픽스:
  1) RSS 파싱을 `defusedxml.ElementTree`로 전환
  2) bot host 바인딩을 env 기반(`BOT_HOST`)으로 변경하고 Compose에서 명시 주입
  3) security workflow에 리포트 파일 생성 가드(`touch` + `if-no-files-found: warn`) 추가
- 근본 해결:
  - 보안 스캐너(Bandit) 규칙과 런타임 설정을 분리하지 않고 코드/구성에서 일관되게 충족
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - XML 파싱 경로 테스트/기존 RSS 테스트 회귀 확인
  - workflow YAML 파싱 검증

## 4. 구현/수정 내용
- 변경 파일(예정):
  1) `src/agents/news/rss_news_pipeline.py`
  2) `requirements.txt`
  3) `requirements-bot.txt`
  4) `src/bot/main.py`
  5) `deploy/cloud/oci/docker-compose.prod.yml`
  6) `deploy/docker-compose.yml`
  7) `.github/workflows/ci.yml`
  8) `docs/troubleshooting/27-01_bandit_xml_and_bind_all_interfaces_findings.md`
  9) `docs/work-result/27_ci_pipeline_dependency_and_test_env_fix_result.md` (Phase 2 추가)
- DB 변경(있다면):
  - 없음
- 주의점:
  - `BOT_HOST` 기본값은 보안 관점 `127.0.0.1`로 두되, Compose에서 `0.0.0.0`을 주입해 서비스 통신 호환성 유지

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  1) Bandit `B314`, `B104` 미검출
  2) security job artifact 경고 미발생
- 회귀 테스트:
  - `tests/agents/test_rss_news_pipeline.py` 통과
  - 기존 CI 대상 pytest 셋 통과
- 운영 체크:
  - bot 컨테이너 기동 후 `/health` 정상
  - Prometheus `coinpilot-core` target UP 유지

## 6. 롤백
- 코드 롤백:
  - 변경 파일 revert로 즉시 복원
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 승인 후 구현, 완료 후 result에 Phase 2로 기록
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 보안/CI 변경 이력 추가 필요

## 8. 아키텍처/설계 대안 비교
- 대안 1: `# nosec`으로 Bandit 억제
  - 장점: 빠름
  - 단점: 실질 보안 개선 없음, 감사 신뢰도 저하
- 대안 2: 코드/구성에서 근본 수정(채택)
  - 장점: 스캐너와 런타임 둘 다 정합성 확보
  - 단점: 수정 파일 수 증가
- 대안 3: Bandit severity threshold 완화
  - 장점: 파이프라인 즉시 통과
  - 단점: 중간등급 취약점 방치

## 9. 후속 조치
1. CI 재실행 결과를 결과 문서/체크리스트에 반영
2. 보안 스캐너 정책 변경 시 charter changelog 동기화

---

## Plan 변경 이력
- 2026-03-02: 초기 작성, 승인 대기(`Approval Pending`).
- 2026-03-02: 사용자 승인 반영(`Approved`), 구현 착수.
- 2026-03-02: B314/B104 대응 및 security artifact 가드 적용 완료(`Verified`).
