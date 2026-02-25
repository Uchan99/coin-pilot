import asyncio
import time
import signal
import os
import sys
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
import pandas as pd
import numpy as np
from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_client import make_asgi_app
import uvicorn

from sqlalchemy import select, desc, update, func

# Add project root to path
sys.path.append(os.getcwd())

from src.common.db import get_db_session, get_redis_client
from src.common.models import MarketData, Position, TradingHistory
from src.common.indicators import get_all_indicators, resample_to_hourly
from src.engine.strategy import MeanReversionStrategy, evaluate_entry_conditions
from src.engine.executor import PaperTradingExecutor
from src.engine.risk_manager import RiskManager
from src.utils.metrics import metrics
from src.agents.context_features import (
    build_market_context,
    compute_bear_context_features,
    should_run_ai_analysis,
)
from src.agents.guardrails import should_block_ai_call, mark_ai_call_started
from src.common.json_utils import dumps_json

# Graceful Shutdown Handler
SHUTDOWN = False

def handle_sigterm(signum, frame):
    global SHUTDOWN
    print(f"[*] Signal {signum} received. Initiating graceful shutdown...")
    SHUTDOWN = True

# Register signals
signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

def build_status_reason(indicators: Dict, pos: Dict, config, risk_valid: bool = True, risk_reason: str = None) -> str:
    """
    봇의 판단 근거를 사람이 읽기 쉬운 문장으로 생성합니다.
    v3.0 마켓 레짐 기반 전략에 맞게 업데이트됨.
    """
    regime = indicators.get("regime", "UNKNOWN")
    
    if pos:
        close = float(indicators.get("close", 0.0))
        avg_price = float(pos["avg_price"])
        hwm = float(pos.get("high_water_mark") or pos["avg_price"])
        pnl_pct = ((close - avg_price) / avg_price * 100) if avg_price else 0.0
        hwm_delta_pct = ((close - hwm) / hwm * 100) if hwm else 0.0
        return f"[{regime}] 포지션 보유 중 (수익률: {pnl_pct:.2f}%, HWM 대비: {hwm_delta_pct:.2f}%)"

    if not risk_valid:
        return f"[{regime}] 진입 보류: {risk_reason}"

    if regime == "UNKNOWN":
        return "데이터 수집 중: 레짐 판단 대기 (약 8.3일치 데이터 필요)"

    regime_config = config.REGIMES.get(regime)
    if not regime_config:
        return f"[{regime}] 설정 로드 실패"
    entry_config = regime_config["entry"]
    eval_result = evaluate_entry_conditions(indicators, entry_config, regime)
    if not eval_result["valid"]:
        return f"[{regime}] {eval_result['reason']}"

    passed_str = "\n".join(eval_result["passed_checks"])
    return f"✅ [{regime}] 진입 조건 충족! AI 검증 대기 중...\n{passed_str}"


async def get_recent_candles(session, symbol: str, limit: int = 200) -> pd.DataFrame:
    """
    DB에서 최근 캔들 데이터를 조회하여 DataFrame으로 변환합니다.
    """
    start_time = time.time()
    try:
        # 1. DB 조회 (최신순 정렬)
        stmt = select(MarketData).where(
            MarketData.symbol == symbol
        ).order_by(desc(MarketData.timestamp)).limit(limit)
        
        result = await session.execute(stmt)
        rows = result.scalars().all()
        
        if not rows:
            return pd.DataFrame()
            
        # 2. 데이터 변환 및 정렬 (최신순 -> 과거순)
        data = [{
            "timestamp": r.timestamp.replace(tzinfo=timezone.utc) if r.timestamp.tzinfo is None else r.timestamp,
            "open": float(r.open_price),
            "high": float(r.high_price),
            "low": float(r.low_price),
            "close": float(r.close_price),
            "volume": float(r.volume)
        } for r in reversed(rows)]
        
        return pd.DataFrame(data)
    finally:
        # API Latency Metric Update
        latency = time.time() - start_time
        metrics.api_latency.observe(latency)


