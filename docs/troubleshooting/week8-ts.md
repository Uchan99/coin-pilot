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

| # | 이슈 | 카테고리 | 심각도 |
|---|------|----------|--------|
| 1 | APScheduler Runtime Error | Runtime | Medium |
| 2 | Bot Pod Crash (ModuleNotFoundError) | K8s/Docker | High |
| 3 | Redis Connection Error | K8s Config | High |
| 4 | Minikube Service Access | K8s/Network | Low |
| 5 | Scipy Build Failure | CI/CD | High |
| 6 | Dependency Resolution Loop | CI/CD | High |
| 7 | Test Collection Import Error | CI/CD | Medium |
| 8 | Volatility Method Mismatch | Code Review | Critical |
| 9 | DNS Resolution Error | K8s/Network | High |
| 10 | Dashboard Line Break Issue | UX/UI | Low |
| 11 | Chatbot API Key Error | K8s Config | High |
| 12 | DB Authentication Error | K8s/DB | Critical |
| 13 | Port Forwarding Zombie | Local Env | Low |
| 14 | Git Security Risk (Secret Leak) | Security | Critical |
| 15 | n8n Health Check Error | K8s/Env | Medium |
| 16 | Discord Webhook Placeholder | K8s Config | High |

---

## 9. DNS Resolution Error (Temporary failure in name resolution)
**증상**:
Bot 및 Collector가 DB에 연결할 때 `Temporary failure in name resolution` 에러 발생.

**원인**:
Minikube 내부 DNS가 간헐적으로 단축 도메인(`db`)을 해석하지 못함.

**해결**:
- `k8s/apps/bot-deployment.yaml`, `collector-deployment.yaml` 내 `DATABASE_URL`을 FQDN(`db.coin-pilot-ns.svc.cluster.local`)으로 변경.

## 10. Dashboard Line Break Rendering Issue
**증상**:
Streamlit 대시보드에서 Bot Reasoning(사유)이 한 줄로 뭉쳐서 출력됨.

**원인**:
`st.info()`는 기본적으로 공백을 축소(collapse)함. 또한, Bot에서 `|`로 구분하던 메시지 포맷이 가독성이 떨어짐.

**해결**:
- `src/bot/main.py`: 구분자를 `\n` 개행 문자로 변경.
- `src/dashboard/pages/2_market.py`: `st.info` 대신 `st.markdown` 사용 및 `\n`을 마크다운 줄바꿈(`  \n`)으로 변환 처리.

## 11. Chatbot API Key Error (Validation Error)
**증상**:
Dashboard 로그에 `1 validation error for ChatAnthropic anthropic_api_key Input should be a valid string` 발생.

**원인**:
`k8s/apps/dashboard-deployment.yaml`에 `ANTHROPIC_API_KEY` 환경 변수 주입 설정이 누락됨. (RAG Agent는 OpenAI 임베딩을 쓰므로 `OPENAI_API_KEY`도 누락 확인)

