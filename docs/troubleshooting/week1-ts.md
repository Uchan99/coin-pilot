# Week 1 Trouble Shooting

CoinPilot v3.0 개발 1주차 과정에서 발생한 기술적 문제와 해결 과정을 기록합니다. 포트폴리오의 "문제 해결 능력" 섹션으로 활용할 수 있습니다.

---

## 1. Docker Daemon 권한 문제 (Permission Denied)

### **문제 현상**
- `docker compose up -d` 또는 `docker ps` 실행 시 `permission denied while trying to connect to the Docker daemon socket` 에러 발생.

### **원인 파악**
- 사용자가 `docker` 그룹에 포함되어 있지 않아, `/var/run/docker.sock`에 접근할 수 있는 관리자 권한이 부족하여 발생.

### **해결 방법**
- **단기 해결**: 모든 도커 명령어 앞에 `sudo`를 붙여 관리자 권한으로 실행 (`sudo docker compose up -d`).
- **장기 해결**: 사용자를 `docker` 그룹에 추가하여 `sudo` 없이 명령어를 사용할 수 있도록 설정 (환경에 따라 재부팅 필요).

---

## 2. Requirements.txt 설치 실패 (Invalid Distribution)

### **문제 현상**
- `pip install -r requirements.txt` 실행 중 `ERROR: Could not find a version that satisfies the requirement EOF` 메시지와 함께 설치 중단.

### **원인 파악**
- `requirements.txt` 파일 생성 시 쉘 스크립트의 `EOF` 문자가 실수로 파일 마지막 줄에 포함됨. `pip`는 이를 패키지 이름으로 인식하여 설치를 시도함.

### **해결 방법**
- `requirements.txt` 파일을 열어 하단에 잘못 포함된 `EOF` 텍스트를 제거하고 저장 후 재설치 진행.

---

## 3. SQL 초기화 스크립트(init.sql) 구문 오류

### **문제 현상**
- TimescaleDB 하이퍼테이블 생성 및 압축 정책 설정 시 `PostgresSyntaxError: syntax error at or near ">"` 발생.

### **원인 파악**
- SQL 스크립트 내에서 함수 인자 전달 시 `if_not_exists => TRUE` 형식을 사용했으나, 특정 라이브러리 또는 파서에서 이를 잘못 해석하거나 줄바꿈 과정에서 공백이 삽입되어 구문 오류가 발생함.

### **해결 방법**
- SQL 문을 한 줄로 정렬하고 공백을 최소화하여 가독성과 실행 안정성을 확보. `if_not_exists => TRUE`와 같은 표현을 표준 SQL 형식에 맞춰 직관적으로 수정하여 해결.

---

## 4. SQLAlchemy ORM과 TimescaleDB 초기화 순서 상충

### **문제 현상**
- SQLAlchemy의 `Base.metadata.create_all()`을 사용할 경우, TimescaleDB 전용 기능(하이퍼테이블, 압축)이 적용되지 않은 일반 테이블로 생성됨.

### **원인 파악**
- ORM은 관계형 표준 모델만 지원하므로, TimescaleDB와 같은 특수한 확장은 DB 엔진 수준에서 직접 SQL 스크립트로 처리하는 것이 정석임.

### **해결 방법**
- `init.sql` 스크립트를 통해 DB 레벨에서 모든 기초 설계를 완료한 후, 파이썬 코드에서는 기존 테이블에 매핑만 하는 방식으로 설계 방향을 분리함. 이를 검증하기 위해 별도의 `verify_db.py` 스크립트를 작성하여 자동 검증 프로세스 구축.
