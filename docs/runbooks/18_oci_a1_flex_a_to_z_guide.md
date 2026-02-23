# 18. OCI A1.Flex 인스턴스 생성/재시도 A to Z 가이드 (학생용)

작성일: 2026-02-22
상태: Ready
대상: OCI/CLI를 처음 쓰는 사용자
관련 문서:
- `docs/runbooks/18_oci_a1_flex_auto_retry_runbook.md`
- `docs/runbooks/18_data_migration_runbook.md`
관련 스크립트:
- `scripts/cloud/oci_retry_launch_a1_flex.sh`
- `scripts/cloud/run_oci_retry_from_env.sh`
- `scripts/cloud/oci_retry.env.example`

---

## 0. 목표

이 가이드는 아래 작업을 끝까지 수행하는 것이 목표다.

1. OCI CLI 인증 완료
2. 기존 VCN/서브넷/보안규칙을 재사용
3. `coinpilot-ins` 인스턴스를 A1.Flex(2 OCPU / 12GB)로 자동 재시도 생성
4. 데스크톱을 껐다 켜도 1줄 명령으로 재시작
5. 보안 기준(외부 포트 최소화/시크릿 점검)을 만족한 상태로 운영 시작

---

## 1. 먼저 알아둘 개념

### 1.1 OCID란?
- OCI 리소스의 고유 ID 문자열이다.
- 예: `ocid1.compartment...`, `ocid1.subnet...`, `ocid1.tenancy...`

### 1.2 왜 자동 재시도가 필요할까?
- Chuncheon 리전에서 A1.Flex는 `Out of host capacity`가 자주 발생한다.
- 설정 오류가 아니라 용량 부족이므로, 주기적 재시도가 실용적이다.

### 1.3 private key는 어디 저장되나?
- 인스턴스 SSH key는 로컬 PC의 `~/.ssh/coinpilot-oci/`에 저장된다.
- API signing key는 `~/.oci/`에 저장된다.
- 둘 다 절대 외부 공유 금지.

### 1.4 외부에서 열어도 되는 포트는?
- 기본 원칙: `22`, `80`, `443`만 외부 허용
  - `22`: SSH 원격 접속
  - `80`: HTTP -> HTTPS 리다이렉트/인증서 발급
  - `443`: HTTPS 서비스
- 아래 포트는 외부 공개 금지:
  - `5432`, `6379`, `5678`, `8000`, `8501`, `9090`, `3000`

---

## 2. 사전 준비 (WSL 기준)

### 2.1 왜 WSL에서 실행하나?
- 프로젝트 스크립트가 bash 기반이므로 WSL에서 실행이 가장 안정적이다.
- PowerShell만 써도 되지만, 이 가이드는 WSL을 기준으로 설명한다.

### 2.2 필수 패키지 설치
```bash
sudo apt update
sudo apt install -y python3-pip pipx jq curl
pipx ensurepath
export PATH="$HOME/.local/bin:$PATH"
pipx install oci-cli
```

확인:
```bash
oci --version
jq --version
```

---

## 3. OCI CLI 인증 (처음 1회)

### 3.1 설정 시작
```bash
oci setup config
```

### 3.2 프롬프트 입력 방법
1. User OCID 입력
- 콘솔 경로: 우측 상단 프로필 아이콘 -> `User settings`
- `OCID` 복사 후 붙여넣기

2. Tenancy OCID 입력
- 콘솔 경로: 우측 상단 프로필 아이콘 -> `Tenancy: <이름>`
- `OCID` 복사 후 붙여넣기

3. Region 선택
- `ap-chuncheon-1` 입력

4. API Signing Key 생성
- `Y` 선택
- 경로/파일명은 기본값 사용 가능
- passphrase는 아래 둘 중 하나 선택
  - 보안 우선: passphrase 설정
  - 자동화 우선: 빈 값(엔터) 또는 `N/A` 방식

### 3.3 공개키 콘솔 등록
```bash
cat ~/.oci/oci_api_key_public.pem
```
출력 전체(`-----BEGIN PUBLIC KEY-----` ~ `-----END PUBLIC KEY-----`)를 복사해서,

- 콘솔 경로: `User settings` -> `API Keys` -> `Add API Key`
- `Paste public keys`로 등록

### 3.4 인증 확인
```bash
oci iam availability-domain list \
  --profile DEFAULT \
  --compartment-id <COMPARTMENT_OCID> \
  --query 'data[0].name' --raw-output
```
정상 예시: `UBJq:AP-CHUNCHEON-1-AD-1`

---

## 4. 필수 OCID 수집 (A to Z)

### 4.1 `COMPARTMENT_OCID`
- 경로: `Identity & Security` -> `Compartments` -> `coinpilot-prod`
- OCID 복사

### 4.2 `SUBNET_OCID`
- 경로: `Networking` -> `Virtual Cloud Networks` -> `coinpilot-vcn` -> `Subnets`
- `public subnet-coinpilot-vcn` 클릭 -> OCID 복사

### 4.3 `AVAILABILITY_DOMAIN`
- CLI로 확인:
```bash
oci iam availability-domain list \
  --profile DEFAULT \
  --compartment-id <COMPARTMENT_OCID> \
  --query 'data[0].name' --raw-output
```

### 4.4 `IMAGE_COMPARTMENT_OCID` (중요)
- 플랫폼 이미지 조회가 프로젝트 compartment에서 실패할 수 있어,
- **tenancy(root) OCID**를 넣는 것을 권장한다.
- 경로: 우측 상단 프로필 아이콘 -> `Tenancy: <이름>` -> OCID 복사

