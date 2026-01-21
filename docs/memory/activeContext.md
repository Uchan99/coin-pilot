# Active Context

## Current Focus
- Week 2 준비 (Rule Engine & Risk Manager)

## Recent Accomplishments (Week 1 완료)
- **Week 1 목표 달성 완료**: PostgreSQL + TimescaleDB 구축 및 초기화 성공.
- **DB 스키마 검증**: `pgvector` 및 TimescaleDB 하이퍼테이블 설정 검증 완료.
- **연결 테스트 성공**: Upbit API를 통한 실시간 데이터 수집 및 DB 저장(Collector) 성공.
- **프로젝트 기반 구축**: `src/`, `docs/`, `deploy/`, `scripts/`, `tests/` 등 MSA 지향 구조의 폴더 세팅 완료.
- **문서화**: 트러블슈팅 기록 (week1-ts.md), 작업 결과 문서 (week1-walkthrough.md) 작성 완료.

## Week 2 목표 (Core Logic)
PROJECT_CHARTER 섹션 6 로드맵에 따른 Week 2 핵심 목표:

### Rule Engine (src/engine/)
- Mean Reversion + Trend Filter 전략 구현
- 진입 조건: RSI < 30, Price > MA(200), Volume > 20일 평균 1.5배, BB 하단 터치
- 청산 조건: Take Profit (+5%), Stop Loss (-3%), RSI > 70, Time Exit (48h)

### Risk Manager (src/engine/)
- 단일 포지션 한도: 총 자산의 5%
- 일일 최대 손실: -5% → 당일 거래 중단
- 일일 최대 거래: 10회
- 쿨다운: 3연패 시 2시간 거래 중단
- 최소 거래 간격: 30분

### 백테스팅 엔진
- 과거 데이터 기반 전략 검증 프레임워크 구축

## Next Step
- Week 2 작업 계획(work-plan) 수립 → `docs/work-plans/week2-rule-engine.md`
- Rule Engine 핵심 로직 설계 및 구현 시작
- Risk Manager 연동 설계
- 기술 지표 계산 유틸리티 구현 (RSI, MA, Bollinger Band)
