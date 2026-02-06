# CoinPilot v3.0 User Manual

**Last Updated**: 2026-02-06
**Version**: v3.0 (Market Regime Strategy)

---

## 1. 개요 (Introduction)
CoinPilot v3.0은 Kubernetes 기반의 AI 자동 매매 시스템입니다.
규칙 기반 엔진과 AI 리스크 매니저가 협력하여 안정적인 수익을 추구하며, **Streamlit Dashboard**를 통해 실시간 모니터링이 가능합니다.

---

## 2. 대시보드 사용법 (Dashboard Guide)

### 2.1 실행 방법
로컬 환경(VS Code)에서 대시보드를 실행하려면 다음 단계가 필요합니다.

**Step 1. 포트 포워딩 (별도 터미널에서 실행)**
```bash
# DB (필수)
kubectl port-forward -n coin-pilot-ns service/db 5432:5432 &

# Redis (System Health 페이지용)
kubectl port-forward -n coin-pilot-ns service/redis 6379:6379 &

# n8n (System Health 페이지용, 선택)
kubectl port-forward -n coin-pilot-ns service/n8n 5678:5678 &
```
*Tip: `&`를 붙이면 백그라운드 실행됩니다.*

**Step 2. 대시보드 앱 실행**
```bash
source .venv/bin/activate
PYTHONPATH=. streamlit run src/dashboard/app.py
```
브라우저에서 `http://localhost:8501` 접속.

**Step 3. 포트 포워딩 종료 (세션 종료 시)**
```bash
# 백그라운드 포트 포워딩 프로세스 종료
pkill -f "kubectl port-forward"
```

### 2.2 메뉴 설명
-   **📊 Overview**:
    -   **Key Metrics**: 총 거래 횟수, 승률, 누적 손익(PnL)을 확인합니다.
    -   **Active Positions**: 현재 봇이 보유 중인 코인과 수익률을 봅니다.
-   **📈 Market Analysis**:
    -   **Market Regime**: 현재 마켓 레짐(🟢BULL/🟡SIDEWAYS/🔴BEAR)과 설명을 확인합니다.
    -   **Chart**: 비트코인 등 주요 코인의 캔들차트를 확인합니다.
    -   **Bot Brain**: 현재 Action, RSI, HWM(트레일링 스탑 최고가), Reasoning을 확인합니다.
    -   **Controls**: 사이드바에서 종목(Symbol)과 시간 봉(Interval)을 변경할 수 있습니다.
-   **🛡️ Risk Monitor**:
    -   **Daily Limits**: 오늘의 손익이 허용 범위(-5%) 내에 있는지 게이지로 확인합니다.
    -   **Status**: 거래 제한(Halt) 상태나 쿨다운 여부를 체크합니다.
-   **📜 Trade History**:
    -   과거의 모든 거래 내역을 검색하고, 매수/매도 비율을 분석합니다.
-   **⚙️ System Health**:
    -   DB, Redis, n8n 등 시스템 구성 요소의 연결 상태를 점검합니다.

### 2.3 자동 새로고침
-   왼쪽 사이드바의 **Auto Refresh** 체크박스를 켜면, 30초마다 화면이 자동 갱신됩니다.

---

## 3. 운영 가이드 (Operation Guide)

### 3.1 봇 시작/종료
Minikube 클러스터 전체를 관리합니다.

| 작업 | 명령어 |
|------|--------|
| **클러스터 시작** | `minikube start` |
| **전체 배포** | `./deploy/deploy_to_minikube.sh` |
| **클러스터 중지** | `minikube stop` |
| **봇 로그 확인** | `kubectl logs -f -l app=bot -n coin-pilot-ns` |
| **Collector 로그** | `kubectl logs -f -l app=collector -n coin-pilot-ns` |
| **전체 파드 상태** | `kubectl get pods -n coin-pilot-ns` |

### 3.2 긴급 상황 대응
*   **거래 멈추기**:
    봇이 이상 행동을 보일 경우, 즉시 파드를 중지시키는 것이 안전합니다.
    ```bash
    kubectl scale deployment bot --replicas=0 -n coin-pilot-ns
    ```
*   **수동 청산**:
    업비트 모바일 앱 또는 웹사이트에서 직접 매도하세요. (봇은 재기동 시 DB 상태를 동기화합니다)

---

## 4. 알림 시스템 (Notification)
*   **Discord**: 매매 체결 및 중요 리스크 경고는 Discord 채널로 즉시 전송됩니다.

---

## 5. 시스템 모니터링 (System Monitoring)
Week 8 업데이트로 **Grafana** 기반의 상세 모니터링이 가능해졌습니다.

### 5.1 접속 방법
Minikube 환경에서는 포트 포워딩을 통해 접속합니다.
```bash
kubectl port-forward -n coin-pilot-ns service/grafana 3000:3000
```
- 주소: [http://localhost:3000](http://localhost:3000)
- 계정: `admin` / `admin` (또는 설정된 비밀번호)

### 5.2 대시보드 설명
**1) CoinPilot Overview**
- **System Metrics**: API 지연 시간(Latency), 에러율 등을 확인합니다.
- **Volatility Index**: 현재 시장의 변동성 지수(GARCH 모델)를 시각화합니다.
    - 변동성이 높으면 리스크 매니저가 거래 비중을 줄입니다.
- **Active Positions**: 실시간 보유 포지션 현황.

**2) CoinPilot Trades**
- **PnL Analysis**: 일별/누적 손익 그래프.
- **Win Rate**: 승률 및 익절/손절 횟수 통계.

---
