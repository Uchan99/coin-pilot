# Week 8 Troubleshooting Log

## 1. APScheduler Runtime Error
**증상**:
`main.py` 실행 시 `RuntimeError: The scheduler is already running` 에러 발생.

**원인**:
FastAPI의 수명 주기(Lifespan) 이벤트 내에서 `scheduler.start()`를 호출했는데, `AsyncIOScheduler`가 일부 환경에서 중복 시작되거나 비동기 루프 충돌을 일으킴.

**해결**:
- `lifespan` 컨텍스트 매니저 내에서 스케줄러 상태를 확인 (`if not scheduler.running:`)
- `try-except` 블록으로 `SchedulerAlreadyRunningError` 예외 처리 추가.

## 2. Bot Pod Crash (ModuleNotFoundError)
**증상**:
K8s 배포 후 Bot 포드가 `Error` 상태로 진입. 로그 확인 시 `ModuleNotFoundError: No module named 'prometheus_client'` 발생.

**원인**:
`requirements-bot.txt` (Docker 이미지 빌드용)에 Week 8에서 추가된 의존성(`prometheus-client`, `arch`, `apscheduler`)이 누락됨.

**해결**:
- `requirements-bot.txt`에 누락된 패키지 추가.
- `deploy/deploy_to_minikube.sh` 실행하여 이미지 리빌드 및 재배포.

## 3. Redis Connection Error (Hostname Mismatch)
**증상**:
Bot 로그에 `[RiskManager] Redis Error ... Error -3 connecting to coinpilot-redis:6379` 지속 발생.

**원인**:
`k8s/base/secret.yaml`의 `REDIS_URL`이 `redis://coinpilot-redis:6379/0`으로 설정되어 있었으나, 실제 K8s Service 이름은 `redis`임. (DNS 해석 불가)

**해결**:
- `k8s/base/secret.yaml`의 `REDIS_URL`을 `redis://redis:6379/0`으로 수정.
- Secret 재적용 및 Deployment 재시작 (`kubectl rollout restart deployment bot`).

## 4. Minikube Service Access Issue
**증상**:
`minikube ip` (192.168.49.2)로 접근 시 Connection Timeout 발생 (Linux/Docker Driver 환경 특성).

**해결**:
- `kubectl port-forward`를 사용하여 로컬 포트를 파드 포트와 맵핑.
- `docs/daily-startup-guide.md` 및 `USER_MANUAL.md`에 포트 포워딩 가이드 추가.

---

## CI/CD Pipeline Issues (GitHub Actions)

## 5. Scipy Build Failure
**증상**:
GitHub Actions CI에서 `pip install` 시 `scipy metadata-generation-failed` 에러 발생.

**원인**:
scipy가 wheel이 없는 환경에서 소스 빌드를 시도하며, BLAS/LAPACK 라이브러리가 CI 환경에 없어 빌드 실패.

**해결**:
- `.github/workflows/ci.yml`에 시스템 의존성 추가: `libopenblas-dev`, `liblapack-dev`
- pip install 시 `--only-binary=scipy` 플래그 추가
- `requirements.txt`에 버전 핀 추가: `scipy>=1.11.0,<2.0.0`

## 6. Dependency Resolution Loop (resolution-too-deep)
**증상**:
CI에서 `pip install -r requirements.txt` 실행 시 `resolution-too-deep` 에러 발생.

**원인**:
`requirements.txt`에 동일 패키지가 중복 선언됨 (fastapi, uvicorn, redis가 2회씩 존재).

**해결**:
- `requirements.txt`에서 중복 패키지 제거.
- 최종 31개 패키지로 정리.

## 7. Test Collection Import Error
**증상**:
CI pytest 실행 시 `tests/agents/test_manual.py` 수집 단계에서 `ModuleNotFoundError` 발생.

**원인**:
`test_manual.py`가 `src.agents.router`를 import하고, 이 모듈이 `src.common.db`를 import하면서 DB 엔진을 import 시점에 생성 시도. CI 환경에 DB가 없어 실패.

**해결**:
- `tests/agents/test_manual.py`를 `scripts/manual_agent_test.py`로 이동.
- 해당 파일은 수동 테스트용이므로 CI pytest 대상에서 제외.

## 8. Volatility Scheduler Method Signature Mismatch
**증상**:
코드 리뷰 시 발견 - `retrain_volatility_job()` 함수에서 존재하지 않는 메서드 호출.

**원인**:
```python
# 잘못된 코드
vol, is_high = model.predict_volatility(returns)  # 메서드 없음
await model.update_volatility_state(redis_client, vol, is_high)  # 시그니처 불일치
```

**해결**:
```python
# 수정된 코드
vol = model.fit_predict(df['close'])
model.update_volatility_state(vol, threshold=2.0)
```

---

## Summary

| 이슈 | 카테고리 | 심각도 |
|------|----------|--------|
| APScheduler Runtime Error | Runtime | Medium |
| Bot Pod Crash (ModuleNotFoundError) | K8s/Docker | High |
| Redis Connection Error | K8s Config | High |
| Minikube Service Access | K8s/Network | Low |
| Scipy Build Failure | CI/CD | High |
| Dependency Resolution Loop | CI/CD | High |
| Test Collection Import Error | CI/CD | Medium |
| Volatility Method Mismatch | Code Review | Critical |
