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

---

## 5. 추가 업데이트 (2026-02-07): v3.1 전략 정교화 및 AI Reject 추적

Claude Code를 통해 전략의 안정성을 높이고 AI 거절 사유 분석을 강화하는 추가 기능이 구현되었습니다.

### 5.1 전략 정교화 (v3.1)
**파일**: `src/config/strategy.py`, `src/engine/strategy.py`, `src/common/indicators.py`, `config/strategy_v3.yaml`

기존 v3.0 전략에서 발견된 약점(하락장에서의 섣부른 진입, 횡보장에서의 잦은 손절)을 보완하기 위해 진입 조건을 강화했습니다.

1. **RSI(7) 최소 반등 폭 (`min_rsi_7_bounce_pct`)**
    - 단순히 과매도에서 벗어났다고 진입하는 것이 아니라, 바닥 대비 최소 3% 이상 반등해야 진입.
    - V자 반등 확인용.

2. **BEAR 레짐 진입 조건 개선 ("proximity_or_above")**
    - 기존: MA20 아래 97% 지점 근처일 때만 진입 (너무 엄격)
    - 개선: MA20을 돌파했거나(강한 반등), MA20 아래 3% 이내에 있을 때 진입 허용.

3. **Falling Knife 방지 (`require_price_above_bb_lower`)**
    - 볼린저 밴드 하단을 뚫고 내려간 상태(급락 중)에서는 진입 금지.
    - 밴드 안으로 복귀했을 때만 진입.

4. **거래량 필터 추가**
    - `volume_min_ratio`: 거래량이 평소의 50% 미만이면 진입 금지 (유동성 부족 방지).
    - `volume_surge_check` (BEAR 전용): 거래량이 평소 대비 2배 이상 폭증하면 패닉 셀링으로 간주하여 진입 보류.
    - `indicators.py`에 `calculate_volume_ratios()` 함수 및 `recent_vol_ratios` 지표 추가.

### 5.2 AI Reject 추적 및 DB 확장
**파일**: `src/common/models.py`, `migrations/v3_1_reject_tracking.sql`

AI가 왜 매수를 거절했는지 사후 분석하기 위해 데이터를 추가로 저장합니다.

- **DB 스키마 변경**: `agent_decisions` 테이블에 컬럼 추가
    - `price_at_decision`: 거절/승인 당시 가격
    - `regime`: 당시 마켓 레짐

이 데이터는 추후 대시보드에서 "어떤 레짐에서 거절이 많은지", "거절 후 가격이 어떻게 움직였는지" 분석하는 데 사용됩니다.

### 5.3 기타 수정
- `indicators.py`: pandas FutureWarning 수정 (`'1H'` → `'1h'`)

### 5.4 Redis TTL 설정 최적화
**파일**: `src/bot/main.py`

스케줄러 지연 시 레짐 데이터가 소실되는 문제를 방지하기 위해 Redis Key 만료 시간을 연장했습니다.

- **기존**: 3900초 (1시간 + 5분 여유)
- **변경**: 7200초 (2시간)
- **효과**: 스케줄러가 1회 누락되거나 지연되더라도 데이터 지속성 보장.