---

## 5. 한 번만 만들어두면 재부팅 후 편한 방식 (권장)

### 5.1 환경파일 생성
```bash
cd /home/syt07203/workspace/coin-pilot
cp scripts/cloud/oci_retry.env.example scripts/cloud/oci_retry.env
chmod 600 scripts/cloud/oci_retry.env
```

### 5.2 파일 수정
```bash
nano scripts/cloud/oci_retry.env
```
아래 키는 반드시 실제 값으로 수정한다.
- `COMPARTMENT_OCID`
- `SUBNET_OCID`
- `AVAILABILITY_DOMAIN`
- `IMAGE_COMPARTMENT_OCID` (tenancy OCID 권장)

기본값 유지 항목(요구사항 반영):
- `INSTANCE_NAME=coinpilot-ins`
- `SHAPE=VM.Standard.A1.Flex`
- `OCPUS=2`
- `MEMORY_GBS=12`

선택:
- `DISCORD_WEBHOOK_URL`
- `DISCORD_NOTIFY_EVERY_N_ATTEMPTS`

---

## 6. 인스턴스 자동 재시도 실행

### 6.1 권장 실행 (환경파일 사용)
```bash
cd /home/syt07203/workspace/coin-pilot
./scripts/cloud/run_oci_retry_from_env.sh
```

### 6.2 동작 설명
1. `oci_retry.env`를 읽어 환경변수 export
2. 이미지 OCID 자동 탐색(필요 시)
3. 인스턴스 생성 시도
4. `Out of host capacity`면 대기 후 재시도
5. 성공 시 `instance_id/public_ip/ssh 경로` 출력 후 종료

---

## 7. 성공 확인과 SSH 접속

성공 로그에 아래 값이 나온다.
- `instance_id`
- `public_ip`
- `private_key` 경로

접속 예시:
```bash
ssh -i ~/.ssh/coinpilot-oci/coinpilot-ins_a1_flex ubuntu@<PUBLIC_IP>
```

---

## 8. Discord 알림 연결 (선택)

`oci_retry.env`에 아래를 설정하면 된다.
```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy
DISCORD_NOTIFY_EVERY_N_ATTEMPTS=10
```

알림 시점:
1. 시작
2. 진행(기본 10회마다)
3. capacity 재시도
4. 성공
5. 비재시도 오류

---

## 9. 데스크톱 종료 후 다시 켰을 때 (재개 가이드)

### 9.1 핵심 요약
- 기존 실행은 PC 종료와 함께 중단된다.
- 다시 켜면 **아래 1줄만 실행**하면 된다.

```bash
cd /home/syt07203/workspace/coin-pilot && ./scripts/cloud/run_oci_retry_from_env.sh
```

### 9.2 재개 전 점검(30초)
```bash
oci --version
jq --version
test -f /home/syt07203/workspace/coin-pilot/scripts/cloud/oci_retry.env && echo "env ok"
```

보안 점검(권장):
```bash
cd /home/syt07203/workspace/coin-pilot
./scripts/security/preflight_security_check.sh
```

### 9.3 오래 켜둘 때 권장
`tmux`를 사용하면 터미널이 끊겨도 백그라운드 유지가 쉽다.

```bash
sudo apt install -y tmux
tmux new -s oci-retry
cd /home/syt07203/workspace/coin-pilot
./scripts/cloud/run_oci_retry_from_env.sh
# 분리: Ctrl+b, d
# 재접속: tmux attach -t oci-retry
```

---

## 10. 자주 겪는 오류와 해결

1. `oci: command not found`
- OCI CLI 미설치 -> 2.2 단계 다시 수행

2. `NotAuthenticated (401)`
- API key 등록 누락/오입력 -> 3.3 재확인

3. `Out of host capacity`
- 정상 재시도 대상 -> 스크립트 유지

4. `failed to resolve IMAGE_OCID automatically`
- `IMAGE_COMPARTMENT_OCID`를 tenancy OCID로 수정

5. `command not found: jq`
- `sudo apt install -y jq`

---

## 11. 보안 체크리스트

1. 권한
```bash
chmod 700 ~/.oci ~/.ssh ~/.ssh/coinpilot-oci
chmod 600 ~/.oci/oci_api_key.pem ~/.ssh/coinpilot-oci/coinpilot-ins_a1_flex
chmod 600 /home/syt07203/workspace/coin-pilot/scripts/cloud/oci_retry.env
```

2. 금지 사항
- private key를 Git/메신저/이메일로 전송 금지
- `oci_retry.env`를 원격 저장소에 커밋 금지

---

## 12. 다음 단계

인스턴스 생성 성공 후 아래 순서로 이어간다.
1. SSH 접속
2. `/opt/coin-pilot` 코드 동기화
3. `deploy/cloud/oci/.env` 준비
4. `bootstrap.sh` 실행
5. `docker compose -f deploy/cloud/oci/docker-compose.prod.yml up -d --build`

자세한 운영 전환은 아래 문서를 따른다.
- `docs/runbooks/18_data_migration_runbook.md`

---

## 13. References (Primary)
- OCI CLI 개념: https://docs.oracle.com/en-us/iaas/Content/API/Concepts/cliconcepts.htm
- OCI CLI compute launch: https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/compute/instance/launch.html
- Always Free resources: https://docs.oracle.com/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- API errors: https://docs.oracle.com/iaas/Content/API/References/apierrors.htm