async def get_filled_trade_count_last_days(session, days: int = 2) -> int:
    """
    최근 N일 FILLED 체결 건수를 반환합니다.

    왜 필요한가:
    - Prometheus Counter는 프로세스 재시작 시 0에서 다시 시작합니다.
    - 운영 대시보드에서 "최근 2일" 같은 기간 집계를 안정적으로 보려면
      DB 기반 재계산 값(Gauge)이 필요합니다.
    """
    now_utc = datetime.now(timezone.utc)
    since_ts = now_utc - timedelta(days=max(1, int(days)))
    stmt = (
        select(func.count())
        .select_from(TradingHistory)
        .where(
            TradingHistory.status == "FILLED",
            func.coalesce(TradingHistory.executed_at, TradingHistory.created_at) >= since_ts,
        )
    )
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


from src.config.strategy import get_config

async def bot_loop():
    """
    CoinPilot Trading Bot Main Loop (Infinite Daemon) - 멀티 심볼 지원
    
    설정된 모든 코인 심볼에 대해 순차적으로 시장 데이터를 분석하고,
    전략 및 리스크 관리 규칙에 따라 매매를 수행함.
    """
    # 설정 로드 (롤백 모드 지원)
    config = get_config()
    
    # 컴포넌트 초기화 (설정 주입)
    strategy = MeanReversionStrategy(config)   # 매매 전략 (평균 회귀 v2.0)
    executor = PaperTradingExecutor()          # 주문 실행기 (모의 투자)
    risk_manager = RiskManager(config)         # 리스크 관리자 (포트폴리오 리스크 포함)
    
    print(f"[*] CoinPilot Trading Bot Started for {len(config.SYMBOLS)} symbols")
    print(f"[*] Strategy: {strategy.name}")
    print(f"[*] Target Symbols: {config.SYMBOLS}")
    
    while not SHUTDOWN:
        loop_start_time = time.time()
        
        try:
            async with get_db_session() as session:
                # -----------------------------------------------------------
                # Step 0. 전역 상태 및 메트릭 업데이트
                # -----------------------------------------------------------
                # 일일 리스크 상태(PnL 등) 조회 및 메트릭 반영
                risk_state = await risk_manager.get_daily_state(session)
                metrics.total_pnl.set(float(risk_state.total_pnl))
                
                # 전체 활성 포지션 수 조회 (메트릭용)
                open_positions_count = await risk_manager.count_open_positions(session)
                metrics.active_positions.set(open_positions_count)

                # 최근 2일 체결 건수(DB 기준) 메트릭 반영
                # Counter 기반 패널은 재시작 직후 0으로 보일 수 있어, 운영 관측용 Gauge를 병행합니다.
                filled_trade_count_2d = await get_filled_trade_count_last_days(session, days=2)
                metrics.trade_count_2d.set(float(filled_trade_count_2d))

                # Redis 클라이언트 초기화 (상태 전송용)
                try:
                    redis_client = await get_redis_client()
                except Exception as e:
                    print(f"[!] Redis Init Error: {e}")
                    redis_client = None

                # ========== 멀티 심볼 반복 처리 ==========
                for symbol in config.SYMBOLS:
                    try:
                        # -----------------------------------------------------------
                        # Step 1. Market Data Fetching
                        # -----------------------------------------------------------
                        df = await get_recent_candles(session, symbol)
                        
                        # 데이터 부족 시 스킵 (MA20 기간 + BB/RSI 여유분)
                        min_data_required = 20 + 20  # MA(20) + 여유분
                        if len(df) < min_data_required:
                            # 잦은 로그 방지를 위해 print는 생략하거나 조건부 출력
                            # print(f"[-] {symbol}: Not enough data ({len(df)} < {min_data_required}). Waiting...")
                            if redis_client:
                                try:
                                    status_data = {
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                        "symbol": symbol,
                                        "action": "WAITING",
                                        "reason": f"데이터 부족: {len(df)} lines",
                                        "indicators": {}
                                    }
                                    await redis_client.set(f"bot:status:{symbol}", dumps_json(status_data), ex=300)
                                except Exception:
                                    pass
                            continue

                        # 데이터 신선도 체크 (2분 이상 지연되면 경고)
                        last_ts = df.iloc[-1]["timestamp"]
                        now = datetime.now(timezone.utc)
                        if (now - last_ts) > timedelta(minutes=2):
                            # print(f"[!] {symbol}: Data stale. Last candle: {last_ts.isoformat()}")
                            continue

                        # -------------------------------------------------------
                        # Step 2. Market Analysis (지표 계산 & 레짐 조회)
                        # -------------------------------------------------------
                        # Redis에서 현재 레짐 조회 (없으면 UNKNOWN)
                        regime = "UNKNOWN"
                        if redis_client:
                            regime = await redis_client.get(f"market:regime:{symbol}") or "UNKNOWN"
                        
                        regime_entry_config = config.REGIMES.get(regime, {}).get("entry", {})
                        indicators = get_all_indicators(
                            df,
                            ma_period=regime_entry_config.get("ma_period", 20),
                            rsi_short_recovery_lookback=regime_entry_config.get("rsi_7_recovery_lookback", 5),
                            bb_touch_lookback=regime_entry_config.get("bb_touch_lookback", 30),
                            bb_recovery_sustain_candles=regime_entry_config.get("bb_recovery_sustain_candles", 1),
                        )
                        indicators["regime"] = regime
                        indicators["symbol"] = symbol  # 디버깅용
                        current_price = Decimal(str(indicators["close"]))
                        
                        # -------------------------------------------------------
                        # Step 3. Position & Signal Check
                        # -------------------------------------------------------
                        pos = await executor.get_position(session, symbol)
                        
                        # [Redis Status Update 준비]
                        bot_action = "HOLD"
                        bot_reason = ""
                        
                        if pos:
                            # [Case A] 포지션 보유 중 -> 청산(Exit) 체크
                            bot_action = "HOLD (POS)"
                            should_exit, exit_reason = strategy.check_exit_signal(indicators, pos)
                            
                            if should_exit:
                                bot_action = "SELL"
                                print(f"[{symbol}] Exit Triggered: {exit_reason}")
                                
                                # signal_info에 청산 사유 및 최종 HWM 추가
                                signal_info = {
                                    **indicators,
                                    "exit_reason": exit_reason,
                                    "regime": pos["regime"],
                                    "entry_avg_price": float(pos["avg_price"]),
                                }
                                
                                success = await executor.execute_order(
                                    session, symbol, "SELL", 
                                    current_price, pos["quantity"], 
                                    strategy.name, 
                                    signal_info
                                )
                                if success:
                                    # 리스크 상태 업데이트 (PnL 반영)
                                    pnl = (current_price - pos["avg_price"]) * pos["quantity"]
                                    await risk_manager.update_after_trade(session, pnl, side="SELL")
                                    # Redis의 HWM 삭제
                                    if redis_client:
                                        await redis_client.delete(f"position:{symbol}:hwm")
                                    print(f"[+] {symbol} Trade Closed. Reason: {exit_reason}, PnL: {pnl:,.0f} KRW")
                                    metrics.trade_count.inc()
                                    bot_reason = f"[{regime}] 포지션 청산 완료: {exit_reason}"
                                    pos = None
                                else:
                                    bot_reason = f"[{regime}] 매도 실행 실패: {exit_reason}"
                            else:
                                # 청산 안 됐을 때 HWM 업데이트 (Redis)
                                if redis_client and indicators.get("new_hwm"):
                                    await redis_client.set(f"position:{symbol}:hwm", str(indicators["new_hwm"]))
                                    # DB 업데이트 (주기적으로 하거나 청산 시 최종 기록)
                                    await session.execute(
                                        update(Position).where(Position.symbol == symbol).values(
                                            high_water_mark=indicators["new_hwm"],
                                            updated_at=datetime.now(timezone.utc)
                                        )
                                    )
                                bot_reason = build_status_reason(indicators, pos, config)

                        else:
                            # [Case B] 포지션 미보유 -> 진입(Entry) 체크
                            # DEBUG_ENTRY=1 환경변수로 진입 조건 디버깅 활성화
                            debug_entry = os.getenv("DEBUG_ENTRY", "0") == "1"
                            if strategy.check_entry_signal(indicators, debug=debug_entry):
                                print(f"[{symbol}] Entry Signal Detected!")
                                
                                balance = await executor.get_balance(session)
                                reference_equity = await risk_manager.get_reference_equity(session)

                                # 주문 금액 3중 캡(min) 정책:
                                # 1) target_cap: 기준자산 기반 목표 주문금액
                                # 2) cash_cap: 현재 가용 현금(수수료 버퍼 제외)
                                # 3) exposure_cap: 총 노출 한도 잔여분
                                # 위 세 값을 min으로 제한해, 비중 의도를 유지하면서 잔고 부족/과노출을 동시에 방지합니다.
                                regime_ratio = Decimal(str(
                                    config.REGIMES.get(regime, {}).get("position_size_ratio", 0.0)
                                ))
                                target_invest_amount = reference_equity * risk_manager.max_per_order * regime_ratio

                                cash_cap = balance * (Decimal("1") - risk_manager.fee_buffer)
                                current_exposure = await risk_manager.get_total_exposure(session)
                                max_total_exposure = reference_equity * Decimal(str(config.MAX_TOTAL_EXPOSURE))
                                exposure_cap = max_total_exposure - current_exposure

                                actual_invest_amount = min(target_invest_amount, cash_cap, exposure_cap)
                                if actual_invest_amount <= 0:
                                    bot_action = "SKIP"
                                    if exposure_cap <= 0:
                                        bot_reason = (
                                            f"Risk Rejected: 노출 한도 도달 "
                                            f"({current_exposure:,.0f}/{max_total_exposure:,.0f})"
                                        )
                                    elif cash_cap <= 0:
                                        bot_reason = f"Risk Rejected: 가용 현금 부족 ({cash_cap:,.0f})"
                                    else:
                                        bot_reason = "Risk Rejected: 주문 가능 금액이 0 이하"
                                    print(f"[-] {symbol} Order Skipped: {bot_reason}")
                                    continue

                                is_valid, risk_reason = await risk_manager.check_order_validity(
                                    session, symbol, actual_invest_amount
                                )

                                if is_valid:
                                    bot_action = "BUY"
                                    # 수량 계산 (투자금 / 현재가)
                                    quantity = actual_invest_amount / current_price
                                    if quantity > 0:
                                        # Rule 통과 시점에만 AI 전용 컨텍스트(1시간봉 24개 목표) 추가 조회
                                        ai_df_1m = await get_recent_candles(session, symbol, limit=36 * 60)
                                        ai_source_df = ai_df_1m if len(ai_df_1m) > 0 else df
                                        hourly_for_ai = resample_to_hourly(ai_source_df)
                                        market_context = build_market_context(hourly_for_ai, target_candles=24)
                                        context_len = len(market_context)
                                        metrics.ai_context_candles.observe(context_len)

                                        ai_indicators = {
                                            **indicators,
                                            "ai_context_candles": context_len
                                        }
                                        if regime == "BEAR":
                                            ai_indicators.update(compute_bear_context_features(hourly_for_ai, window=8))

                                        should_run_ai, prefilter_reason = should_run_ai_analysis(
                                            regime=regime,
                                            indicators=ai_indicators,
                                            market_context_len=context_len,
                                            entry_config=regime_entry_config,
                                        )
                                        if not should_run_ai:
                                            bot_action = "SKIP"
                                            bot_reason = f"AI PreFilter Rejected: {prefilter_reason}"
                                            metrics.ai_prefilter_skips.inc()
                                            print(f"[-] {symbol} AI PreFilter Rejected: {prefilter_reason}")
                                        else:
                                            ai_blocked, ai_block_reason = await should_block_ai_call(
                                                redis_client,
                                                symbol,
                                                regime_entry_config,
                                            )
                                            if ai_blocked:
                                                bot_action = "SKIP"
                                                bot_reason = f"AI Guardrail Blocked: {ai_block_reason}"
                                                metrics.ai_prefilter_skips.inc()
                                                print(f"[-] {symbol} AI Guardrail Blocked: {ai_block_reason}")
                                            else:
                                                await mark_ai_call_started(redis_client)
                                                signal_info = {
                                                    **ai_indicators,
                                                    "market_context": market_context,
                                                    "regime": regime,
                                                    "entry_config": regime_entry_config,
                                                }
                                                metrics.ai_requests.inc()
                                                success = await executor.execute_order(
                                                    session, symbol, "BUY", 
                                                    current_price, quantity, 
                                                    strategy.name, 
                                                    signal_info
                                                )
                                                if success:
                                                    await risk_manager.update_after_trade(
                                                        session,
                                                        Decimal("0"),
                                                        side="BUY",
                                                    )
                                                    metrics.trade_count.inc()
                                                else:
                                                    bot_action = "SKIP"
                                                    bot_reason = "AI Rejected or Execution Failed"
                                else:
                                    # 리스크 관리로 인한 거부
                                    bot_action = "SKIP"
                                    bot_reason = f"Risk Rejected: {risk_reason}"
                                    print(f"[-] {symbol} Order Skipped: {risk_reason}")
                            else:
                                # 시그널 없음
                                bot_reason = build_status_reason(indicators, None, config)

                        # [Redis Status Update 실행]
                        if redis_client:
                            status_data = {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "symbol": symbol,
                                "current_price": float(current_price),
                                "regime": regime,
                                "indicators": {
                                    "rsi": float(indicators.get("rsi", 0)),
                                    "ma_trend": float(indicators.get("ma_trend", 0)),
                                    "hwm": float(indicators.get("new_hwm", 0))
                                },
                                "position": {
                                    "has_position": bool(pos),
                                    "avg_price": float(pos["avg_price"]) if pos else None,
                                    "quantity": float(pos["quantity"]) if pos else None,
                                    "pnl_pct": (
                                        float(
                                            (
                                                (float(current_price) - float(pos["avg_price"]))
                                                / float(pos["avg_price"])
                                                * 100
                                            )
                                        )
                                        if pos and float(pos["avg_price"]) != 0
                                        else 0.0
                                    ),
                                    "regime": pos.get("regime") if pos else None
                                },
                                "action": bot_action,
                                "reason": bot_reason
                            }
                            try:
                                await redis_client.set(
                                    f"bot:status:{symbol}",
                                    dumps_json(status_data),
                                    ex=300
                                )
                            except Exception:
                                pass

                    except Exception as e_sym:
                        # 특정 심볼 처리 중 에러가 발생해도 다른 심볼은 계속 처리
                        print(f"[!] Error processing {symbol}: {e_sym}")
                        import traceback
                        traceback.print_exc()

        except Exception as e:
            print(f"[!] Critical Bot Loop Error: {e}")
            import traceback
            traceback.print_exc()
        
        if SHUTDOWN:
            break
            
        elapsed = time.time() - loop_start_time
        sleep_time = max(10, 60 - elapsed) # 최소 10초는 대기 보장
        await asyncio.sleep(sleep_time)

    print("[*] Bot Loop Terminated Gracefully.")

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.analytics.volatility_model import VolatilityModel
from src.analytics.post_exit_tracker import track_post_exit_prices_job
from src.analytics.exit_performance import ExitPerformanceAnalyzer
from src.agents.news.rss_news_pipeline import (
    news_ingest_rss_job,
    news_summarize_and_score_job,
)

