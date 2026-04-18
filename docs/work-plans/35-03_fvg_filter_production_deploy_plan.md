# 35-03. FVG 필터 프로덕션 배포 작업 계획

**작성일**: 2026-04-13  
**작성자**: Claude  
**상태**: Approval Pending  
**관련 계획 문서**: `docs/work-plans/35_multi_evidence_technical_analysis_plan.md`  
**승인 정보**: -

---

## 0. 트리거(Why started)
- 백테스트 검증 결과, RSI/BB Mean-reversion 전략의 **모든 레짐에서 EV 음수** 확인
- FVG 필터가 유일하게 유의미한 개선 효과: 거래 79% 필터링, 누적PnL −85% → −11% (74%p 개선)
- 전략 근본 재설계 전 손실 속도를 줄이는 방어적 배포
- **한계 인식**: FVG 필터 적용 후에도 EV는 −0.31%/건으로 음수. 이 배포는 "전략 수정"이 아니라 "손실 완화" 목적

## 1. 문제 요약
- 증상: RSI/BB 진입이 FVG(수급 불균형) 없는 구간에서도 진입 → 낮은 품질의 거래 누적
- 영향 범위: 프로덕션 진입 로직 전체 (전 레짐, 전 심볼)
- 재현 조건: FVG 미존재 구간에서 RSI/BB 조건 충족 시 진입 발생

## 2. 원인 분석
- 가설: FVG 존재 = 기관/대형 참여자의 수급 불균형 → 반등 확률 상승
- 조사 과정: 5개 백테스트 라운드, 총 60+ 시나리오 검증
  - Phase 1-2 구조적 SL/TP → 승률 급락 (55→24%)
  - SMC 네이티브 진입 → 거래 부족 (27건), 18.5% 승률
  - 레짐 필터 → SIDEWAYS가 주손실원, BEAR 제외해도 EV 악화
  - BB 가드 변형 → 승률 하락이 avg_W 상승 상쇄
  - **FVG 필터 단독** → 유일한 양성 시그널 (승률 55→61%, PnL 74%p 개선)
- Root cause: RSI/BB 신호만으로는 수급 뒷받침 없는 진입이 79% 포함

## 3. 대응 전략

### 선택: Option B — bot_loop에서 별도 필터 단계 (AI 데이터 통합)

**대안 비교:**

| 옵션 | 설명 | 장점 | 단점 |
|---|---|---|---|
| A. strategy.py 내부 | evaluate_entry_conditions()에 FVG 체크 추가 | 코드 변경 최소 | indicators dict에 df 없음, 1시간봉 조회 필요 |
| **B. bot_loop 별도 단계** | Rule → **FVG 필터** → Risk → AI | 퍼널 추적, 데이터 재활용, 롤백 용이 | main.py 변경 |
| C. 전체 multi_evidence 통합 | score_multi_evidence() 사용 | 확장성 최고 | 과도한 변경, 성능 부담, 백테스트 미검증 |

**B안 선택 이유:**
- FVG 필터를 AI 컨텍스트 데이터 조회와 통합 → **DB 조회 1회로 FVG + AI 모두 커버**
- rule_funnel에 `fvg_filter_reject` 단계 추가 → FVG 통과/탈락 거래 성과 사후 분석 가능
- `fvg_filter_enabled` config 플래그 → 즉시 롤백 가능
- 기존 AI 단계의 `36*60` 조회를 `168*60`으로 확장 → 추가 쿼리 0회

## 4. 구현/수정 내용

### 변경 파일:
1. **`src/bot/main.py`** — FVG 필터 단계 추가, 데이터 조회 통합
2. **`config/strategy_v3.yaml`** — 레짐별 `fvg_filter_enabled` 플래그 추가

### 파이프라인 변경 (Before → After):

```
[Before]
Rule Engine → Risk Manager → AI PreFilter → AI Guardrail → AI Agent → Execute

[After]
Rule Engine → FVG Filter (NEW) → Risk Manager → AI PreFilter → AI Guardrail → AI Agent → Execute
               ↑ 데이터 조회 통합: 168*60봉 1회 조회
               ↑ hourly_df를 AI 컨텍스트에도 재사용
```

