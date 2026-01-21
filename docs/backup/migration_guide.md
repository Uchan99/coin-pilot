# Migration Guide: VMware to WSL2

이 문서는 기존 VMware(Linux) 환경에서 개발하던 CoinPilot 프로젝트를 Windows Subsystem for Linux 2 (WSL2) 환경으로 이전하기 위한 가이드입니다.

---

## 1. 사전 준비 (Windows 환경)

### 1.1 WSL2 설치
PowerShell을 **관리자 권한**으로 실행하고 아래 명령어를 입력합니다.
```powershell
wsl --install
```
- 설치 완료 후 컴퓨터를 재부팅해야 할 수 있습니다.
- 재부팅 후 Ubuntu 초기 설정(Username, Password)을 완료하세요.

### 1.1.X 마이그레이션 필수 최적화 (사용자 스펙 맞춤)
사용자님의 하드웨어(i5-12400F, 32GB RAM, RTX 3060 Ti) 성능을 WSL2에서 100% 활용하기 위해, **반드시** 설정 파일을 생성해야 합니다. 이 설정이 없으면 WSL2가 메모리를 과도하게 점유하여 윈도우가 버벅거릴 수 있습니다.

1.  윈도우 탐색기 주소창에 `%UserProfile%` 을 입력하고 엔터를 칩니다.
2.  해당 폴더에 `.wslconfig` 라는 이름의 파일(확장자 없음)을 생성합니다. (메모장으로 열기)
3.  아래 내용을 복사해서 붙여넣고 저장하세요.

```ini
[wsl2]
# RAM: 16GB (32GB의 절반). 개발과 고사양 게임을 동시에 하기에 가장 이상적인 '황금 밸런스'입니다.
memory=16GB

# CPU: 8개 할당. 윈도우(게임)를 위해 4개 이상의 스레드를 남겨둡니다. 
processors=8

# Swap: RAM 부족 시 디스크를 사용하는 공간 (8GB로 충분)
swap=8GB

# localhost forwarding: WSL2 내부 서버를 윈도우에서 localhost로 접속 허용
localhostForwarding=true

[gui]
# WSL2 내부에서 띄운 GUI 앱이 흐릿하지 않게 설정
autoProxy=true
```
4.  저장 후 PowerShell(관리자)에서 `wsl --shutdown` 명령어로 WSL2를 완전히 껐다가 다시 켜야 적용됩니다.

### 1.2 Docker Desktop 설치
1.  [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)를 다운로드하여 설치합니다.
2.  설정(Settings) > **Resources** > **WSL Integration** 메뉴로 이동합니다.
3.  방금 설치한 Ubuntu 배포판을 체크하여 활성화합니다. (이 과정이 있어야 WSL2 내부에서 `docker` 명령어를 쓸 수 있습니다.)

---

## 2. 프로젝트 가져오기 (WSL2 터미널)

WSL2(Ubuntu) 터미널을 열고 작업을 시작합니다.

### 2.1 Git Clone
```bash
# 작업 디렉토리 생성
mkdir -p ~/workspace
cd ~/workspace

# Repository 복제 (GitHub 주소 확인 필요)
git clone https://github.com/Uchan99/coin-pilot.git
cd coin-pilot

# dev 브랜치 체크아웃 (최신 작업 내역)
git checkout dev
```

### 2.2 환경 변수 설정 (.env)
`.env` 파일은 보안상 Git에 포함되지 않았으므로 **새로 생성**해야 합니다.
`src/common/db.py`가 사용하는 변수들입니다.

```bash
# .env 파일 생성 및 편집
nano .env
```
**내용 예시:**
```ini
# DB Settings
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=coinpilot

# Upbit API (Collector용 - 필요 시)
UPBIT_ACCESS_KEY=your_access_key
UPBIT_SECRET_KEY=your_secret_key
```
> **주의**: 비밀번호나 키 값은 기존 환경과 동일하게 혹은 새로 설정한 값으로 맞춰주세요.

### 2.3 가상환경 구성 (선택 사항이지만 권장)
```bash
# venv 설치 및 생성
sudo apt update && sudo apt install -y python3.10-venv
python3 -m venv .venv

# 가상환경 활성화
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

---

## 3. 서비스 구동 및 검증

### 3.1 데이터베이스 실행
```bash
cd deploy
docker compose up -d
```
- Docker Desktop이 켜져 있어야 합니다. `sudo` 없이 실행 가능할 수도 있습니다 (권한 설정에 따라 다름).

### 3.2 검증 스크립트 실행
DB가 정상적으로 떴는지 확인합니다.
```bash
# 프로젝트 루트로 이동
cd ../

# PYTHONPATH 설정 후 검증 스크립트 실행
export PYTHONPATH=$PYTHONPATH:$(pwd)
python3 scripts/verify_db.py
```
- `[✓] market_data is a hypertable.` 메시지가 나오면 성공입니다.

### 3.3 데이터 수집 테스트
```bash
python3 src/collector/main.py
```
- `[+] Saved 1 candle(s).` 로그가 뜨면 마이그레이션 완료!

---

## 4. AI Agent (Antigravity) 복원

새로운 환경에서 IDE(Cursor, VS Code 등)를 켜고 AI Agent에게 아래와 같이 말하세요.
(`docs/backup/restore_prompt.md` 참조)

> "프로젝트 환경을 WSL2로 이사했어. docs/backup/migration_context.md 파일을 읽고 프로젝트 상태와 문맥을 복원해줘."

---
**수고하셨습니다! 이제 WSL2의 쾌적한 환경에서 Week 2 개발을 이어가세요.** 🚀