# ... existing code ...

async def update_regime_job():
    """
    1시간마다 마켓 레짐 업데이트 (v3.0)
    """
    print("[Scheduler] Updating Market Regime...")
    config = get_config()
    try:
        async with get_db_session() as session:
            redis_client = await get_redis_client()
            for symbol in config.SYMBOLS:
                # 1. 1시간봉 계산을 위해 충분한 1분봉 데이터 조회
                df_1m = await get_recent_candles(session, symbol, limit=200 * 60) # 200시간어치
                if len(df_1m) < config.MIN_HOURLY_CANDLES_FOR_REGIME:
                    await redis_client.set(f"market:regime:{symbol}", "UNKNOWN", ex=7200)
                    continue
                
                # 2. 리샘플링 및 MA 계산
                from src.common.indicators import resample_to_hourly, calculate_ma, detect_regime
                df_1h = resample_to_hourly(df_1m)
                ma50 = calculate_ma(df_1h['close'], period=50).iloc[-1]
                ma200 = calculate_ma(df_1h['close'], period=200).iloc[-1]
                
                # 3. 레짐 판단
                regime = detect_regime(
                    ma50, ma200,
                    bull_threshold=config.BULL_THRESHOLD_PCT,
                    bear_threshold=config.BEAR_THRESHOLD_PCT
                )
                
                # 4. Redis 캐싱
                await redis_client.set(f"market:regime:{symbol}", regime, ex=7200)
                
                # 5. DB 기록 (레짐 변경 시 또는 주기적)
                from src.common.models import RegimeHistory
                diff_pct = float((ma50 - ma200) / ma200 * 100) if ma200 else 0
                history = RegimeHistory(
                    regime=regime,
                    ma50=Decimal(str(ma50)) if not np.isnan(ma50) else None,
                    ma200=Decimal(str(ma200)) if not np.isnan(ma200) else None,
                    diff_pct=Decimal(str(diff_pct)),
                    coin_symbol=symbol
                )
                session.add(history)
                print(f"[Scheduler] {symbol} Regime: {regime} (diff: {diff_pct:.2f}%)")
                
    except Exception as e:
        print(f"[Scheduler] Regime Update Failed: {e}")

