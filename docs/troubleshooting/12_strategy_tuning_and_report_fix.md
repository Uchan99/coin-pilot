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

## 5. 모니터링 중 추가 트러블슈팅 (2026-02-13)

v3.1 배포 후 12시간 이상 모니터링 중 발견된 추가 문제들과 해결 과정.

### 5.1 AI Agent Decision DB 저장 실패 (Critical)

**증상**:
- 봇 로그에 `✅ 모든 진입 조건 충족!` → `Entry Signal Detected!` → AI Agent REJECT 판단까지 정상 수행
- 그러나 대시보드 System 탭의 "Recent AI Agent Decisions"에 새로운 결정이 표시되지 않음 (마지막 기록: 2026-02-07)
- 봇 로그에 매번 `[!] Failed to log agent decision: 'list' object has no attribute 'get'` 에러 출력

**원인**:
- `src/agents/runner.py:133`에서 `market_context.get("regime")` 호출
- `market_context`는 `executor.py:73`에서 `signal_info.get("market_context", {})`로 전달되는데, 이 값은 `df.tail(10).to_dict(orient="records")` — **dict가 아닌 list**
- list에는 `.get()` 메서드가 없어 `AttributeError` 발생 → `_log_decision` 전체 실패 → DB 미저장
- 같은 문제가 REJECT 시 Discord 알림 전송 코드(line 154)에도 존재했으나, DB 저장이 먼저 실패하여 해당 코드까지 도달하지 못함

**해결**:
```python
# Before (runner.py:133, 154)
regime = market_context.get("regime") if market_context else None
"regime": market_context.get("regime", "UNKNOWN") if market_context else "UNKNOWN"

# After
regime = indicators.get("regime") if indicators else None
"regime": indicators.get("regime", "UNKNOWN") if indicators else "UNKNOWN"
```
- `regime`은 `signal_info`에 직접 포함되어 있으므로 `indicators`(= `signal_info`)에서 추출하는 것이 올바름

**파일**: `src/agents/runner.py` (2곳 수정)

### 5.2 n8n Health Check 대시보드 표시 오류

**증상**:
- 대시보드 System 탭에서 n8n Workflow가 🔴 Error로 표시
- 그러나 n8n 자체는 정상 동작 (Daily Report Discord 발송 성공, AI REJECT 알림도 정상)

**원인**:
- 대시보드가 K8s pod이 아닌 **로컬에서 Streamlit으로 실행** 중
- 로컬 환경에서는 `N8N_SERVICE_HOST` 환경변수가 없어 `localhost:5678`로 폴백
- n8n 포트포워딩이 누락되어 있었음 (DB, Redis만 포트포워딩된 상태)

**해결**:
1. n8n 포트포워딩 추가: `kubectl port-forward -n coin-pilot-ns service/n8n 5678:5678 &`
2. Health check 안정성 개선: timeout 2초→3초, 재시도 1회 추가 (`src/dashboard/pages/5_system.py`)

### 5.3 Regime UNKNOWN 표시 (재시작 후)

**증상**:
- PC 재부팅 후 대시보드에 "Regime 판단 대기중, 8.3일 데이터 필요" 표시
- 약 3시간 후 자동 복구

**원인**:
- 재부팅으로 Redis 캐시 초기화 → regime 값 소실
- 봇 시작 시 `update_regime_job()`이 즉시 호출되나(`main.py:507`), 당시 startup 에러 또는 캔들 데이터 부족으로 UNKNOWN 설정
- 1시간 주기 스케줄러 재실행 시 정상 복구

**상태**: 현재는 정상 동작 확인. 시작 시 regime 업데이트 실패 원인은 로그 소실로 정확한 추적 불가.

---

## 6. 결론

- **전략**: 지나친 보수성을 탈피하고 유연함을 확보 (백테스트 결과 0건 → 13건 거래).
- **리포트**: 스케줄러 및 환경변수 완비로 안정적 운영 기반 마련.
- **배포**: 설정 파일 동기화 문제 해결로 CI/CD 신뢰성 향상.
- **AI Agent**: Decision DB 저장 버그 수정으로 대시보드 모니터링 정상화 및 Discord REJECT 알림 동작 확인.
- **대시보드**: n8n Health Check 정상화 (포트포워딩 + 재시도 로직).
