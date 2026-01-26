# CoinPilot Daily Startup Guide 🚀

**작성일**: 2026-01-26
**목적**: 컴퓨터 부팅 후 개발 환경을 빠르게 세팅하고 대시보드를 띄우기 위한 체크리스트

---

## 1. 🐳 Docker Desktop 실행 (필수)
가장 먼저 데이터베이스(PostgreSQL)와 캐시(Redis)를 켜야 합니다.

1.  **Docker Desktop** 애플리케이션 실행.
2.  좌측 **Containers** 메뉴 클릭.
3.  `coin-pilot` 그룹이 보이면 **Start (▶️)** 버튼 클릭.
    *   `postgres-db` (Running ✅)
    *   `redis-cache` (Running ✅)
    *   상태가 `Running`인지 확인.

> **Tip**: 만약 컨테이너가 없다면 터미널에서 `docker-compose -f deploy/docker-compose.yml up -d` 입력.

---

## 2. 💻 VS Code & Terminal 세팅
1.  **VS Code** 실행 및 `coin-pilot` 프로젝트 열기.
2.  **Terminal** 열기 (`Ctrl + ~`).
3.  **가상환경 활성화** (터미널 프롬프트 앞에 `(.venv)`가 떠야 함):
    ```bash
    source .venv/bin/activate
    ```
4.  **환경변수 확인**: `.env` 파일에 API Key가 잘 들어있는지 확인.
    *   `ANTHROPIC_API_KEY=sk-ant...` (따옴표 없이)
    *   `UPBIT_ACCESS_KEY=...`

---

## 3. 🔍 데이터베이스 상태 점검 (Optional)
오늘 처음 켰거나 DB가 비어있는지 찜찜하다면 확인해봅니다.

1.  **마이그레이션 (테이블 생성)**:
    ```bash
    PYTHONPATH=. .venv/bin/python scripts/migrate_week3.py
    ```
    *   `[OK]` 뜨면 정상.
2.  **데이터 확인**:
    ```bash
    PYTHONPATH=. .venv/bin/python scripts/check_db.py
    ```
    *   저장된 AI 결정 내역이 리스트로 출력되면 정상.

---

## 4. 📊 대시보드 실행 (Monitoring Mode)
실시간 시세를 수집하면서 AI의 판단을 모니터링하려면 **터미널 탭을 2개** 열어야 합니다.

### Tab 1: 데이터 수집기 (Data Collector)
Upbit에서 1분마다 시세를 긁어와 DB에 넣습니다. (이게 켜져 있어야 차트가 움직임)
```bash
# 터미널 1
PYTHONPATH=. .venv/bin/python src/collector/main.py
```

### Tab 2: 웹 대시보드 (Dashboard UI)
웹 브라우저로 차트와 AI 로그를 봅니다.
```bash
# 터미널 2
PYTHONPATH=. .venv/bin/streamlit run src/dashboard/app.py
```
*   브라우저가 자동으로 열리거나 [http://localhost:8501](http://localhost:8501) 접속.

---

## 5. 🧪 AI 매매 테스트 (Simulation)
대시보드를 켜둔 상태에서 AI가 잘 작동하는지 강제로 테스트해보고 싶다면:

1.  대시보드 왼쪽 사이드바의 **[Run Simulation]** 버튼 클릭.
2.  잠시 후(약 3~5초), **"Market Analysis"** 와 **"Resistance/Support"** 로그가 메인 화면에 갱신되는지 확인.
    *   초록색 `CONFIRM` 또는 빨간색 `REJECT` 박스가 뜨면 성공!

---

## ⚠️ 자주 발생하는 문제 (Troubleshooting)

**Q. 대시보드 차트가 텅 비었어요.**
> A. `src/collector/main.py`가 실행 중인지 확인하세요. 과거 데이터를 채우고 싶다면 `scripts/fetch_historical_data.py`를 한 번 실행하세요.

**Q. AI Decision에 아무것도 안 떠요.**
> A. 시뮬레이션 버튼을 눌렀는데도 안 뜬다면 `.env` 파일의 API Key를 다시 확인하고, `scripts/debug_simulation.py`를 터미널에서 직접 실행해서 에러 메시지를 확인하세요.

**Q. `401 Unauthorized` / `404 Not Found` 에러**
> A. API Key가 없거나, 모델명(`claude-3-haiku` vs `sonnet`)이 계정 권한과 맞지 않는 경우입니다. `src/agents/factory.py`에서 모델명을 확인하세요.