async def retrain_volatility_job():
    """
    일일 변동성 모델 재학습 작업
    """
    print("[Scheduler] Starting Daily Volatility Model Retraining...")
    symbol = "KRW-BTC"
    try:
        async with get_db_session() as session:
            # 1. 데이터 조회 (최근 1000개 정도? GARCH 학습용)
            df = await get_recent_candles(session, symbol, limit=1000)
            if len(df) < 500:
                print(f"[Scheduler] Not enough data for training ({len(df)})")
                return

            # 2. 모델 학습
            model = VolatilityModel()

            # 고변동성 임계값 (환경변수 기반, 기본 2.0)
            try:
                volatility_threshold = float(os.getenv("VOLATILITY_HIGH_THRESHOLD", "2.0"))
            except Exception:
                volatility_threshold = 2.0

            # GARCH fitting
            vol = model.fit_predict(df['close'])
            is_high = vol > volatility_threshold

            # 3. 상태 업데이트
            model.update_volatility_state(vol, threshold=volatility_threshold)
            print(
                f"[Scheduler] Retraining Complete. High Volatility: {is_high} "
                f"(Vol: {vol:.4f}, Threshold: {volatility_threshold:.4f})"
            )
            
    except Exception as e:
        print(f"[Scheduler] Retraining Failed: {e}")

