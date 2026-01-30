# CoinPilot v3.0 User Manual

**Last Updated**: 2026-01-30
**Version**: v1.0 (Week 6 Complete)

---

## 1. 개요 (Introduction)
CoinPilot v3.0은 Kubernetes 기반의 AI 자동 매매 시스템입니다.
규칙 기반 엔진과 AI 리스크 매니저가 협력하여 안정적인 수익을 추구하며, **Streamlit Dashboard**를 통해 실시간 모니터링이 가능합니다.

---

## 2. 대시보드 사용법 (Dashboard Guide)

### 2.1 실행 방법
로컬 환경(VS Code)에서 대시보드를 실행하려면 다음 2단계가 필요합니다.

1.  **DB 포트 포워딩 (필수)**
    ```bash
    kubectl port-forward -n coin-pilot-ns service/db 5432:5432
    ```
    *주의: 터미널 창을 닫지 마세요.*

2.  **대시보드 앱 실행**
    ```bash
    source .venv/bin/activate
    PYTHONPATH=. streamlit run src/dashboard/app.py
    ```
    브라우저에서 `http://localhost:8501` 접속.

### 2.2 메뉴 설명
-   **📊 Overview**:
    -   **Key Metrics**: 총 거래 횟수, 승률, 누적 손익(PnL)을 확인합니다.
    -   **Active Positions**: 현재 봇이 보유 중인 코인과 수익률을 봅니다.
-   **📈 Market Analysis**:
    -   **Chart**: 비트코인 등 주요 코인의 캔들차트를 확인합니다.
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

*   **시작**: `deploy/deploy_to_minikube.sh`
*   **중지**: `./minikube stop`
*   **로그 확인**: `./minikube kubectl -- logs -f -l app=bot -n coin-pilot-ns`

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
*   **n8n**: 워크플로우 수정이 필요한 경우 `localhost:5678`에 접속하세요. (포트포워딩 필요)
