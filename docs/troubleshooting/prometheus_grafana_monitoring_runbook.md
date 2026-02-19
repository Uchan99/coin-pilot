# Prometheus + Grafana 모니터링 점검/활용 Runbook

**작성일**: 2026-02-19  
**대상 환경**: `coin-pilot-ns` (Kubernetes)

---

## 1. 목적

이 문서는 CoinPilot에서 Prometheus/Grafana가 연결되어 있어도 실제로 어떻게 확인하고 활용하는지 모를 때, 다음을 빠르게 점검하기 위한 운영 가이드다.

1. Prometheus 수집 대상(Target) 정상 여부 확인
2. bot `/metrics` 노출 확인
3. Grafana 데이터소스/대시보드 연결 확인
4. 자주 발생하는 설정 불일치(타겟 주소) 고정

---

## 2. 데이터 흐름 요약

1. `bot`이 `/metrics`로 `coinpilot_*` 메트릭 노출
2. Prometheus가 15초 간격으로 bot 메트릭 수집
3. Grafana가 Prometheus를 datasource로 조회
4. 대시보드(`coinpilot-overview`, `coinpilot-trades`)에서 시각화

---

## 3. 빠른 점검 절차 (필수)

### 3.1 Prometheus ConfigMap 실제값 확인

```bash
kubectl get configmap prometheus-config -n coin-pilot-ns -o yaml | sed -n '1,220p'
```

확인 포인트:
- `scrape_configs`의 `targets`가 현재 서비스 이름과 일치해야 함
- 권장 target: `bot:8000`

---

### 3.2 Prometheus Pod 내부 적용 설정 확인

```bash
kubectl exec -n coin-pilot-ns deployment/prometheus -- \
  sh -lc "cat /etc/prometheus/prometheus.yml"
```

---

### 3.3 Prometheus Target 상태 확인

```bash
kubectl port-forward -n coin-pilot-ns service/prometheus 9090:9090
```

브라우저 접속:
- `http://localhost:9090/targets`

정상 기준:
- `job="coinpilot-core"` 상태가 `UP`

---

### 3.4 bot 메트릭 직접 확인

```bash
kubectl exec -n coin-pilot-ns deployment/bot -- \
  sh -lc "wget -qO- http://localhost:8000/metrics | head -n 60"
```

정상 기준:
- `coinpilot_` 접두사 메트릭이 출력됨

예시 메트릭:
- `coinpilot_active_positions`
- `coinpilot_total_pnl`
- `coinpilot_trade_count_total`
- `coinpilot_ai_requests_total`

---

### 3.5 Grafana 데이터소스 확인

```bash
kubectl port-forward -n coin-pilot-ns service/grafana 3000:3000
```

브라우저 접속:
- `http://localhost:3000`

확인 경로:
1. `Connections -> Data sources -> Prometheus`
2. URL이 `http://prometheus:9090`인지 확인
3. `Save & Test` 성공 확인

---

### 3.6 Grafana 대시보드 확인

확인 대상:
- `coinpilot-overview`
- `coinpilot-trades`

패널이 비어 있으면:
1. Prometheus Targets (`UP/DOWN`) 먼저 확인
2. Prometheus Graph에서 쿼리 직접 실행

권장 테스트 쿼리:
- `coinpilot_active_positions`
- `coinpilot_total_pnl`
- `coinpilot_trade_count_total`
- `coinpilot_ai_requests_total`

---

## 4. 정상 설정 1안 (타겟 고정)

현재 레포에는 Prometheus 설정 경로가 2개가 있어 target 불일치가 발생할 수 있다.

- 경로 A: `k8s/monitoring/prometheus-config-cm.yaml`
- 경로 B: `deploy/monitoring/k8s-monitoring.yaml`

운영 기준은 아래처럼 `coinpilot-core` target을 `bot:8000`으로 통일한다.

### 4.1 기준 설정

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'coinpilot-core'
    static_configs:
      - targets: ['bot:8000']
    metrics_path: '/metrics'

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

### 4.2 적용 방법 (ConfigMap 재적용)

```bash
kubectl apply -f k8s/monitoring/prometheus-config-cm.yaml
kubectl rollout restart deployment/prometheus -n coin-pilot-ns
kubectl rollout status deployment/prometheus -n coin-pilot-ns
```

적용 후 `3.3` 절차로 `Targets`를 다시 확인한다.

---

## 5. 자주 발생하는 문제와 원인

1. Grafana 패널이 전부 비어 있음
- 원인: Prometheus target 주소 불일치 (`coinpilot-service:8000` 등)

2. Prometheus는 살아있는데 `coinpilot_*`가 없음
- 원인: bot `/metrics` 미노출 또는 bot 서비스명/포트 불일치

3. Grafana datasource 테스트 실패
- 원인: datasource URL 오설정, 네임스페이스 DNS 불일치

4. 설정 파일을 바꿨는데 반영 안 됨
- 원인: ConfigMap 변경 후 Prometheus 재시작 미수행

---

## 6. 운영 활용 포인트

1. 시스템 상태 확인
- Active Positions, Total PnL, Trade Count 추이로 기본 헬스 확인

2. AI 호출량 감시
- `coinpilot_ai_requests_total`로 모델 호출량/비용 리스크 추적

3. 장애 조기 탐지
- API latency, 변동성 지표 급등 시 봇 상태/거래 안전장치 점검

---

## 7. 체크리스트

- [ ] Prometheus target `coinpilot-core`가 `UP`
- [ ] bot `/metrics`에서 `coinpilot_*` 확인
- [ ] Grafana datasource `Save & Test` 성공
- [ ] `coinpilot-overview`, `coinpilot-trades` 패널 값 확인
- [ ] ConfigMap 반영 후 Prometheus rollout 재시작 완료