### 구현 상세:

#### Step 1. 데이터 조회 통합 + FVG 감지

Rule Engine 통과 직후, 기존 AI 컨텍스트용 데이터 조회를 앞당겨 실행:

```python
# Rule Engine 통과 직후 (기존 line 311 위치)
fvg_filter_enabled = regime_entry_config.get("fvg_filter_enabled", False)
if fvg_filter_enabled:
    # 168시간봉 = 7일 데이터 (FVG lookback=168 충족)
    # AI 컨텍스트(36시간봉)도 이 데이터의 subset으로 커버
    fvg_df_1m = await get_recent_candles(session, symbol, limit=168 * 60)
    fvg_hourly = resample_to_hourly(fvg_df_1m)

    # 데이터 부족 시 안전하게 통과 (fail-open)
    if len(fvg_hourly) < 50:
        print(f"[!] {symbol} FVG Filter: 데이터 부족 ({len(fvg_hourly)}봉), 필터 스킵")
    else:
        fvg_result = detect_fvg(fvg_hourly, lookback=168)
        has_fvg = fvg_result.get("price_in_fvg", False) or fvg_result.get("has_bullish_fvg_nearby", False)

        if not has_fvg:
            bot_action = "SKIP"
            bot_reason = f"[{regime}] FVG 필터 탈락: 근처 미해소 FVG 없음"
            record_rule_funnel_event(
                session, symbol=symbol, strategy_name=strategy.name,
                regime=regime, stage="fvg_filter_reject",
                result="reject", reason=bot_reason,
            )
            print(f"[-] {symbol} FVG Filter Rejected")
            continue
        else:
            record_rule_funnel_event(
                session, symbol=symbol, strategy_name=strategy.name,
                regime=regime, stage="fvg_filter_pass",
                result="pass", reason=f"FVG detected: {fvg_result.get('nearest_bullish_fvg', {}).get('gap_low', 'N/A')}",
            )
```

#### Step 2. AI 컨텍스트 데이터 재사용

기존 AI 단계에서 `get_recent_candles(limit=36*60)`를 별도 호출하던 것을 FVG 조회 데이터로 대체:

```python
# 기존: ai_df_1m = await get_recent_candles(session, symbol, limit=36 * 60)
# 변경: FVG 데이터 재사용 (168*60 > 36*60이므로 superset)
ai_source_df = fvg_df_1m if fvg_filter_enabled and len(fvg_df_1m) > 0 else await get_recent_candles(session, symbol, limit=36 * 60)
```

#### Step 3. Config 플래그

```yaml
regimes:
  BULL:
    entry:
      fvg_filter_enabled: true
  SIDEWAYS:
    entry:
      fvg_filter_enabled: true
  BEAR:
    entry:
      fvg_filter_enabled: true
```

### 에러 핸들링 정책:

| 상황 | 정책 | 이유 |
|---|---|---|
| DB 조회 실패 | **fail-open** (필터 스킵, 거래 허용) | DB 장애 시 거래 차단은 과도 |
| 데이터 부족 (<50봉) | **fail-open** (필터 스킵) | 신규 심볼/재시작 직후 보호 |
| detect_fvg 예외 | **fail-open** + 에러 로그 | FVG 필터는 보조 필터, 주 로직 차단 불가 |
| FVG 미감지 | **fail-closed** (거래 차단) | 정상 동작 — 수급 불균형 없으면 진입 안 함 |

### 성능 분석:

| 항목 | Before | After | 변화 |
|---|---|---|---|
| Rule 통과 시 DB 조회 | 1회 (36*60=2,160행) | 1회 (168*60=10,080행) | 조회량 4.7배 증가, 횟수 동일 |
| detect_fvg 연산 | 없음 | 168봉 루프 (~1ms) | 무시 가능 |
| AI 단계 DB 조회 | 1회 (2,160행) | **0회** (FVG 데이터 재사용) | 1회 절감 |
| **총 DB 조회** | **2회 / 4,320행** | **1회 / 10,080행** | 횟수 감소, 총량 2.3배 |

