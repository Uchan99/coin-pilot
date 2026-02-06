# 11. 알림 시스템 및 운영 개선 구현 결과

**작성일**: 2026-02-07
**작성자**: Antigravity (AI Architect)
**관련**: 스케줄러 안정화, 알림 시스템 개선, 운영 편의성 향상

---

## 1. 개요

운영 중 발견된 여러 문제를 해결하고 운영 편의성을 개선했습니다:
- 스케줄러 작업 누락 문제
- AI REJECT 상황 실시간 알림
- 대시보드 시간대 표기 (UTC → KST)
- n8n 워크플로우 Discord 알림 형식 개선
- 과거 데이터 백필 자동화

---

## 2. 주요 구현 사항

### 2.1 스케줄러 안정화

**파일**: `src/bot/main.py`

| 설정 | 이전 | 이후 |
|------|------|------|
| misfire_grace_time | 1초 (기본값) | 300~3600초 |
| coalesce | False | True |

```python
scheduler.add_job(retrain_volatility_job, 'cron', ...,
                  misfire_grace_time=3600, coalesce=True)
scheduler.add_job(update_regime_job, 'interval', hours=1,
                  misfire_grace_time=300, coalesce=True)
```

### 2.2 AI REJECT Discord 알림

**파일**: `src/agents/runner.py`

AI 에이전트가 매수를 거절할 때 Discord로 실시간 알림 전송:
- 심볼, 레짐, RSI, 거절 사유 포함
- n8n `/webhook/ai-reject` 엔드포인트 사용

```python
if decision == "REJECT":
    asyncio.create_task(notifier.send_webhook("/webhook/ai-reject", {
        "symbol": symbol,
        "regime": market_context.get("regime", "UNKNOWN"),
        "rsi": indicators.get("rsi", 0),
        "reason": reasoning[:500],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }))
```

### 2.3 대시보드 시간대 KST 변환

**수정 파일**:
| 파일 | 적용 대상 |
|------|----------|
| `pages/4_history.py` | 거래 내역 |
| `pages/5_system.py` | AI Agent Decisions, Risk Audit |
| `pages/3_risk.py` | Risk Log History |

```sql
SELECT created_at + interval '9 hours' as created_at, ...
SELECT timestamp + interval '9 hours' as timestamp, ...
```

### 2.4 n8n 워크플로우 개선

**수정 파일**: `config/n8n_workflows/*.json`

| 워크플로우 | 개선 내용 |
|-----------|----------|
| ai_reject.json | 신규 추가 |
| trade_notification.json | Expression 형식으로 변경 |
| daily_report.json | Webhook 방식으로 변경 (Cron → 봇 연동) |
| risk_alert.json | Expression 형식으로 변경 |

**주요 변경**: `$json.xxx` → `$json.body.xxx` (n8n 데이터 구조에 맞춤)

### 2.5 설정 로딩 및 백필 개선

**파일**: `src/config/strategy.py`
- YAML 키 매핑 수정 (`regime_detection` → `MA_FAST_PERIOD` 등)

**파일**: `scripts/backfill_for_regime.py`
- `get_config()` 의존성 제거, 심볼 목록 직접 정의

**파일**: `deploy/deploy_to_minikube.sh`
- `--backfill` 옵션 추가 (선택적 과거 데이터 수집)

```bash
./deploy/deploy_to_minikube.sh --backfill  # 첫 배포 시
./deploy/deploy_to_minikube.sh              # 일반 재배포
```

---

## 3. 변경 파일 목록

| 파일 | 변경 내용 |
|------|----------|
| `src/bot/main.py` | 스케줄러 misfire_grace_time, coalesce 설정 |
| `src/agents/runner.py` | AI REJECT 알림 전송 로직 |
| `src/config/strategy.py` | YAML 키 매핑 수정 |
| `src/dashboard/pages/3_risk.py` | KST 시간대 변환 |
| `src/dashboard/pages/4_history.py` | KST 시간대 변환 |
| `src/dashboard/pages/5_system.py` | KST 시간대 변환 |
| `scripts/backfill_for_regime.py` | get_config() 제거, 직접 심볼 정의 |
| `deploy/deploy_to_minikube.sh` | --backfill 옵션 추가 |
| `config/n8n_workflows/*.json` | Expression 형식 및 $json.body 적용 |

---

## 4. 기대 효과

| 항목 | 효과 |
|------|------|
| 운영 안정성 | 스케줄러 누락 방지로 레짐 데이터 신뢰성 확보 |
| 가시성 | AI 의사결정 과정 실시간 모니터링 |
| 편의성 | 대시보드 시간 확인 시 KST 바로 확인 |
| 배포 자동화 | 첫 배포 시 과거 데이터 자동 수집 |