**해결**:
- `dashboard-deployment.yaml`에 `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `UPBIT` 키들을 Secret으로부터 주입하도록 추가.

## 12. DB Authentication Error (InvalidPasswordError)
**증상**:
`InvalidPasswordError: password authentication failed for user "postgres"` 발생하며 모든 앱이 DB 연결 실패.

**원인**:
DB Pod(`db-0`)는 8일 전 생성되어 옛날 비밀번호(`postgres`)를 유지하고 있었으나, 최근 배포된 앱들은 `k8s/base/secret.yaml`의 플레이스홀더 값(`PLACEHOLDER...`)을 비밀번호로 사용함.

**해결**:
- `k8s/base/secret.yaml`을 실제 비밀번호(`postgres`)가 담긴 값으로 수정하여 재적용.
- `kubectl exec`를 통해 DB 내부 사용자 비밀번호를 `postgres`로 강제 재설정(`ALTER USER`).

## 13. Port Forwarding Zombie Process
**증상**:
`kubectl port-forward` 시 `bind: address already in use` 에러 발생하며 포트(8501, 5432 등) 사용 불가.

**원인**:
이전 세션의 `kubectl` 프로세스가 종료되지 않고 백그라운드에서 포트를 점유 중.

**해결**:
- `lsof -i :8501` 등으로 PID 식별 후 `kill -9`로 좀비 프로세스 강제 종료.

## 14. Git Security Risk (Secret Leakage Prevention)
**증상**:
긴급 수정 과정에서 `k8s/base/secret.yaml`에 실제 API 키가 평문으로 기재됨. Git 업로드 시 유출 위험.

**원인**:
배포 편의를 위해 파일을 직접 수정했으나, 보안 원칙 위배.

**해결**:
- `k8s/base/secret.yaml` 내용을 다시 `PLACEHOLDER`로 원복.
- `deploy/deploy_to_minikube.sh` 스크립트를 수정하여, 배포 시점에 로컬 `.env` 파일을 읽어 동적으로 K8s Secret을 생성하도록 변경 (Git에는 껍데기만 올라감).

## 15. n8n System Health Check Error (K8s Env Variable Conflict)
**증상**:
Dashboard System 탭에서 n8n Workflow가 🔴 Error로 표시됨. 실제 n8n은 정상 작동 중.

**원인**:
`5_system.py`에서 `N8N_HOST`, `N8N_PORT` 환경변수를 사용했으나, K8s가 서비스에 대해 자동 주입하는 환경변수와 이름 충돌 발생.
```
N8N_PORT=tcp://10.101.53.39:5678  # K8s 자동 주입 (원치 않는 형식)
N8N_SERVICE_PORT=5678              # K8s 자동 주입 (올바른 형식)
```

**해결**:
- `src/dashboard/pages/5_system.py`에서 K8s 자동 주입 변수 사용으로 변경:
```python
# 변경 전
N8N_HOST = os.getenv("N8N_HOST", "n8n")
N8N_PORT = os.getenv("N8N_PORT", "5678")

# 변경 후
N8N_HOST = os.getenv("N8N_SERVICE_HOST", "localhost")
N8N_PORT = os.getenv("N8N_SERVICE_PORT", "5678")
```

## 16. Discord Webhook Not Working (Placeholder in Secret)
**증상**:
n8n Execute 시 `Invalid URL: PLACEHOLDER_USE_DEPLOY_SCRIPT` 에러 발생. Discord 알림 미전송.

**원인**:
`deploy/deploy_to_minikube.sh`가 `N8N_WEBHOOK_SECRET`과 `DISCORD_WEBHOOK_URL`을 `.env`에서 읽지 않고 플레이스홀더로 하드코딩함.

**해결**:
- `.env`에 `N8N_WEBHOOK_SECRET`, `DISCORD_WEBHOOK_URL` 추가.
- `deploy/deploy_to_minikube.sh` 수정하여 해당 값을 `.env`에서 동적 로딩:
```bash
--from-literal=N8N_WEBHOOK_SECRET="${N8N_WEBHOOK_SECRET:-coinpilot-n8n-secret}" \
--from-literal=DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"
```
- n8n Pod 재시작: `kubectl rollout restart deployment/n8n -n coin-pilot-ns`

---

## 정량 증빙 상태 (2026-03-04 백필)
- 해결한 문제:
  - 본문의 "증상/원인/조치" 섹션에 정의된 이슈를 해결 대상으로 유지한다.
- 현재 문서에서 확인 가능한 구체 수치(원문 기반):
  - `requirements.txt`에 동일 패키지가 중복 선언됨 (fastapi, uvicorn, redis가 2회씩 존재).
- 표준 Before/After 비교표:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 문서 내 확인 가능한 수치 라인 수(자동 추출 기준) | 0 | 1 | +1 | N/A |
| 표준 비교표 포함 여부(0/1) | 0 | 1 | +1 | N/A |

- 현재 기록 한계:
  - 결과 문서 대비 표준 Before/After 표(변화량/변화율)가 문서별로 일부 누락되어 있다.
- 추후 보강 기준:
  1) 관련 Result 문서와 로그 명령을 연결해 Before/After 표를 추가한다.
  2) 수치가 없는 경우 "측정 불가 사유"와 "추후 수집 계획"을 함께 기록한다.
