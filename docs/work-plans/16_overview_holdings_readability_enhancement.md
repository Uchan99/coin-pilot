# 16. Overview 보유자산 가독성 개선 계획

**작성일**: 2026-02-19  
**상태**: Draft  
**우선순위**: P1 (운영 가시성 개선)

---

## 1. 배경 및 문제 정의

현재 `Overview > Holdings` 테이블은 아래 컬럼 중심으로 표시된다.

- `symbol`
- `quantity`
- `avg_price`
- `current_price`
- `unrealized_pnl_pct`

운영 관점에서 다음 한계가 있다.

1. `quantity`가 소수점 자리수가 길어 가독성이 떨어짐.  
2. 실제로 얼마를 매수했고(`매수 원금`), 현재 얼마 가치인지(`평가 금액`)가 즉시 보이지 않음.  
3. `수익률(%)`은 보이지만 `수익금(KRW)`이 없어 체감이 어려움.

핵심 목표는 **보유자산 상태를 KRW 기준으로 직관적으로 파악**할 수 있도록 표시 구조를 개선하는 것이다.

---

## 2. 목표

1. Holdings 표를 KRW 중심 지표로 재구성한다.  
2. 소수점 수량 표시를 제어해 시각적 잡음을 줄인다.  
3. 수익률(%)과 수익금(KRW)을 동시에 제공한다.  
4. 기존 데이터 모델 변경 없이 Dashboard 쿼리/표시 레이어에서 완결한다.

---

## 2.5 기술 스택 선택 이유 및 대안 비교

### 선택 기술
- Streamlit `st.dataframe` 표시 레이어 개선
- pandas 계산/포맷팅 로직 확장
- DB 스키마 변경 없음

### 선택 이유
1. 문제의 본질이 UX/표시 포맷이므로 프론트 레이어 수정이 가장 저위험
2. 배포/롤백이 빠르고 운영 영향 범위가 작음
3. 기존 쿼리 결과를 활용해 구현 가능

### 대안 비교
1. DB에 계산 컬럼(매수금액/평가손익) 저장
- 장점: 조회 시 계산 부담 감소
- 단점: 중복 데이터/동기화 이슈 발생, 단순 UI 개선 대비 과한 변경

2. 별도 프론트엔드 프레임워크로 대시보드 전환
- 장점: UI 자유도/확장성 높음
- 단점: 현재 Streamlit 기반 운영 구조와 충돌, 도입 비용 큼

---

## 3. 구현 범위

### 3.1 Holdings 계산 컬럼 추가

`src/dashboard/pages/1_overview.py`에서 아래 계산 컬럼을 추가한다.

- `invested_krw` = `avg_price * quantity` (매수금액)
- `valuation_krw` = `current_price * quantity` (평가금액)
- `unrealized_pnl_krw` = `valuation_krw - invested_krw` (평가손익)
- `unrealized_pnl_pct` = `unrealized_pnl_krw / invested_krw * 100` (수익률)

예외 처리:
- `avg_price <= 0` 또는 `quantity <= 0`인 비정상 데이터는 0 또는 `N/A`로 안전 처리
- `current_price`가 `NULL`이면 해당 행은 수익 계산을 skip하고 `N/A` 표시
- `quantity`도 `pd.to_numeric(..., errors="coerce")`로 명시 변환 후 계산
- `current_price`는 `market_data` 최신가 JOIN 값을 기준으로 사용(포지션 테이블 직접 저장값에 의존하지 않음)

---

### 3.2 컬럼 구성/정렬 재정의

기존 컬럼을 아래 순서로 교체한다.

1. `Symbol`
2. `Qty`
3. `Invested (KRW)`
4. `Current Value (KRW)`
5. `PnL (KRW)`
6. `PnL (%)`

정렬 기준:
- 기본 정렬 `PnL (KRW)` 내림차순 또는 `Symbol` 오름차순 중 하나로 고정 (초기안: `Symbol` 오름차순)

---

### 3.3 표시 포맷 개선

- `Qty`: 과도한 소수점 억제 (기본 `{:,.6f}` 후 trailing zero 정리)
- KRW 금액 컬럼: 천 단위 구분기호 + 소수점 0자리
- `PnL (%)`: 소수점 2자리
- 양수/음수 부호(`+/-`) 명시
- 0 값은 부호 없이 `0` 또는 `0.00%`로 표시

예시:
- `Qty`: `0.001234`
- `Invested (KRW)`: `1,250,000`
- `PnL (KRW)`: `+35,420`
- `PnL (%)`: `+2.83%`

---

### 3.4 Streamlit 표시 안정성 보강

최근 발생했던 `st.dataframe(..., width="stretch")` 타입 오류 재발 방지를 위해:

- `st.dataframe` 호출에서 `width` 문자열 파라미터를 사용하지 않는다.
- `use_container_width=True` 유지
- 숫자/문자 포맷팅 단계를 분리해 타입 혼선을 방지한다.

### 3.5 불필요 레거시 쿼리 정리

현재 `1_overview.py`에 공존 중인 `query_positions`(미사용)와 관련 주석 블록을 제거하고, 실제 사용 중인 단일 쿼리(`query_positions_fixed` 또는 리네이밍된 최종 쿼리)만 유지한다.

---

## 4. 제외 범위 (Out of Scope)

1. 리스크 카운트 분리(14번) 및 사후분석(15번) 백엔드 변경
2. 매도 로직 변경
3. 신규 DB 컬럼 추가
4. Dashboard 다른 탭(Risk/History)의 UI 리디자인

---

## 5. 구현 파일

