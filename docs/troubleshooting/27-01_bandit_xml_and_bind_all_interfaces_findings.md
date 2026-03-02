# 27-01. Bandit B314/B104 및 security artifact 경고 트러블슈팅 / 핫픽스

작성일: 2026-03-02
상태: Fixed
우선순위: P1
관련 문서:
- Plan: `docs/work-plans/27-01_bandit_findings_and_security_artifact_reliability_fix_plan.md`
- Result: `docs/work-result/27_ci_pipeline_dependency_and_test_env_fix_result.md`
- Charter update 필요: YES

---

## 1. 트리거(왜 시작했나)
- 모니터링/로그/사용자 리포트로 관측된 내용:
  - `security` 잡에서 Bandit 실패
  - 감지 항목: `B314`(XML 파싱), `B104`(0.0.0.0 하드코딩)
  - 후속으로 artifact 업로드 경고(`No files were found...`) 발생
- 긴급도/영향:
  - CI security 게이트 실패로 main 파이프라인 차단

---

## 2. 증상/영향
- 증상:
  1) `src/agents/news/rss_news_pipeline.py`의 `ET.fromstring` 경고(B314)
  2) `src/bot/main.py`의 `host="0.0.0.0"` 경고(B104)
  3) 보안 잡 중단 시 pip-audit 리포트 파일 미생성 경고
- 영향(리스크/데이터/비용/운영):
  - 리스크: 외부 XML 파싱/바인딩 정책 위반 신호
  - 운영: CI 반복 실패
- 발생 조건/재현 조건:
  - `CoinPilot CI` security 단계 실행 시 재현

---

## 3. 재현/관측 정보
- 핵심 로그/에러 메시지:
  - `Issue: [B314:blacklist] Using xml.etree.ElementTree.fromstring ...`
  - `Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.`

---

## 4. 원인 분석
- 가설 목록:
  1) RSS 파싱에 stdlib XML 파서 직접 사용
  2) 앱 코드에서 바인딩 주소 하드코딩
  3) 보안 단계 조기 실패 시 리포트 업로드 가드 부재
- 조사 과정(무엇을 확인했는지):
  - 해당 파일/라인과 CI workflow 단계 확인
- Root cause(결론):
  - 보안 정책을 만족하는 코드/CI 가드레일이 누락된 상태

---

## 5. 해결 전략
- 단기 핫픽스:
  1) `defusedxml` 기반 XML 파싱으로 교체
  2) `BOT_HOST`/`BOT_PORT` env 기반 바인딩으로 전환
  3) security workflow에 리포트 파일 선생성(step) 추가
- 근본 해결:
  - 보안 스캐너 요구사항을 코드/배포 설정/CI에 일관되게 반영
- 안전장치(feature flag, rate limit, timeout/cooldown, circuit breaker 등):
  - 기본 `BOT_HOST=127.0.0.1`, 컨테이너에서만 `0.0.0.0` 주입

---

## 6. 수정 내용
- 변경 요약:
  - XML 파서 전환, 바인딩 env 분리, security artifact 가드 추가
- 변경 파일:
  - `src/agents/news/rss_news_pipeline.py`
  - `src/bot/main.py`
  - `requirements.txt`
  - `requirements-bot.txt`
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `deploy/docker-compose.yml`
  - `deploy/cloud/oci/.env.example`
  - `.env.example`
  - `.github/workflows/ci.yml`
- DB/스키마 변경(있다면):
  - 없음
- 롤백 방법(필수):
  - 해당 커밋 revert

---

## 7. 검증
- 실행 명령/절차:
  - `DB_PASSWORD=ci_test_password DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/coinpilot_test REDIS_URL=redis://localhost:6379/0 PYTHONPATH=. .venv/bin/python -m pytest tests/agents/test_rss_news_pipeline.py tests/utils/test_metrics.py tests/analytics/ tests/agents/`
  - `python - <<'PY' ... yaml.safe_load('.github/workflows/ci.yml') ... PY`
- 결과:
  - pytest: `24 passed`
  - CI workflow YAML 파싱: `CI_YAML_OK`

- 운영 확인 체크:
  1) GitHub Actions에서 Bandit B314/B104 미검출 확인 필요
  2) security artifact 경고 미발생 확인 필요

---

## 8. 재발 방지
- 가드레일(테스트/알림/검증 스크립트/권한/필터/타임아웃 등):
  - 외부 XML 파싱은 `defusedxml` 기본 사용 원칙 유지
  - 서비스 바인딩은 코드 literal 대신 env 주입 원칙 유지
  - security report 파일 선생성으로 업로드 안정성 확보
- 문서 반영:
  - plan/result 업데이트 여부: YES
  - troubleshooting 링크 추가 여부: YES
  - PROJECT_CHARTER.md 변경(있다면): YES (변경 이력 추가)

---

## 9. References
- `docs/work-plans/27-01_bandit_findings_and_security_artifact_reliability_fix_plan.md`
- `.github/workflows/ci.yml`
- `src/agents/news/rss_news_pipeline.py`
- `src/bot/main.py`

## 10. 배운점
- 트러블 슈팅 경험을 통해 깨달은 점이나 배운점
  - 보안 스캐너 경고는 억제가 아니라 코드/구성 분리를 통해 해결해야 유지보수 비용이 낮다.
- 포트폴리오용으로 트러블 슈팅을 작성할때, 어떤 점을 강조해야하는지, 활용하면 좋을 내용
  - "로그 기반 원인 분리 → 최소 변경 핫픽스 → 재현 가능한 검증" 흐름을 명확히 남기는 것이 핵심이다.
- 트러블 슈팅을 통해 어떤 능력이 향상되었는지
  - CI 보안 실패를 코드/배포/파이프라인 관점으로 분해해 동시 복구하는 능력.
