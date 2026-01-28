# Week 5 Troubleshooting Report: Notification System (n8n + Discord)

**Project**: CoinPilot - AI-Powered Cryptocurrency Trading System
**Author**: Hur Youchan
**Date**: 2026-01-29
**Tech Stack**: n8n, Discord Webhook, Kubernetes, Python

---

## Executive Summary

Week 5는 n8n과 Discord를 연동하는 알림 시스템 구축 단계였습니다. 이 과정에서 **n8n 워크플로우 설정**, **Discord API 규격**, **Kubernetes 환경 변수 접근**과 관련된 문제들이 발생했습니다. 이를 해결하며 **Golden Config(검증된 설정 패턴)** 를 확립하고, 외부 API 연동 시 주의해야 할 점들을 학습했습니다.

### Skills Demonstrated
`n8n Workflow Debugging` `Discord API Integration` `Kubernetes Secret/ConfigMap` `Environment Variable Security` `HTTP Method Troubleshooting`

### Issues at a Glance

| # | Issue | Severity | Root Cause | Resolution Time |
|---|-------|----------|------------|-----------------|
| 1 | HTTP Method Reset | High | n8n Import 시 GET으로 초기화 | ~1h |
| 2 | 400 Bad Request | Medium | Discord Payload 형식 불일치 | ~30m |
| 3 | Env Var UI Warning | Low | n8n 보안 정책 (정상 동작) | ~15m |
| 4 | K8s 내부 통신 혼동 | Low | localhost vs Service Name | ~10m |

---

## 개요
Week 5 (n8n 및 Discord 알림 시스템 구축) 과정에서 발생한 주요 이슈와 해결 과정을 기록합니다.
주로 **n8n 설정(Method), Discord API 규격, Kubernetes 환경 변수**와 관련된 문제들이었으며, 이를 통해 **Golden Config(검증된 설정 패턴)** 를 확립했습니다.

---

## 1. n8n HTTP Request Method Reset Issue
### 현상
-   `trade_notification.json` 파일을 Import 한 후 테스트를 진행했으나 Discord로 알림이 오지 않음.
-   n8n 실행 로그에는 성공(Green)으로 표시되지만, 실제로는 Discord Webhook이 동작하지 않음.

### 원인 분석
-   n8n 구버전(또는 특정 버전 호환성) 이슈로 인해, JSON Import 시 **HTTP Request Method가 `GET`으로 초기화**되는 현상 발견.
-   Discord Webhook은 데이터를 보내려면 반드시 **`POST`** 메서드를 사용해야 함. `GET` 요청은 단순히 Webhook 정보만 조회하고 끝남.

### 해결 (Solution)
-   **조치**: Import 후 반드시 `Discord Webhook` 노드를 열어 **Method를 `POST`로 수동 변경**.
-   **교훈**: n8n 워크플로우를 파일로 관리/배포할 때, Import 후에는 반드시 주요 설정(Method, Auth)이 유지되었는지 검수가 필요함.

---

## 2. Discord Payload Format (400 Bad Request)
### 현상
-   Method를 `POST`로 변경 후 전송했으나, `400 Bad Request` 에러 발생.
-   에러 메시지: `Cannot send an empty message`.

### 원인 분석
-   초기에 Discord의 고급 기능인 `embeds` (리치 텍스트) 형식을 사용하려 했으나, JSON 구조가 복잡하여 n8n의 Expression 처리 과정에서 문법 오류(Syntax Error) 또는 빈 값이 전송됨.
-   `Send Body` 옵션이 꺼져있거나, Parameter 설정이 올바르지 않은 경우도 있었음.

### 해결 (Solution)
-   **조치 1**: 복잡한 `embeds` 대신 가장 단순하고 확실한 **`content` (일반 텍스트)** 필드 사용으로 전략 변경.
-   **조치 2**: `Send Body` 옵션을 켜고, `Body Parameters` > `Name: content` > `Value: {{message}}` 형태로 단순화하여 통신 성공.
-   **결과**: 통신 파이프라인(Pipeline)이 확실히 뚫린 것을 확인한 후, 포맷팅은 차후 개선 사항으로 넘김.

---

## 3. Environment Variable Access in UI
### 현상
-   보안을 위해 Webhook URL을 직접 입력하지 않고 `{{$env.DISCORD_WEBHOOK_URL}}`을 사용.
-   n8n UI 편집기에서 해당 변수 입력 시 **`[not accessible via UI]`** 라는 빨간색 에러 메시지가 표시됨.

