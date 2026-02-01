# Week 8: 시스템 고도화 및 운영 안정성 확보 (Monitoring & Advanced Features)

## 1. Goal (목표)
Week 8의 핵심 목표는 시스템의 **관측 가능성(Observability)** 확보와 **고급 분석 기능(Volatility Model)** 의 통합입니다. Week 4에서 미완성된 모니터링 시스템을 완성하고, 룰 기반 코어에 변동성 기반 리스크 관리를 추가합니다.

### 1.1 세부 목표
1.  **Monitoring 고도화 (High Priority)**
    *   Prometheus를 통한 시스템 메트릭(CPU, Memory) 및 비즈니스 메트릭(매매 횟수, PnL, API Latency) 수집.
    *   Grafana 대시보드 구성을 통해 실시간 상태 시각화.
2.  **Notification 고도화 (Medium Priority)**
    *   n8n 워크플로우를 코드로 관리 (IaC 개념 도입/JSON Export).
    *   일간 리포트(Daily Report) 자동화.
3.  **Volatility Model 도입 (Medium Priority)**
    *   GARCH 모델을 통합하여 시장 변동성 예측.
    *   변동성이 기준치 초과 시 리스크 매니저가 포지션 크기를 동적으로 축소하도록 로직 연동.
4.  **Backtesting 고도화 (Medium Priority)**
    *   단순 수익률 외 MDD, Sharpe Ratio, Win Rate 등 전문적 지표 산출.
5.  **CI/CD 파이프라인 (Low Priority)**
    *   GitHub Actions를 활용한 기본 테스트 자동화 구축.

> [!NOTE]
> **Agent Memory** 기능은 Week 8의 우선순위 조정에 따라 본 계획에서 제외하고 이후 일정(Future)으로 이관합니다.

## 2. Design (설계)

### 2.1 System Architecture
*   **Observer Pattern**: 각 컴포넌트(Engine, Collector)는 Prometheus Client 라이브러리를 통해 메트릭을 노출(`/metrics`).
*   **Volatility Service**: 독립적인 모델 서비스 혹은 주기적 Job으로 실행되어 Redis에 `current_volatility` 상태를 업데이트.
    *   **Fallback Strategy**: Volatility Service 장애(Redis 조회 실패) 시, Risk Manager는 기본값(변동성 낮음, 100% 비중)으로 동작하여 매매 중단을 방지.

### 2.2 Directory Structure
```
coin-pilot/
├── .github/
│   └── workflows/
│       └── ci.yml                    # [NEW] CI Pipeline
├── deploy/
│   ├── monitoring/
│   │   ├── prometheus-config.yaml
│   │   ├── grafana-provisioning/
│   │   │   ├── datasources.yaml
│   │   │   └── dashboards/
│   │   │       ├── coinpilot-overview.json  # [NEW] 종합 대시보드 
│   │   │       └── coinpilot-trades.json    # [NEW] 매매 상세 대시보드
│   │   └── k8s-monitoring.yaml
├── src/
│   ├── core/
│   │   └── risk_manager.py
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── volatility_model.py
│   │   └── performance.py
│   └── utils/
│       └── metrics.py
├── tests/                            # [NEW] 테스트 추가
│   ├── analytics/
│   │   ├── test_volatility_model.py
│   │   └── test_performance.py       # [NEW] 성과 지표 계산 테스트
│   └── utils/
│       └── test_metrics.py
└── docs/
    └── work-plans/
        └── week8-advancement.md
```

### 2.3 Key Metrics (Prometheus)
*   `coinpilot_active_positions`: 현재 활성 포지션 수 (Gauge)
*   `coinpilot_total_pnl`: 누적 손익 (Gauge)
*   `coinpilot_trade_count_total`: 총 거래 횟수 (Counter)
*   `coinpilot_api_latency_seconds`: 거래소 API 응답 지연 (Histogram)
*   `coinpilot_volatility_index`: 현재 계산된 변동성 지수 (Gauge)

