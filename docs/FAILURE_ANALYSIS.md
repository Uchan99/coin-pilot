# Failure Analysis & Recovery Playbook

**Version**: 1.0
**Target System**: CoinPilot v3.0 (K8s + Streamlit + n8n)

---

## 1. 개요
본 문서는 CoinPilot 운영 중 발생할 수 있는 주요 장애 유형과 대응 절차를 정의합니다.
Week 4~6 개발 과정에서 실제로 겪은 이슈들을 바탕으로 작성되었습니다.

---

## 2. 주요 장애 유형 및 대응 (Common Failures)

### Type A: DB 접속 불가 (Connection Refused)
*   **증상**: 대시보드나 봇 로그에 `Connection refused` 또는 `Address already in use` 발생.
*   **원인**:
    1.  Minikube 클러스터가 중지됨.
    2.  `kubectl port-forward` 프로세스가 좀비 상태로 남아서 포트 점유.
    3.  로컬의 다른 PostgreSQL이 5432 포트 사용.
*   **대응 절차**:
    1.  Minikube 상태 확인: `./minikube status` -> 꺼져있으면 `./minikube start`
    2.  포트 점유 프로세스 강제 종료:
        ```bash
        lsof -t -i:5432 | xargs -r kill -9
        ```
    3.  포트 포워딩 재시도:
        ```bash
        kubectl port-forward -n coin-pilot-ns service/db 5432:5432
        ```

### Type B: 대시보드 무한 로딩 / 에러 (Streamlit Async Loop)
*   **증상**: `InterfaceError`, `Task attached to a different loop`.
*   **원인**: Streamlit의 리로드 메커니즘과 AsyncIO Engine이 충돌.
*   **대응 절차**:
    1.  `db_connector.py`가 **Sync Engine (psycopg2)** 을 사용하고 있는지 확인하세요.
    2.  앱을 완전히 껐다가 다시 켭니다 (Ctrl+C -> 재실행).
    3.  브라우저 강력 새로고침 (Ctrl+Shift+R).

### Type C: 알림 발송 실패 (n8n Webhook Error)
*   **증상**: 매매는 체결되었는데 디스코드 알림이 안 옴.
*   **확인 방법**:
    1.  n8n UI 접속 (`localhost:5678`) -> Executions 탭 확인.
    2.  실패한 실행 로그 클릭하여 원인 파악 (보통 Discord API 포맷 문제).
*   **대응 절차**:
    1.  n8n 설정 수정 후 활성화(Active) 상태 재확인.
    2.  Engine 로그에서 Webhook URL이 올바른지 확인.

### Type D: Redis 연결 실패
*   **증상**: 대시보드 System Health에서 Redis가 🔴 Error 표시.
*   **원인**:
    1.  Redis 파드가 실행되지 않음.
    2.  Redis 포트 포워딩 누락.
*   **대응 절차**:
    1.  파드 상태 확인:
        ```bash
        kubectl get pods -l app=redis -n coin-pilot-ns
        ```
    2.  포트 포워딩 실행:
        ```bash
        kubectl port-forward -n coin-pilot-ns service/redis 6379:6379
        ```

### Type E: 봇 파드 CrashLoopBackOff
*   **증상**: `kubectl get pods`에서 봇 파드가 `CrashLoopBackOff` 상태.
*   **원인**:
    1.  환경 변수 누락 (API Key, DB URL 등).
    2.  코드 버그로 인한 즉시 종료.
    3.  DB 연결 실패로 초기화 중 에러.
*   **대응 절차**:
    1.  로그 확인:
        ```bash
        kubectl logs -l app=bot -n coin-pilot-ns --previous
        ```
    2.  ConfigMap/Secret 확인:
        ```bash
        kubectl get configmap -n coin-pilot-ns
        kubectl get secret -n coin-pilot-ns
        ```
    3.  DB 파드 상태 우선 확인 후 봇 재배포.

### Type F: TimescaleDB 쿼리 실패 (time_bucket 에러)
*   **증상**: Market 페이지에서 `function time_bucket does not exist` 에러.
*   **원인**: TimescaleDB 확장이 활성화되지 않음.
*   **대응 절차**:
    1.  DB에 접속하여 확장 확인:
        ```sql
        SELECT * FROM pg_extension WHERE extname = 'timescaledb';
        ```
    2.  확장이 없으면 활성화:
        ```sql
        CREATE EXTENSION IF NOT EXISTS timescaledb;
        ```

---

## 3. 예방 점검 리스트 (Preventive Checks)
봇을 가동하기 전, 다음 항목을 반드시 체크하세요.

-   [ ] **Minikube Check**: `kubectl get pods -n coin-pilot-ns` -> 모든 파드가 `Running` 인가?
-   [ ] **DB Connection**: 대시보드 `System Health` 페이지에서 DB/Redis가 녹색(🟢)인가?
-   [ ] **Time Check**: 타임스케일DB와 시스템 시간이 UTC 기준으로 일치하는가?

---

## 4. 긴급 대응 명령어 (Quick Reference)

| 상황 | 명령어 |
|------|--------|
| **봇 즉시 중지** | `kubectl scale deployment bot --replicas=0 -n coin-pilot-ns` |
| **봇 재시작** | `kubectl rollout restart deployment bot -n coin-pilot-ns` |
| **전체 파드 재시작** | `kubectl delete pods --all -n coin-pilot-ns` |
| **특정 파드 강제 종료** | `kubectl delete pod <pod-name> -n coin-pilot-ns --force` |
| **포트 충돌 해제** | `lsof -t -i:5432 \| xargs -r kill -9` |
| **Minikube 재시작** | `minikube stop && minikube start` |

---

## 5. 롤백 절차 (Rollback)

배포 후 문제가 발생한 경우:

```bash
# 1. 이전 버전으로 롤백
kubectl rollout undo deployment bot -n coin-pilot-ns

# 2. 롤백 상태 확인
kubectl rollout status deployment bot -n coin-pilot-ns

# 3. 히스토리 확인
kubectl rollout history deployment bot -n coin-pilot-ns
```

---

## 6. 참고 문서
-   [Week 5 Troubleshooting](troubleshooting/week5-ts.md): n8n 및 알림 관련 이슈
-   [Week 6 Troubleshooting](troubleshooting/week6-ts.md): 대시보드 및 DB 연결 이슈
-   [Daily Startup Guide](guides/daily-startup.md): 일일 시작 가이드
