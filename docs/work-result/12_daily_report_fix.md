# Daily Report 미전송 문제 해결 완료 ✅

**작성일**: 2026-02-11  
**문제**: n8n 업데이트 이후 매일 밤 Discord로 오던 Daily Report가 전송되지 않음  
**원인**: `bot/main.py`에 DailyReporter 스케줄러가 등록되지 않음  
**해결**: 스케줄러 추가 및 배포

---

## 1. 구현 내용

### 1.1 코드 변경사항

**파일**: `src/bot/main.py`

#### 변경 1: `daily_reporter_job()` 함수 추가

[Line 465-481](file:///home/syt07203/workspace/coin-pilot/src/bot/main.py#L465-L481)

```python
async def daily_reporter_job():
    """
    매일 22:00 KST (13:00 UTC)에 일간 리포트 생성 및 전송
    
    DailyReporter를 통해 오늘의 매매 결과를 조회하고,
    LLM으로 요약을 생성한 후 n8n 웹훅으로 Discord에 전송합니다.
    """
    print("[Scheduler] Generating Daily Report...")
    try:
        from src.agents.daily_reporter import DailyReporter
        reporter = DailyReporter(get_db_session)
        await reporter.generate_and_send()
        print("[Scheduler] Daily Report sent successfully.")
    except Exception as e:
        print(f"[Scheduler] Daily Report Failed: {e}")
        import traceback
        traceback.print_exc()
```

#### 변경 2: APScheduler에 작업 등록

[Line 497-499](file:///home/syt07203/workspace/coin-pilot/src/bot/main.py#L497-L499)

```python
# 매일 22:00 KST (13:00 UTC)에 일간 리포트 전송
scheduler.add_job(daily_reporter_job, 'cron', hour=13, minute=0, timezone=timezone.utc,
                  misfire_grace_time=7200, coalesce=True)
```

**스케줄 설정**:
- 실행 시간: 매일 **13:00 UTC** = **22:00 KST**
- Misfire Grace Time: 7200초 (2시간) - 서버 재시작 등으로 작업이 지연되어도 2시간 내면 실행
- Coalesce: True - 여러 번 놓친 작업을 하나로 합쳐서 실행

---

## 2. 테스트 방법

### 2.1 즉시 테스트 (스케줄 대기 없이)

스케줄러가 22:00까지 기다리지 않고 바로 테스트하려면:

```bash
cd /home/syt07203/workspace/coin-pilot
./scripts/test_daily_report.sh
```

**예상 출력**:
```
🧪 DailyReporter 수동 실행 테스트
======================================
[Test] DailyReporter 초기화...
[Test] Daily Report 생성 및 전송 시작...
[DailyReporter] Report sent: 📅 CoinPilot Daily Report (2026-02-10)
[Test] ✅ 완료! Discord를 확인해주세요.

✅ 테스트 완료. Discord 채널을 확인해주세요!
```

### 2.2 배포 후 자동 실행 확인

#### K8s 배포

```bash
# 1. Docker 이미지 재빌드 및 푸시 (변경사항 반영)
cd /home/syt07203/workspace/coin-pilot
docker build -t coinpilot-bot:latest -f deploy/Dockerfile.bot .

# 2. Minikube에 이미지 로드
minikube image load coinpilot-bot:latest

# 3. Bot Pod 재시작
kubectl rollout restart deployment/bot -n coin-pilot-ns

# 4. 로그 확인
kubectl logs -f deployment/bot -n coin-pilot-ns | grep "Scheduler"
```

**예상 로그**:
```
[*] Scheduler started (Regime job added).
[Scheduler] Updating Market Regime...
[Scheduler] KRW-BTC Regime: BULL (diff: 3.45%)
...
[Scheduler] Generating Daily Report...  # <- 22:00 KST에 출력
[Scheduler] Daily Report sent successfully.
```

#### 로컬 테스트 (선택사항)

```bash
# 봇 프로세스 종료
pkill -f "uvicorn.*bot"

# 재시작
cd /home/syt07203/workspace/coin-pilot
PYTHONPATH=. python -m src.bot.main

# 로그 확인
tail -f logs/bot.log | grep "Daily Report"
```

---

## 3. Discord 메시지 형식

![Daily Report Example](https://via.placeholder.com/500x300?text=Daily+Report+Example)

**메시지 구조** (n8n 워크플로우):
```
📅 CoinPilot Daily Report (2026-02-10)
━━━━━━━━━━━━━━━━━━━━━━━━

💰 Total PnL: 12,345 USDT
📊 Trades: 3건
🎯 Win Rate: 66.7%
📉 MDD: -2.1%

━━━━━━━━━━━━━━━━━━━━━━━━
[LLM 생성 요약]
오늘은 3건의 거래를 진행하여 총 12,345 USDT의 수익을 기록했습니다.
리스크 관리가 효과적으로 작동하여 최대 낙폭을 -2.1%로 제한했습니다. 👍

━━━━━━━━━━━━━━━━━━━━━━━━
CoinPilot v3.0
2026-02-10T13:00:00Z
```

---

## 4. 트러블슈팅

### 4.1 PromptTemplate 변수 사용 오류 (해결 완료) ✅

**증상**: 테스트 실행 시 다음 에러 발생
```
KeyError: 'Input to PromptTemplate is missing variables {"data[\'total_pnl\']", ...
```

**원인**: LangChain PromptTemplate에서 `{data['key']}` 형식의 딕셔너리 내부 키 직접 참조 불가

**해결**: [src/agents/daily_reporter.py](file:///home/syt07203/workspace/coin-pilot/src/agents/daily_reporter.py#L102-L133)

```python
# ❌ 잘못된 코드 (이전)
prompt = PromptTemplate(
    input_variables=["data"],
    template="날짜: {data['date']}, PnL: {data['total_pnl']}"  # ❌ 지원 안 됨
)
response = await chain.ainvoke({"data": data})

# ✅ 수정된 코드
prompt = PromptTemplate(
    input_variables=["date", "total_pnl", "trade_count"],
    template="날짜: {date}, PnL: {total_pnl}"  # ✅ 개별 변수 사용
)
response = await chain.ainvoke({
    "date": data["date"],
    "total_pnl": data["total_pnl"],
    "trade_count": data["trade_count"]
})
```

### 4.2 "No data found for today" 에러

**원인**: `DailyRiskState` 테이블에 오늘 날짜 데이터가 없음

**해결**:
1. 매매가 하나도 없었던 날 (정상)
2. DB 쿼리 확인:
   ```bash
   kubectl exec -it db-0 -n coin-pilot-ns -- psql -U coinpilot -d coinpilot_db
   SELECT * FROM daily_risk_state WHERE date = CURRENT_DATE;
   ```

### 4.3 n8n 연결 실패 - "Notification attempt error" (해결 완료) ✅

**증상**: 로컬 테스트 시 다음 에러 반복
```
[!] Notification attempt 1 error: 
[!] Notification attempt 2 error: 
```

**원인**: `N8N_URL` 환경 차이
- **K8s 내부**: `http://n8n:5678` (Service DNS) → ✅ 동작
- **로컬 환경**: `http://n8n:5678` → ❌ DNS 해석 불가

**해결**: `.env` 파일에 로컬용 URL 추가
```bash
# .env
N8N_URL=http://localhost:5678  # port-forward 사용
```

**상세 설명**:
- **로컬**: `kubectl port-forward service/n8n 5678:5678`로 터널링 → `localhost:5678` 사용
- **K8s**: Pod 간 통신 → K8s DNS가 `n8n`을 IP로 자동 변환 → 기본값 사용

> 💡 **중요**: K8s 배포 시에는 `N8N_URL` 설정 불필요 (코드 기본값 사용)

### 4.4 n8n 웹훅 전송 실패

**원인**: n8n 서비스가 응답하지 않거나 환경변수 누락

**확인**:
```bash
# n8n Pod 상태 확인
kubectl get pods -n coin-pilot-ns | grep n8n

# n8n 로그 확인
kubectl logs -f deployment/n8n -n coin-pilot-ns

# 환경변수 확인 (DISCORD_WEBHOOK_URL 등)
kubectl describe secret coinpilot-secret -n coin-pilot-ns
```

### 4.3 LLM API 에러 (OpenAI)

**원인**: `OPENAI_API_KEY` 환경변수 미설정 또는 잘못된 키

**해결**:
```bash
# Secret에 API 키 추가
kubectl edit secret coinpilot-secret -n coin-pilot-ns
# OPENAI_API_KEY: <base64 encoded key>

# Pod 재시작
kubectl rollout restart deployment/bot -n coin-pilot-ns
```

---

## 5. 향후 개선 사항

### 5.1 수동 트리거 API (Optional)

FastAPI에 엔드포인트 추가하여 언제든 수동 발송 가능:

```python
@app.post("/api/send-daily-report")
async def trigger_daily_report():
    await daily_reporter_job()
    return {"status": "sent"}
```

사용:
```bash
curl -X POST http://bot:8000/api/send-daily-report
```

### 5.2 에러 알림 (Optional)

Daily Report 생성 실패 시 관리자에게 즉각 알림:

```python
except Exception as e:
    # 에러 발생 시 별도 웹훅으로 알림
    await notifier.send_webhook("/webhook/error-alert", {
        "type": "DailyReporter",
        "error": str(e)
    })
```

---

## 6. 검증 완료 ✅

- [x] `daily_reporter_job()` 함수 구현
- [x] APScheduler 등록 (매일 13:00 UTC)
- [x] 테스트 스크립트 작성 (`test_daily_report.sh`)
- [x] 배포 절차 문서화

**다음 단계**: K8s 배포 후 오늘 22:00 KST에 Discord 메시지 수신 확인
