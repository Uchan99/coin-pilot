# 20-01 OCI VM 런타임 보안 검증 체크리스트 (Compose 운영)

작성일: 2026-02-23  
대상: `/opt/coin-pilot` 운영 VM  
관련 계획: `docs/work-plans/20-01_project_wide_security_hardening_plan.md`  

---

## 0. 목적
- 배포 직후, 컨테이너가 정상 동작하는지와 보안 가드레일(포트/권한/시크릿 fail-fast)이 실제 런타임에서 유지되는지 확인한다.

## 1. 사전 조건
1. SSH 접속 완료
2. 경로 이동:
```bash
cd /opt/coin-pilot
```
3. 운영 env 파일 존재/권한 확인:
```bash
ls -l deploy/cloud/oci/.env
```
기대값:
- 권한이 `-rw-------` (600)

## 2. 배포 전 정적 검증 (필수)
1. preflight 보안 점검:
```bash
./scripts/security/preflight_security_check.sh /opt/coin-pilot/deploy/cloud/oci/.env
```
기대값:
- 마지막 줄이 `[RESULT] PASSED`

2. compose 렌더링 검증:
```bash
docker compose --env-file deploy/cloud/oci/.env \
  -f deploy/cloud/oci/docker-compose.prod.yml config >/tmp/coinpilot-compose.resolved.yml
```
기대값:
- 에러 없이 종료

## 3. 배포/재기동
```bash
docker compose --env-file deploy/cloud/oci/.env \
  -f deploy/cloud/oci/docker-compose.prod.yml up -d --build
```

## 4. 런타임 상태 검증 (필수)
1. 서비스 상태:
```bash
docker compose --env-file deploy/cloud/oci/.env \
  -f deploy/cloud/oci/docker-compose.prod.yml ps
```
기대값:
- `coinpilot-db`, `coinpilot-redis`, `coinpilot-collector`, `coinpilot-bot`, `coinpilot-dashboard`, `coinpilot-n8n`, `coinpilot-prometheus`, `coinpilot-grafana`가 모두 `Up`

2. DB Health:
```bash
docker inspect -f '{{.State.Health.Status}}' coinpilot-db
```
기대값:
- `healthy`

3. 공개 포트 점검(외부 노출 금지 포트):
```bash
sudo ss -tulpen | egrep ':(5432|6379|5678|9090|3000|8501|8000)\b'
```
기대값:
- 서비스가 떠 있더라도 host 바인딩은 `127.0.0.1:*` 또는 미바인딩
- `0.0.0.0:*`로 보이면 즉시 수정 필요

4. 앱 컨테이너 사용자 확인(non-root):
```bash
docker exec coinpilot-bot id -u
docker exec coinpilot-collector id -u
docker exec coinpilot-dashboard id -u
```
기대값:
- 모두 `0`이 아닌 값(=root 아님)

## 5. 기본 기능 스모크 체크
1. Dashboard (포워딩 후):
```bash
ssh -L 8501:127.0.0.1:8501 -i <PRIVATE_KEY> ubuntu@<OCI_PUBLIC_IP>
```
- 브라우저 `http://localhost:8501`
- 비밀번호 가드 동작 확인

2. Grafana:
```bash
ssh -L 3000:127.0.0.1:3000 -i <PRIVATE_KEY> ubuntu@<OCI_PUBLIC_IP>
```
- 브라우저 `http://localhost:3000`
- 변경한 관리자 계정으로 로그인 확인

3. n8n:
```bash
ssh -L 5678:127.0.0.1:5678 -i <PRIVATE_KEY> ubuntu@<OCI_PUBLIC_IP>
```
- 브라우저 `http://localhost:5678`
- Basic Auth 적용 확인

## 6. 실패 시 즉시 조치
1. 컨테이너 로그 확인:
```bash
docker compose --env-file deploy/cloud/oci/.env \
  -f deploy/cloud/oci/docker-compose.prod.yml logs --tail=100
```

2. 특정 서비스만 재시작:
```bash
docker compose --env-file deploy/cloud/oci/.env \
  -f deploy/cloud/oci/docker-compose.prod.yml up -d <service_name>
```

3. 시크릿 누락/오타가 의심되면:
- `deploy/cloud/oci/.env` 값 재검토
- `./scripts/security/preflight_security_check.sh` 재실행

## 7. 완료 체크
1. preflight `PASSED`
2. compose `ps` 전 서비스 `Up`
3. DB `healthy`
4. 금지 포트의 `0.0.0.0` 바인딩 없음
5. app 컨테이너 non-root 확인