Rule 통과는 1시간에 수 건 미만 → 10,080행 조회의 절대적 부하는 미미.

## 4-1. OCI 사전 검증 (배포 전 필수)

배포 전 OCI에서 아래 확인:

```bash
# 1. DB에 7일치 1분봉 존재 확인
docker exec coinpilot-db psql -U coinpilot -d coinpilot -c "
  SELECT symbol, COUNT(*) as rows,
         MIN(timestamp) as oldest,
         MAX(timestamp) as newest,
         EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp)))/3600 as hours
  FROM market_data
  GROUP BY symbol ORDER BY symbol;"

# 2. 기대값: 각 심볼 rows >= 10,080 (7일), hours >= 168
# 3. 미달 시: FVG lookback을 축소 (예: 72시간) 또는 fail-open 유지
```

## 5. 검증 기준

### 배포 전 (OCI dry-run):
- [ ] DB 데이터 가용성 확인 (7일 1분봉 ≥ 10,080행/심볼)
- [ ] 구문 검사 통과
- [ ] 봇 시작 후 에러 없이 1시간 이상 구동 확인
- [ ] FVG 필터 로그 출력 확인: `docker logs coinpilot-bot 2>&1 | grep "FVG"`

### 배포 후 24h:
- [ ] rule_funnel 테이블에서 `fvg_filter_reject` 비율 확인 (~79% 예상)
- [ ] `fvg_filter_pass` → 이후 AI 단계 정상 진행 확인
- [ ] 에러 로그 없음 확인

### 배포 후 7일:
- [ ] 진입 건수 감소 추이 (기존 대비 ~80% 감소 예상)
- [ ] FVG 통과 거래의 승률/PnL 추적
- [ ] FVG 탈락 거래의 "가상 성과" 추적 (rule_funnel 데이터로 사후 분석)

### 롤백 기준:
- 24시간 동안 **모든** 거래가 FVG 탈락 (100% reject) → lookback 축소 또는 OFF
- detect_fvg 관련 예외가 3회 이상 발생 → OFF
- 예상 외 DB 부하 증가 (응답 지연 2초 초과) → OFF

## 6. 롤백

### 즉시 롤백 (1분):
```yaml
# config/strategy_v3.yaml에서 각 레짐의 fvg_filter_enabled를 false로 변경
fvg_filter_enabled: false
# 봇 재시작
docker restart coinpilot-bot
```

### 코드 롤백 (5분):
```bash
git revert <commit_hash>
# 재빌드 + 재배포
```

- 데이터/스키마 변경 없음 → 데이터 롤백 불필요
- rule_funnel 이벤트는 이력성 데이터이므로 삭제 불필요

## 7. 문서 반영
- [ ] 35-03 result 문서 작성 (배포 후 7일 데이터 포함)
- [ ] remaining_work_master_checklist 업데이트
- [ ] README.md 업데이트 여부: 배포 후 7일 성과에 따라 결정

## 8. 후속 조치

### 단기 (배포 후 1주):
- FVG 필터 적용 후 실전 승률/EV 측정
- FVG 통과 vs 탈락 거래의 성과 비교 (rule_funnel 데이터)
- 필터율이 90%+ 이면 lookback/proximity 파라미터 완화 검토

### 중기 (1~4주):
- avg_W/avg_L 비율 변화 추적
- FVG 필터 데이터를 활용한 전략 재설계 방향 도출
- 새 전략 Plan 수립 (별도 번호)

### 한계 명시:
- FVG 필터는 **수익 전략이 아님** — 손실 속도를 74% 줄이는 방어 장치
- 157일/36건 표본 기반 → 통계적 유의성 제한적 (향후 실전 데이터로 재검증 필수)
- 전략 근본 문제(avg_W < avg_L)는 미해결 → 후속 전략 재설계 필수
