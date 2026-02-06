# 11. 스케줄러 및 알림 시스템 트러블슈팅

**작성일**: 2026-02-07
**작성자**: Antigravity
**상태**: 해결 완료 (Resolved)

---

## 1. 스케줄러 작업 누락 (Job Missed)

### 증상
```
Run time of job "update_regime_job" was missed by 0:03:33.739266
```
- 레짐 업데이트가 실행되지 않고 `UNKNOWN` 상태 지속

### 원인
- APScheduler 기본 `misfire_grace_time`이 1초로, 조금만 지연되어도 작업이 스킵됨

### 해결
```python
scheduler.add_job(update_regime_job, 'interval', hours=1,
                  misfire_grace_time=300, coalesce=True)
```
- `misfire_grace_time=300`: 5분까지 지연되어도 실행
- `coalesce=True`: 밀린 작업은 1회만 실행

---

## 2. 레짐 UNKNOWN 지속 (데이터 부족)

### 증상
- 봇 재시작 후에도 "데이터 수집 중: 레짐 판단 대기 (약 8.3일치 데이터 필요)" 메시지
- BTC 외 다른 코인들이 계속 UNKNOWN 상태

### 원인
- MA200 계산에 최소 200시간(8.3일)의 1시간봉 데이터 필요
- 신규 코인은 데이터가 부족함

### 해결
- `scripts/backfill_for_regime.py`로 과거 12,000개 1분봉 데이터 수집
- 배포 스크립트에 `--backfill` 옵션 추가

```bash
./deploy/deploy_to_minikube.sh --backfill  # 첫 배포 시
```

---

## 3. backfill 스크립트 TypeError

### 증상
```
TypeError: StrategyConfig.__init__() got an unexpected keyword argument 'regime_detection'
```

### 원인
- YAML 파일 키(`regime_detection`, `data`)와 StrategyConfig 필드명 불일치
- `load_strategy_config()`에서 `**data` 언패킹 실패

### 해결
1. **strategy.py**: YAML 키를 필드에 매핑하도록 수정
2. **backfill 스크립트**: `get_config()` 제거, 심볼 직접 정의
```python
DEFAULT_SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE"]
```

---

## 4. n8n 워크플로우 데이터 접근 문제

### 증상
- Discord 알림에 `undefined` 표시
```
🪙 Symbol: undefined
📊 Regime: undefined
```

### 원인
- n8n Webhook 노드에서 JSON 데이터가 `body` 객체 안에 있음
- `$json.symbol` → 실제 구조는 `$json.body.symbol`

### 해결
- n8n Test URL로 데이터 구조 확인 후 Expression 수정
```
{{ $json.body.symbol }}  (O)
{{ $json.symbol }}       (X)
```

---

## 5. n8n 워크플로우 Import 실패

### 증상
- JSON 파일 import 후에도 설정이 비어있음 (Method: GET, Body Parameters 없음)

### 원인
- n8n 버전별로 JSON 스키마가 다름
- 단순화된 JSON은 n8n에서 제대로 파싱되지 않음

### 해결
- **수동 설정 권장**: n8n UI에서 직접 노드 구성
- Expression 모드 사용하여 Body Parameters 설정

---

## 6. 포트 포워딩 자동 끊김

### 증상
```
error forwarding port 5678: Broken pipe
```
- kubectl port-forward가 주기적으로 끊김

### 원인
- K8s 포트 포워딩은 연결 유휴 시간 초과 시 끊어짐
- Pod 재시작 시에도 끊어짐

### 해결 (임시)
```bash
# 자동 재연결 스크립트
while true; do kubectl port-forward -n coin-pilot-ns service/n8n 5678:5678; sleep 2; done &
```

### 종료 방법
```bash
pkill -f "kubectl port-forward"
pkill -f "while true"
```

---

## 7. BEAR 레짐에서 매수 없음 (전략 관련)

### 증상
- 하락장(BEAR) 레짐에서 AI가 지속적으로 REJECT
- 거래 데이터가 쌓이지 않음

### 원인
- BEAR 레짐의 진입 조건이 매우 보수적 (RSI7 < 30 → 30 이상 반등)
- AI Agent가 "Falling Knife" 패턴 감지 시 추가로 REJECT
- 이는 **의도된 동작**으로, 하락장에서 손실 최소화가 목적

### 대응
- **정상 동작**: BEAR 레짐에서 보수적 운영은 v3.0 전략 설계 의도
- **모니터링**: AI REJECT 알림으로 거절 사유 실시간 확인
- **향후 검토**: 백테스트 결과 분석 후 진입 조건 완화 여부 결정

> v2 → v3 전략 변경 시, 레짐 기반 적응형 전략을 도입한 이유 중 하나가 하락장에서의 무분별한 매수 방지였음. 따라서 BEAR 레짐에서 거래가 적은 것은 정상.

---

## 8. 대시보드 시간대 혼란 (UTC vs KST)

### 증상
- AI Agent Decisions 시간이 9시간 차이
- UTC 12:20 → 한국시각 21:20인데 12:20으로 표시

### 해결
```sql
SELECT created_at + interval '9 hours' as created_at, ...
```
- 적용 파일: `pages/3_risk.py`, `pages/4_history.py`, `pages/5_system.py`

---

## 9. v3.1 DB 마이그레이션 필요

### 증상
- v3.1 업데이트 후 봇 실행 시 DB 에러 발생 가능성 있음.
- `ProgrammingError: column "price_at_decision" of relation "agent_decisions" does not exist`

### 원인
- AI 거절 사유 분석을 위해 `agent_decisions` 테이블에 새로운 컬럼(`price_at_decision`, `regime`)이 추가되었으나, DB에 반영되지 않음.

### 해결
- 새로 추가된 마이그레이션 SQL 파일을 실행해야 함.

```bash
kubectl exec -it -n coin-pilot-ns db-0 -- psql -U postgres -d coinpilot -f - < migrations/v3_1_reject_tracking.sql
```

**참조**: [11_notification_and_timezone_improvements.md](../work-result/11_notification_and_timezone_improvements.md) - v3.1 전략 정교화 상세 내용
