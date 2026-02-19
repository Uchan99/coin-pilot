# 16. Overview Holdings 가독성 개선 구현 결과

**작성일**: 2026-02-19  
**작성자**: Codex (GPT-5)  
**관련 계획서**: `docs/work-plans/16_overview_holdings_readability_enhancement.md`

---

## 1. 구현 요약

Overview 페이지를 한국어 중심으로 정리하고, Holdings 테이블을 KRW 중심으로 재구성했다.

주요 개선:
1. `quantity` 표시 가독성 개선(소수점 6자리 + trailing zero 정리)
2. KRW 기반 핵심 컬럼 추가
   - `평단가 (KRW)`
   - `투자금 (KRW)`
   - `현재가치 (KRW)`
   - `손익 (KRW)`
   - `수익률 (%)`
3. `current_price` 누락/비정상 데이터 시 `N/A`로 안전 처리
4. 미사용 레거시 쿼리 제거 및 단일 쿼리로 정리
5. 상단 KPI에 `총 평가액` 추가
   - `총 평가액 = 현재 잔고 + 보유자산 현재가치 합`
6. KPI 숫자 잘림 개선
   - KPI 레이아웃을 2줄로 재구성
   - `금액 축약 표시 (만 원)` 토글 추가 (기본 ON)

---

## 2. 변경 파일

1. `src/dashboard/pages/1_overview.py`
- Holdings 계산/표시 로직 전면 정리
- 레거시 `query_positions`/주석 블록 제거
- `market_data` 최신가 JOIN 기준으로 계산
- KPI 확장 (`총 평가액`) 및 한글 라벨 적용
- KPI 레이아웃 2줄 분리 및 금액 축약 표시 토글 적용

2. `src/dashboard/utils/formatters.py` (신규)
- `format_qty()`
- `format_krw()`
- `format_krw_compact()`
- `format_pct()`

---

## 3. 계산 로직

추가 컬럼:
1. `avg_price` (평단가 표시)
2. `invested_krw = avg_price * quantity`
3. `valuation_krw = current_price * quantity`
4. `unrealized_pnl_krw = valuation_krw - invested_krw`
5. `unrealized_pnl_pct = unrealized_pnl_krw / invested_krw * 100`

상단 KPI 추가:
1. `holdings_current_value = SUM(quantity * current_price)`
2. `total_valuation = current_balance + holdings_current_value`

KPI 표시 포맷:
1. 기본: 축약 표시 ON (`884.7만 원` 형태)
2. 옵션: 축약 표시 OFF 시 전체 원 단위(`8,847,360`) 표시

예외 처리:
1. `quantity <= 0` 또는 `avg_price <= 0`이면 계산값 `N/A`
2. `current_price`가 `NULL/0`이면 평가 관련 값 `N/A`
3. `pd.to_numeric(..., errors='coerce')`로 타입 안전성 확보

---

## 4. 표시 변경

컬럼 순서:
1. `심볼`
2. `수량`
3. `평단가 (KRW)`
4. `투자금 (KRW)`
5. `현재가치 (KRW)`
6. `손익 (KRW)`
7. `수익률 (%)`

포맷 규칙:
1. 수량: `0.001234` 형식
2. KRW: 천 단위 구분, 소수점 없음
3. 손익/수익률: 양수 `+`, 음수 `-`, 0은 무부호
4. 화면 라벨: 한국어 중심(`총 체결`, `누적 손익`, `현재 잔고`, `총 평가액`)
5. KPI 레이아웃: 1행(총 체결/누적 손익/총 평가액), 2행(현재 잔고/승률)

---

## 5. 검증

실행:
```bash
python3 -m py_compile src/dashboard/pages/1_overview.py src/dashboard/utils/formatters.py
```

결과:
- 통과

---

## 6. 배포 후 확인 체크리스트

1. dashboard 재빌드/재배포
2. `Overview` 페이지 진입 시 오류 없음 확인
3. Holdings 표에서 평단가/투자금/현재가치/손익/수익률 계산값 수동 검산
4. `current_price`가 비어 있는 케이스에서 `N/A` 표시 확인
5. `총 평가액 = 현재 잔고 + 현재가치 합` 일치 확인
6. `금액 축약 표시 (만 원)` 토글 ON/OFF 시 KPI 값이 정상 전환되는지 확인

---

## 7. 결론

16번 계획 목표(가독성 개선, KRW 중심 표시, 예외 안전 처리)를 대시보드 표시 레이어에서 완료했다.
DB 스키마 변경 없이 즉시 배포/롤백 가능한 저위험 개선이다.