## 3. Process (구현 과정)

### Phase 1: Monitoring Infrastructure (Day 1-2)
1.  **Dependency Update**: `requirements.txt`에 `prometheus-client` 추가.
2.  **Metrics Exporter 구현**: `src/utils/metrics.py` 작성 및 단위 테스트 `tests/utils/test_metrics.py` 작성.
3.  **K8s Configuration**: Prometheus/Grafana ConfigMap 작성.
4.  **Dashboard Setup**: `coinpilot-overview.json` 등 템플릿 파일 생성 및 배포.

### Phase 2: Volatility & Analysis (Day 3-4)
1.  **Dependency Update**: `requirements.txt`에 `arch>=6.0` 추가.
2.  **Model Implementation**: `src/analytics/volatility_model.py` 구현.
    *   **Data Requirement**: 최근 90일치 1시간봉(1h candle) 데이터 사용.
    *   **Retraining**: 매일 00:00(UTC) 1회 재학습.
3.  **Performance Analytics**: `src/analytics/performance.py` 구현 (MDD, Sharpe Ratio 계산 로직) 및 단위 테스트 `tests/analytics/test_performance.py` 작성.
4.  **Integration & Fallback**: `RiskManager` 연동 및 Redis 조회 실패 시 예외 처리(Fallback to 100% position size).
5.  **Model Testing**: `tests/analytics/test_volatility_model.py` 작성.

### Phase 3: Notification & Automation (Day 5)
1.  **n8n Backup**: 워크플로우 JSON Export.
2.  **Reporting**: LangChain 기반 일간 리포트 생성기 구현.
3.  **Reporting Test**: 리포트 생성 모듈에 대한 단위 테스트 `tests/utils/test_reporting_agent.py` (혹은 유사) 작성 및 실행.
4.  **CI/CD**: `.github/workflows/ci.yml` 작성 (Push 시 `pytest` 자동 실행).

### Phase 4: Verification (Day 6)
1.  **Load Test**: `locust`를 사용하여 `/metrics` 엔드포인트 부하 테스트 (로컬 실행).
    *   **Success Criteria**: 50 VU(Virtual Users) 부하 시 응답 속도 < 100ms 유지.
2.  **Backtest**: 변동성 모델 적용 전후의 MDD 변화 비교.
3.  **Metrics Verification**: 매매 발생 시 `coinpilot_trade_count_total` 증가 확인.

---
**Verification Request**:
2차 피드백(test_performance.py 추가, 리포팅 테스트 추가)을 모두 반영하여 최종 수정한 계획서입니다. Claude Code에게 최종 승인(/review)을 요청하세요.

---

## Claude Code Review (Final)

**검토일**: 2026-02-02
**검토 대상**: Week 8 계획서 (최종본)

### ✅ 최종 피드백 반영 확인

| 항목 | 반영 상태 |
|------|-----------|
| `test_performance.py` 디렉토리 구조 추가 | ✅ |
| Phase 2에 Performance Analytics 테스트 명시 | ✅ |
| Phase 3에 Reporting 테스트 추가 | ✅ |
| `locust` 로컬 실행 명시 | ✅ |

### 📊 계획서 완성도 체크리스트

| 검증 항목 | 결과 |
|-----------|------|
| PROJECT_CHARTER Week 8 목표 부합 | ✅ |
| 모든 신규 모듈에 테스트 계획 포함 | ✅ |
| 의존성 패키지 명시 | ✅ |
| Fallback 전략 정의 | ✅ |
| Phase별 일정 배분 적절성 | ✅ |
| 검증 기준(Success Criteria) 명확성 | ✅ |

### 📋 최종 판정

| 항목 | 결과 |
|------|------|
| **승인 여부** | ✅ **최종 승인** |
| **보완 필요 사항** | 없음 |
| **구현 준비 상태** | Ready to Implement |

계획서가 완성되었습니다. Week 8 구현을 시작하세요.

---
*Final Review by Claude Code (Operator Role)*
