# 12. Troubleshooting: Strategy Tuning & Daily Report

**작성일**: 2026-02-12
**작성자**: Antigravity (AI Architect)
**관련**: v3.1 전략 튜닝, 일간 리포트 시스템 복구

---

## 1. 개요

이 문서는 다음 두 가지 주요 작업 중 발생한 문제와 해결 과정을 기록합니다.
1. **전략 파라미터 튜닝**: 하락장(BEAR)에서 거래가 전무한 문제 해결
2. **Daily Report 복구**: 스케줄러 누락 및 환경변수 설정 오류 수정

---

## 2. 전략 파라미터 튜닝 (Strategy Tuning)

### 2.1 문제 상황: BEAR 레짐 진입 불가
**증상**:
- v3.0 배포 후 3일간 거래 0건.
- 로그 분석 결과 모든 진입 시도가 RSI(14) 조건(`40` 이하 요구)에서 실패.
- 실제 RSI는 하락장에서도 45~60 구간을 주로 형성하여 진입 기회 차단.

**원인**:
- `rsi_14_max: 40` 설정이 지나치게 보수적임.
- `volume_min_ratio: 0.5` (평균의 50%) 조건이 야간/주말 저유동성 구간에서 발목을 잡음.

**해결**:
1. **RSI 완화**: BULL(50), SIDEWAYS(45), BEAR(45)로 상향 조정.
2. **RSI(7) 반등 조건 완화**: 과매도 진입(`trigger`) 기준을 30→35 등으로 완화.
3. **거래량 하한 완화**: 0.5 → 0.1~0.2로 낮추어 유동성이 적어도 진입 허용.
4. **동적 레짐 임계값**: `detect_regime()` 함수에 하드코딩된 `2.0`을 제거하고 YAML 설정값 연동.

---

## 3. Daily Report 시스템 복구

### 3.1 문제 상황: 리포트 미전송
**증상**: 매일 22:00 KST에 리포트가 전송되지 않음.
**원인**: `bot/main.py`의 `lifespan` 내에 `daily_reporter_job` 스케줄러 등록 코드가 누락됨.

**해결**:
- `APScheduler`에 크론 작업 추가 (13:00 UTC = 22:00 KST).
- `misfire_grace_time=7200` 설정으로 서버 다운 시에도 재시작 후 실행 보장.

### 3.2 트러블슈팅: PromptTemplate 변수 오류
**증상**: `KeyError: 'Input to PromptTemplate is missing variables...'`
**원인**: LangChain `PromptTemplate`에서 `{data['key']}`와 같은 딕셔너리 내부 접근 문법을 지원하지 않음.
**해결**:
```python
# Before
template="PnL: {data['total_pnl']}"
chain.invoke({"data": data})

# After
template="PnL: {total_pnl}"
chain.invoke({"total_pnl": data['total_pnl'], ...})
```

---

## 4. 배포 및 환경변수 (Deployment & Env)

### 4.1 문제 상황: API Key 누락
**증상**: DailyReporter 실행 시 `OpenAIError: The api_key client option must be set...`
**원인**:
- DailyReporter는 `gpt-4o-mini`를 사용하므로 `OPENAI_API_KEY`가 필요함.
- `bot-deployment.yaml`에 해당 환경변수가 정의되지 않음.

**해결**:
1. `k8s/apps/bot-deployment.yaml`에 `OPENAI_API_KEY` 환경변수 추가 (Secret 참조).
2. 추가로 `N8N_WEBHOOK_SECRET`, `N8N_URL`도 누락된 것을 확인하여 함께 추가함.
3. `deploy/deploy_to_minikube.sh`에서 Secret 생성 시 `OPENAI_API_KEY` 포함 확인.

### 4.2 문제 상황: n8n 연결 실패 (Local vs K8s)
**증상**: 로컬 테스트 시 `http://n8n:5678` 접속 불가 에러.
**원인**: K8s 내부 서비스 도메인(`n8n`)을 로컬에서 해석할 수 없음.
**해결**:
1. `k8s/apps/bot-deployment.yaml`에 `N8N_URL` 환경변수 명시 (`http://n8n:5678`).
2. 로컬 테스트(`scripts/test_daily_report.sh`) 시에는 `.env`를 통해 `http://localhost:5678` 사용 (Port Forwarding).

### 4.3 문제 상황: 설정 파일 갱신 안 됨 (Docker)
**증상**: `config/strategy_v3.yaml`을 수정하고 배포했으나 봇이 구버전 설정을 로드함.
**원인**: `Dockerfile`에 `COPY config/ ./config/` 구문이 없어, 빌드 시점의 설정 파일이 이미지에 포함되지 않음.
**해결**:
- `deploy/docker/bot.Dockerfile`, `collector.Dockerfile`, `dashboard.Dockerfile` 모두에 `COPY config/` 추가.

---

## 5. 결론

- **전략**: 지나친 보수성을 탈피하고 유연함을 확보 (백테스트 결과 0건 → 13건 거래).
- **리포트**: 스케줄러 및 환경변수 완비로 안정적 운영 기반 마련.
- **배포**: 설정 파일 동기화 문제 해결로 CI/CD 신뢰성 향상.