### 원인 분석
-   n8n의 보안 정책상, 환경 변수는 노드가 **실제로 실행(Run)** 될 때만 접근 가능하며, UI 편집 모드에서는 보안상 값을 노출하지 않음(Masking).
-   이는 오류가 아니라 정상적인 보안 기능임.

### 해결 (Solution)
-   **조치**: UI의 경고 메시지를 무시하고, 실제 **`Execute Node`** 버튼을 눌러 테스트 실행.
-   **결과**: 실제 실행 로그에서는 환경 변수 값이 정상적으로 치환되어 Discord로 메시지가 전송됨을 확인.
-   **참고**: Kubernetes 배포 시 `N8N_BLOCK_ENV_ACCESS_IN_NODE: "false"` 환경 변수 설정이 필수적임 (이게 `true`면 실제 실행 때도 접근 막힘).

---

## 4. Kubernetes vs Localhost Networking
### 현상
-   로컬(PC)에서 `curl`로 테스트할 때는 `localhost:5678`을 쓰지만, n8n 내부에서 다른 파드(예: DB)에 접속하려 할 때 연결 실패 가능성.

### 원인 & 해결
-   **원인**: Kubernetes 내부에서는 `localhost`가 각 파드(Pod) 자신을 가리킴.
-   **해결**: 파드 간 통신에는 **Kubernetes Service Name**을 사용해야 함.
    -   예: n8n이 PostgreSQL에 접속하려면 `host: localhost`가 아니라 `host: db` (서비스명)를 사용.

---

## 5. Summary: The "Golden Config" for Discord
최종적으로 확립된 n8n Discord 연동 표준 설정입니다.

1.  **Request Method**: `POST` (필수)
2.  **URL**: `{{$env.DISCORD_WEBHOOK_URL}}` (환경 변수 사용)
3.  **Authentication**: `None` (Webhook URL 자체에 토큰 포함)
4.  **Send Body**: `True` (켜기)
5.  **Body Parameters**:
    -   Name: `content`
    -   Value: `{{ "메시지 내용..." }}` (Expression 사용)

이 설정만 지키면 어떤 워크플로우에서도 안정적으로 알림을 보낼 수 있습니다.

---

## 6. Prevention & Lessons Learned (재발 방지 및 교훈)

### 6.1 체크리스트: n8n 워크플로우 배포 전 확인사항

```markdown
[ ] HTTP Request 노드의 Method가 POST인가?
[ ] URL이 하드코딩이 아닌 환경 변수({{$env.xxx}})를 사용하는가?
[ ] Send Body 옵션이 활성화되어 있는가?
[ ] Body Parameters에 content 필드가 정의되어 있는가?
[ ] K8s Deployment에 N8N_BLOCK_ENV_ACCESS_IN_NODE: "false"가 설정되어 있는가?
```

### 6.2 핵심 교훈

| 문제 유형 | 교훈 | 예방 조치 |
|----------|------|----------|
| **Import 후 설정 초기화** | 자동화 도구도 버전/호환성 이슈가 있음 | Import 후 반드시 주요 설정 검수 |
| **외부 API 연동 실패** | 복잡한 구조보다 단순한 것부터 검증 | MVP 방식으로 먼저 통신 확인, 이후 고도화 |
| **UI 경고 vs 실제 동작** | UI 표시와 런타임 동작은 다를 수 있음 | 실제 실행(Execute)으로 최종 검증 |
| **K8s 네트워킹** | localhost는 Pod 자신을 가리킴 | 파드 간 통신은 Service Name 사용 |

### 6.3 향후 유사 작업 시 권장 순서

```
1. 최소 기능으로 통신 테스트 (curl → n8n → Discord)
2. 환경 변수 및 Secret 설정 검증
3. 워크플로우 Import 후 설정 검수
4. 실제 Execute로 End-to-End 테스트
5. 복잡한 포맷(Embeds 등)은 통신 확보 후 적용
```

---

## 7. References

- [n8n Documentation - Environment Variables](https://docs.n8n.io/hosting/environment-variables/)
- [Discord Webhook API](https://discord.com/developers/docs/resources/webhook)
- [Week 5 Walkthrough](../work-result/week5-walkthrough.md)
