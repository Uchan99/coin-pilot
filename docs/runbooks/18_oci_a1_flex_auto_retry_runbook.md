# 18. OCI A1.Flex 자동 재시도 생성 Runbook (기존 네트워크 재사용)

작성일: 2026-02-22
상태: Ready
관련 계획서: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`
관련 결과서: `docs/work-result/18_cloud_migration_cost_optimized_result.md`
관련 스크립트: `scripts/cloud/oci_retry_launch_a1_flex.sh`
빠른 시작 가이드: `docs/runbooks/18_oci_a1_flex_a_to_z_guide.md`

---

## 0. 왜 이 방법을 쓰는가

현재 홈 리전(Chuncheon)에서 `VM.Standard.A1.Flex`가 자주 `Out of capacity`를 반환한다.
수동으로 콘솔 재시도하는 대신, 인스턴스 생성 요청을 주기적으로 반복해 성공 시 즉시 종료하는 자동화가 더 실용적이다.

### 선택한 방식
- **OCI CLI + Bash 재시도 스크립트**
- 기존 VCN/서브넷/보안규칙은 그대로 사용
- 인스턴스만 아래 고정 조건으로 생성 시도
  - Name: `coinpilot-ins`
  - Image: `Canonical Ubuntu 22.04 Minimal aarch64`
  - Shape: `VM.Standard.A1.Flex`
  - OCPU: `2`
  - Memory: `12GB`

### 대안 비교
1. 콘솔 수동 재시도
- 장점: 도구 설치 불필요
- 단점: 반복 피로도 높고 성공 타이밍 놓치기 쉬움

2. Terraform 반복 apply
- 장점: IaC 일관성 높음
- 단점: capacity 실패 시 루프 제어/에러 핸들링이 상대적으로 복잡

3. OCI CLI 재시도 스크립트(채택)
- 장점: 즉시 적용 가능, 실패 유형 분기 단순, 로그/키 파일 관리 용이
- 단점: 로컬 실행 환경(oci cli/jq) 준비 필요

---

## 1. 사전 준비

### 1.1 로컬 PC에서 필요한 도구
1. `oci` CLI
2. `jq`
3. `ssh-keygen` (OpenSSH)

확인:
```bash
oci --version
jq --version
ssh -V
```

### 1.2 OCI 정보 확보
1. `COMPARTMENT_OCID`
2. `SUBNET_OCID` (기존 `public subnet-coinpilot-vcn`)
3. `AVAILABILITY_DOMAIN` (예: `UBJq:AP-CHUNCHEON-1-AD-1`)
4. `IMAGE_OCID` (`Canonical Ubuntu 22.04 Minimal aarch64`) - 선택(자동 탐색 가능)
5. `IMAGE_COMPARTMENT_OCID` - 선택(기본: `COMPARTMENT_OCID`)

`IMAGE_OCID` 조회 예시(수동 지정 시):
```bash
oci compute image list \
  --compartment-id <TENANCY_OCID> \
  --all \
  --shape VM.Standard.A1.Flex \
  --operating-system "Canonical Ubuntu" \
  --operating-system-version "22.04" \
  --query 'data[?contains("display-name", `Minimal`) && contains("display-name", `aarch64`)].{name:"display-name",id:id} | [0]' \
  --raw-output
```

참고:
- 콘솔에서 이미지 상세 페이지를 열어 `Image OCID`를 직접 복사하는 방식이 가장 확실하다.
- 스크립트는 `IMAGE_OCID`가 비어 있으면 `Canonical Ubuntu 22.04 + Minimal + aarch64` 조건으로 최신 이미지를 자동 탐색한다.
- 프로젝트 compartment에서 플랫폼 이미지 조회가 안 되는 경우, `IMAGE_COMPARTMENT_OCID`를 **tenancy(root) OCID**로 지정한다.

---

## 2. 실행 방법 (복붙 순서)

### 2.1 환경변수 설정
아래 값만 본인 환경에 맞게 바꾼다.

```bash
export OCI_PROFILE="DEFAULT"
export COMPARTMENT_OCID="ocid1.compartment.oc1..xxxx"
export SUBNET_OCID="ocid1.subnet.oc1.ap-chuncheon-1.xxxx"
export AVAILABILITY_DOMAIN="UBJq:AP-CHUNCHEON-1-AD-1"
export IMAGE_OCID="ocid1.image.oc1.ap-chuncheon-1.xxxx"
export IMAGE_COMPARTMENT_OCID="ocid1.tenancy.oc1..xxxx"   # 선택

