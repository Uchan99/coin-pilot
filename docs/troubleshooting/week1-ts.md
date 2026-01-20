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

---

## Claude Code Review (트러블슈팅 문서 검토)

**검토일:** 2026-01-20
**검토자:** Claude Code (Operator & Reviewer)
**상태:** ✅ **문서화 품질 우수**

---

### 1. 문서화 품질 평가

| 항목 | 평가 | 비고 |
| :--- | :--- | :--- |
| 문제-원인-해결 구조 | ✅ 우수 | 일관된 3단계 포맷 |
| 원인 분석 깊이 | ✅ 적절 | 근본 원인까지 파악 |
| 재현 가능성 | ✅ 양호 | 에러 메시지 명시 |
| 포트폴리오 활용도 | ✅ 높음 | 실무 문제 해결 역량 증명 |

---

### 2. 각 이슈별 코멘트

#### Issue #1: Docker Daemon 권한 문제
- **평가:** 일반적인 Linux 환경 셋업 이슈로, 해결 방법이 적절함
- **추가 팁:** `newgrp docker` 명령으로 재로그인 없이 그룹 적용 가능

#### Issue #2: Requirements.txt EOF 문제
- **평가:** heredoc 사용 시 흔히 발생하는 실수로, 원인 파악이 정확함
- **예방책:** `cat requirements.txt | tail -5`로 파일 끝 검증 습관화

#### Issue #3: SQL 구문 오류
- **평가:** PostgreSQL named parameter 문법(`=>`)이 포매터에 의해 깨진 케이스
- **보충:** `=>` 대신 `:=` 문법도 PostgreSQL에서 지원됨 (호환성 향상)

#### Issue #4: ORM vs TimescaleDB 초기화 순서
- **평가:** 아키텍처 레벨의 중요한 의사결정으로, 문서화 가치가 높음
- **설계 원칙:** "DB 확장 기능은 SQL로, 애플리케이션 로직은 ORM으로" 분리 원칙이 잘 적용됨

---

### 3. 추가 권장 문서화 항목

향후 발생할 수 있는 이슈에 대비하여 다음 항목도 기록 권장:

| 잠재적 이슈 | 예상 원인 | 예방책 |
| :--- | :--- | :--- |
| pgvector 확장 미설치 | timescaledb 이미지에 미포함 | timescaledb-ha 이미지 또는 Dockerfile 커스텀 |
| 중복 데이터 삽입 | Collector 재시작 시 | `ON CONFLICT DO NOTHING` 추가 |
| 타임존 불일치 | UTC vs KST 혼용 | 모든 timestamp를 UTC 기준으로 통일 |

---

### 4. 결론

Week 1 트러블슈팅 문서가 **포트폴리오 품질 수준**으로 잘 작성되었습니다.

- 문제 해결 과정이 논리적으로 구조화됨
- 실제 개발 환경에서 발생하는 실무적 이슈들을 다룸
- ORM-TimescaleDB 분리 설계는 **아키텍처 의사결정 문서**로도 활용 가능 -> 포트폴리오에서 설게 역량을 보여주는 좋은 사례

**Week 2 작업 시에도 동일한 형식으로 트러블슈팅 기록을 유지하시기 바랍니다.**