async def daily_reporter_job():
    """
    매일 22:00 KST (13:00 UTC)에 일간 리포트 생성 및 전송
    
    DailyReporter를 통해 오늘의 매매 결과를 조회하고,
    LLM으로 요약을 생성한 후 n8n 웹훅으로 Discord에 전송합니다.
    """
    print("[Scheduler] Generating Daily Report...")
    try:
        from src.agents.daily_reporter import DailyReporter
        reporter = DailyReporter(get_db_session)
        await reporter.generate_and_send()
        print("[Scheduler] Daily Report sent successfully.")
    except Exception as e:
        print(f"[Scheduler] Daily Report Failed: {e}")
        import traceback
        traceback.print_exc()


async def weekly_exit_report_job():
    """
    매주 일요일 22:00 KST (13:00 UTC)에 exit 성과 주간 리포트 생성/전송.
    """
    print("[Scheduler] Generating Weekly Exit Report...")
    try:
        from src.common.notification import notifier

        analyzer = ExitPerformanceAnalyzer(get_db_session)
        payload = await analyzer.build_weekly_report_payload(days=7, min_samples=20)
        ok = await notifier.send_webhook("/webhook/weekly-exit-report", payload)

        if ok:
            print("[Scheduler] Weekly Exit Report sent successfully.")
        else:
            print("[Scheduler] Weekly Exit Report send failed (webhook not accepted).")
    except Exception as e:
        print(f"[Scheduler] Weekly Exit Report Failed: {e}")
        import traceback
        traceback.print_exc()