- `src/dashboard/pages/1_overview.py`
- `src/dashboard/utils/formatters.py` 신규 분리 (권장, Risk/History 재사용 대비)

문서 반영:
- `docs/work-result/16_overview_holdings_readability_result.md` (구현 결과)
- `docs/PROJECT_CHARTER.md`의 Dashboard 관련 상태 문구 갱신 (필요 시)

---

## 6. 검증 계획

### 6.1 기능 검증

1. 보유 포지션 1개 이상 상태에서 Holdings 표가 정상 렌더링되는지 확인
2. `Invested`, `Current Value`, `PnL(KRW)`, `PnL(%)` 계산값 수동 검산
3. `current_price` 누락 행에서 오류 없이 `N/A` 처리되는지 확인

### 6.2 회귀 검증

1. Overview 페이지 로드 시 예외 미발생 (`TypeError` 재발 여부)
2. 기존 상단 KPI (`Total Trades`, `Total PnL`, `Current Balance`) 정상 표시
3. 빈 포지션 상태 메시지(`No Active Positions`) 정상 표시

### 6.3 운영 검증

1. 대시보드 배포 후 30분 모니터링 중 UI 오류 로그 0건
2. 실제 보유 종목 기준으로 수익금/수익률 가독성 확인

---

## 7. 롤백 계획

1. UI 오류 발생 시 `src/dashboard/pages/1_overview.py`를 직전 커밋으로 롤백
2. `kubectl rollout undo deployment/dashboard -n coin-pilot-ns`
3. DB 스키마 변경이 없으므로 데이터 롤백 불필요

---

## 8. 산출물

1. Overview Holdings 컬럼 구조 개선 코드
2. 포맷팅/예외 처리 보강 코드
3. 구현 결과 문서 `docs/work-result/16_overview_holdings_readability_result.md`

---

## 9. 연계 관계

- 선행 권장: 14번 핫픽스(리스크 카운트 분리) 적용 여부와 무관하게 독립 진행 가능
- 병행 가능: 15번 사후분석 강화와 충돌 없음
- 후속 제안: Risk/History 탭도 동일 포맷 원칙(KRW 중심, 부호/단위 일관)으로 표준화 검토

---

## Claude Code Review

**검증일**: 2026-02-19
**검증 기준**: 현행 코드 대비 계획 정합성, 구현 가능성

### 코드 크로스 체크 결과

| # | 항목 | 판정 | 비고 |
|---|------|------|------|
| 1 | 레거시 `query_positions` 존재 확인 | ✅ 확인 | 1_overview.py:55에 미사용 쿼리 존재, L73의 `query_positions_fixed`가 실제 사용 (L87) |
| 2 | 현재 컬럼 구조 확인 | ✅ 확인 | `symbol`, `quantity`, `avg_price`, `current_price`, `unrealized_pnl_pct` — 계획서 분석과 일치 |
| 3 | `unrealized_pnl_pct` 계산 방식 | ✅ 확인 | L95: `(current_price - avg_price) / avg_price * 100` — 계획서 3.1의 계산식과 일치 |
| 4 | `st.dataframe` width 타입 오류 언급 | ✅ 확인 | 계획서 3.4에서 `width="stretch"` 문자열 파라미터 방지를 명시. `use_container_width=True` 사용 중 |
| 5 | DB 스키마 변경 없음 | ✅ 적절 | 표시 레이어만 수정. Position 테이블의 기존 컬럼(`quantity`, `avg_price`)과 `MarketData` 최신 가격으로 계산 가능 |

### Major Findings

없음. 순수 UI/표시 개선으로 범위가 명확하고 리스크가 낮음.

### Minor Findings

1. **`current_price` 소스 확인**: 현재 `query_positions_fixed`가 `Position` 테이블의 데이터만 조회하는지, JOIN으로 MarketData 최신가를 가져오는지 확인 필요. 현재 쿼리가 Position 테이블에 `current_price`를 직접 저장하고 있다면 계산이 단순하지만, 그렇지 않으면 추가 JOIN이나 Redis 조회가 필요할 수 있음.

2. **포맷팅 분리**: 계획서에서 `src/dashboard/utils/formatters.py` 분리를 "(선택)"으로 표기했으나, 향후 Risk/History 탭에도 동일 포맷을 적용할 계획이 있으므로 분리 권장.

3. **양수/음수 부호 표시**: pandas의 `map('{:+,.0f}'.format)` 사용 시 양수에 `+` 부호가 붙지만, 0일 경우 `+0`으로 표시됨. 0은 부호 없이 표시하는 것이 자연스러움.

### 종합 판정: **PASS** ✅

저위험 UI 개선. 기존 코드 분석이 정확하며 즉시 구현 가능.

### 리뷰 반영 결정 (2026-02-19)

1. `current_price` 소스 명확화: **반영 완료**
- `market_data` 최신가 JOIN 기준으로 명시 (`3.1`)

2. 포맷팅 모듈 분리 권장: **반영 완료**
- `formatters.py` 분리를 권장 사항으로 격상 (`5`)

3. 0값 부호 표시 개선: **반영 완료**
- 0은 무부호 표기 규칙 추가 (`3.3`)

### Round 2 최종 검증 (2026-02-19)

**판정: APPROVED** ✅ — 미해결 항목 없음. 구현 착수 가능.

- Minor 3건 반영 확인 완료
  - `market_data` 최신가 JOIN 기준 명시 (3.1:L76)
  - `formatters.py` 분리 권장으로 격상 (5:L138)
  - 0값 무부호 표기 규칙 (3.3:L102)