export INSTANCE_NAME="coinpilot-ins"
export OCPUS="2"
export MEMORY_GBS="12"
export RETRY_INTERVAL_SECONDS="600"
export MAX_ATTEMPTS="0"
export THROTTLE_RETRY_BASE_SECONDS="900"
export THROTTLE_RETRY_MAX_SECONDS="3600"
export THROTTLE_JITTER_MAX_SECONDS="120"
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/xxx/yyy"   # 선택
export DISCORD_NOTIFY_EVERY_N_ATTEMPTS="10"                              # 선택
```

### 2.2 스크립트 실행
```bash
cd /home/syt07203/workspace/coin-pilot
./scripts/cloud/oci_retry_launch_a1_flex.sh
```

### 2.3 성공 시 기대 결과
스크립트가 아래 정보를 출력하고 종료한다.
1. `instance_id`
2. `public_ip`
3. `private_key` 저장 경로
4. `launch_result_json` 저장 경로

SSH 접속 예시도 함께 출력된다.

### 2.4 Discord 알림(선택)
- 스크립트는 `DISCORD_WEBHOOK_URL`이 설정된 경우에만 알림을 보낸다.
- 기본 알림 시점:
  1. 재시도 시작
  2. 재시도 진행(기본 10회마다)
  3. 용량 부족 재시도 상태
  4. 인스턴스 생성 성공
  5. 비재시도 오류 종료
- 알림 간격은 `DISCORD_NOTIFY_EVERY_N_ATTEMPTS`로 조절한다.

---

## 3. private key 저장 관련 (질문 답변)

질문: "private key도 저장해줄 수 있나?"

답: **가능하다.** 단, 저장 위치는 "실행한 로컬 PC"다.

- 스크립트는 아래 경로에 키를 자동 생성/보관한다.
  - private key: `~/.ssh/coinpilot-oci/coinpilot-ins_a1_flex`
  - public key: `~/.ssh/coinpilot-oci/coinpilot-ins_a1_flex.pub`
- 이미 키가 있으면 재사용한다.
- 권한은 자동으로 `600`(private), `644`(public)으로 맞춘다.

중요:
- private key는 OCI 콘솔에서 나중에 다시 다운로드할 수 없다.
- 반드시 키 파일을 안전하게 백업해 둔다.

---

## 4. 실패 케이스 대응

### 4.1 `Out of capacity for shape`
- 정상 재시도 대상이다.
- 스크립트가 자동으로 대기 후 반복 시도한다.

### 4.2 `TooManyRequests` (HTTP 429)
- 정상 재시도 대상이다.
- OCI API 스로틀링 상황으로 보고, 용량 부족(`RETRY_INTERVAL_SECONDS`)보다 긴 대기시간으로 자동 백오프 재시도한다.
- 기본값:
  - `THROTTLE_RETRY_BASE_SECONDS=900` (15분)
  - `THROTTLE_RETRY_MAX_SECONDS=3600` (60분 상한)
  - `THROTTLE_JITTER_MAX_SECONDS=120` (0~120초 랜덤 지터)

### 4.3 `NotAuthorizedOrNotFound` / 권한 오류
- 재시도 대상이 아니다.
- IAM 정책/OCID 값을 먼저 점검한다.

### 4.4 `InvalidParameter` / 이미지-셰이프 불일치
- 이미지가 `aarch64`인지 확인한다.
- Shape는 `VM.Standard.A1.Flex`로 고정한다.

---

## 5. 성공 직후 다음 단계

1. SSH 접속
```bash
ssh -i ~/.ssh/coinpilot-oci/coinpilot-ins_a1_flex ubuntu@<PUBLIC_IP>
```

2. CoinPilot 배포 준비
- `/opt/coin-pilot` 코드 동기화
- `deploy/cloud/oci/.env` 준비
- `bootstrap.sh` 실행
- `docker compose -f deploy/cloud/oci/docker-compose.prod.yml up -d --build`

상세는 아래 문서를 따른다.
- `docs/runbooks/18_data_migration_runbook.md`

---

## 6. 가정/미확정/리스크

### 6.1 가정
1. OCI CLI 인증(`~/.oci/config`)이 이미 완료되어 있다.
2. 기존 VCN/서브넷/보안규칙은 콘솔에서 유효 상태다.

### 6.2 미확정 사항
1. Chuncheon 리전의 A1 host capacity 확보 시점은 예측 불가
2. 계정/테넌시별 quota 제한 상이 가능

### 6.3 리스크
1. 무한 재시도(`MAX_ATTEMPTS=0`)로 장시간 실행 가능
2. 잘못된 OCID 입력 시 계속 실패 로그 누적
3. 키 파일 분실 시 SSH 접속 복구 절차 필요

완화:
1. `MAX_ATTEMPTS`를 유한값으로 지정해 상한 통제
2. 실행 전 `COMPARTMENT_OCID/SUBNET_OCID/IMAGE_OCID` 재검증
3. 키 파일 이중 백업(암호화 저장소 권장)

---

## 7. 검증 명령

```bash
bash -n scripts/cloud/oci_retry_launch_a1_flex.sh
```

성공 기준:
- 문법 오류 없이 종료

---

## 8. References (Primary)
- OCI CLI `compute instance launch`: https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/compute/instance/launch.html
- OCI CLI config: https://docs.oracle.com/en-us/iaas/Content/API/Concepts/cliconcepts.htm
- Always Free resources: https://docs.oracle.com/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- OCI Regions/AD 공지(Chuncheon): https://docs.oracle.com/en-us/iaas/releasenotes/changes/4cb6164f-30d5-4c92-9946-481e177cdd72/