async def news_ingest_job():
    """RSS 뉴스 수집 스케줄러 래퍼."""
    try:
        await news_ingest_rss_job()
    except Exception as e:
        print(f"[Scheduler] RSS ingest job failed: {e}")
        import traceback
        traceback.print_exc()


async def news_summary_job():
    """RSS 뉴스 요약/위험점수 집계 스케줄러 래퍼."""
    try:
        await news_summarize_and_score_job()
    except Exception as e:
        print(f"[Scheduler] RSS summarize job failed: {e}")
        import traceback
        traceback.print_exc()


# FastAPI App Setup for Health & Metrics
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Scheduler Setup
    scheduler = AsyncIOScheduler()
    # 매일 00:05 UTC에 실행
    scheduler.add_job(retrain_volatility_job, 'cron', hour=0, minute=5, timezone=timezone.utc,
                      misfire_grace_time=3600, coalesce=True)
    # 1시간마다 레짐 업데이트 (v3.0)
    # misfire_grace_time: 작업이 지연되어도 이 시간(초) 내면 실행 (기본 1초 -> 300초로 변경)
    # coalesce: 놓친 작업들을 하나로 합쳐서 실행
    scheduler.add_job(update_regime_job, 'interval', hours=1,
                      misfire_grace_time=300, coalesce=True)
    # 매일 22:00 KST (13:00 UTC)에 일간 리포트 전송
    scheduler.add_job(daily_reporter_job, 'cron', hour=13, minute=0, timezone=timezone.utc,
                      misfire_grace_time=7200, coalesce=True)
    # 10분마다 SELL post-exit 가격 추적
    scheduler.add_job(track_post_exit_prices_job, 'interval', minutes=10,
                      misfire_grace_time=300, coalesce=True)
    # 매주 일요일 22:00 KST (13:00 UTC)에 주간 Exit 성과 리포트 전송
    scheduler.add_job(
        weekly_exit_report_job,
        'cron',
        day_of_week='sun',
        hour=13,
        minute=0,
        timezone=timezone.utc,
        misfire_grace_time=7200,
        coalesce=True,
    )
    # RSS 뉴스 수집/요약 (RSS-Only: 외부 유료 API 미사용)
    scheduler.add_job(
        news_ingest_job,
        'interval',
        minutes=int(os.getenv("NEWS_RSS_INGEST_INTERVAL_MIN", "10")),
        misfire_grace_time=300,
        coalesce=True,
    )
    scheduler.add_job(
        news_summary_job,
        'interval',
        minutes=int(os.getenv("NEWS_RSS_SUMMARY_INTERVAL_MIN", "30")),
        misfire_grace_time=300,
        coalesce=True,
    )
    scheduler.start()
    
    # 서버 기동 직후 즉시 레짐 업데이트 1회 실행
    asyncio.create_task(update_regime_job())
    # 서버 기동 직후 변동성 모델도 1회 워밍업 실행합니다.
    # 왜 필요한가:
    # - 변동성 학습이 하루 1회(UTC 00:05)만 돌면, 재시작 직후 Grafana에서 0이 오래 유지될 수 있습니다.
    # - startup 즉시 1회 실행하면 Redis/Prometheus 상태를 빠르게 복구할 수 있습니다.
    # 실패 모드:
    # - 데이터가 충분하지 않으면 retrain 함수 내부에서 안전하게 종료하며 서비스는 계속 동작합니다.
    asyncio.create_task(retrain_volatility_job())
    # 서버 기동 직후 뉴스 파이프라인도 1회 실행
    asyncio.create_task(news_ingest_job())
    asyncio.create_task(news_summary_job())
    
    print("[*] Scheduler started (Regime job added).")
    
    # Startup Bot Loop
    task = asyncio.create_task(bot_loop())
    yield
    # Shutdown
    global SHUTDOWN
    SHUTDOWN = True
    scheduler.shutdown()
    await task

app = FastAPI(lifespan=lifespan)
# ...

# Add Prometheus Metrics Endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

if __name__ == "__main__":
    # 봇 서비스 포트는 8000 (monitoring config와 일치)
    uvicorn.run(app, host="0.0.0.0", port=8000)
