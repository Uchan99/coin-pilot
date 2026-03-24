import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.agents.router import process_chat
from src.agents.tools._db import fetch_all, fetch_one
from src.agents.tools.portfolio_tool import run_portfolio_tool
from src.agents.tools.risk_diagnosis_tool import run_risk_diagnosis_tool
from src.agents.tools.trade_history_tool import run_trade_history_tool
from src.common.db import get_db_session, get_redis_client


logger = logging.getLogger(__name__)

mobile_router = APIRouter(prefix="/api/mobile", tags=["mobile"])


def _load_api_secret() -> str:
    return os.getenv("COINPILOT_API_SHARED_SECRET", "").strip()


def _load_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _require_mobile_api_secret(
    x_api_secret: str | None = Header(default=None, alias="X-Api-Secret"),
) -> None:
    """
    모바일 조회 API는 Discord 봇 어댑터 전용 내부 엔드포인트입니다.
    의도:
    - 외부 임의 호출 차단
    - 읽기 전용 운영 채널과 매매 루프를 분리
    실패 모드:
    - 시크릿 미설정: 배포 오구성으로 간주하고 503 반환
    - 시크릿 불일치: 401 반환
    """
    shared_secret = _load_api_secret()
    if not shared_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="COINPILOT_API_SHARED_SECRET is not configured.",
        )

    if not x_api_secret or x_api_secret.strip() != shared_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API secret.",
        )


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=600)
    session_id: str | None = Field(default=None, max_length=128)


@mobile_router.get("/positions")
async def get_positions(_: None = Depends(_require_mobile_api_secret)) -> dict[str, Any]:
    data = await asyncio.to_thread(run_portfolio_tool)
    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


def _fetch_cumulative_stats() -> dict[str, Any]:
    """
    전체 기간 누적 통계 — Overview/Control Center에서 사용
    Streamlit과 동일한 쿼리: SUM(total_pnl), COUNT(*) FROM trading_history
    """
    pnl_row = fetch_one("SELECT COALESCE(SUM(total_pnl), 0) AS cum_pnl FROM daily_risk_state")
    trade_row = fetch_one("SELECT COUNT(*) AS cnt FROM trading_history WHERE status = 'FILLED'")
    return {
        "cumulative_pnl_krw": float(pnl_row["cum_pnl"]) if pnl_row else 0.0,
        "cumulative_trade_count": int(trade_row["cnt"]) if trade_row else 0,
    }


@mobile_router.get("/pnl")
async def get_pnl(_: None = Depends(_require_mobile_api_secret)) -> dict[str, Any]:
    portfolio_data, trade_history, cumulative = await asyncio.gather(
        asyncio.to_thread(run_portfolio_tool),
        asyncio.to_thread(run_trade_history_tool),
        asyncio.to_thread(_fetch_cumulative_stats),
    )

    risk_snapshot = portfolio_data.get("risk_snapshot", {})
    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": {
            "daily_total_pnl_krw": float(risk_snapshot.get("total_pnl") or 0.0),
            "buy_count": int(risk_snapshot.get("buy_count") or 0),
            "sell_count": int(risk_snapshot.get("sell_count") or 0),
            "trade_count": int(risk_snapshot.get("trade_count") or 0),
            "consecutive_losses": int(risk_snapshot.get("consecutive_losses") or 0),
            "is_trading_halted": bool(risk_snapshot.get("is_trading_halted") or False),
            "filled_count_recent": int(trade_history.get("filled_count") or 0),
            "sell_count_recent": int(trade_history.get("sell_count") or 0),
            "last_sell": trade_history.get("last_sell"),
            # 전체 기간 누적 — Overview/Control Center용
            "cumulative_pnl_krw": cumulative["cumulative_pnl_krw"],
            "cumulative_trade_count": cumulative["cumulative_trade_count"],
        },
    }


@mobile_router.get("/risk")
async def get_risk(_: None = Depends(_require_mobile_api_secret)) -> dict[str, Any]:
    data = await asyncio.to_thread(run_risk_diagnosis_tool)
    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


async def _check_db_health() -> tuple[str, str | None]:
    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
        return "UP", None
    except Exception as exc:  # pragma: no cover - 운영환경 의존
        # 내부 예외 상세는 로그에만 남기고 API 응답에는 일반 메시지만 반환
        logger.warning("DB health check failed: %s", exc)
        return "DOWN", "Connection failed"


async def _check_redis_health() -> tuple[str, str | None]:
    try:
        client = await get_redis_client()
        await client.ping()
        await client.aclose()
        return "UP", None
    except Exception as exc:  # pragma: no cover - 운영환경 의존
        logger.warning("Redis health check failed: %s", exc)
        return "DOWN", "Connection failed"


async def _check_n8n_health() -> tuple[str, str | None]:
    n8n_url = os.getenv("N8N_URL", "http://n8n:5678").rstrip("/")
    candidates = ("/healthz", "/health", "/")
    timeout = httpx.Timeout(2.0)
    last_error: str | None = None

    async with httpx.AsyncClient(timeout=timeout) as client:
        for path in candidates:
            try:
                response = await client.get(f"{n8n_url}{path}")
                if response.status_code < 500:
                    return "UP", None
                last_error = f"status={response.status_code}"
            except Exception as exc:  # pragma: no cover - 운영환경 의존
                last_error = str(exc)

    logger.warning("n8n health check failed: %s", last_error)
    return "DOWN", "Service unavailable"


@mobile_router.get("/status")
async def get_system_status(_: None = Depends(_require_mobile_api_secret)) -> dict[str, Any]:
    db_health, redis_health, n8n_health = await asyncio.gather(
        _check_db_health(),
        _check_redis_health(),
        _check_n8n_health(),
    )
    risk_data = await asyncio.to_thread(run_risk_diagnosis_tool)

    components = {
        "bot": {"status": "UP", "detail": None},
        "db": {"status": db_health[0], "detail": db_health[1]},
        "redis": {"status": redis_health[0], "detail": redis_health[1]},
        "n8n": {"status": n8n_health[0], "detail": n8n_health[1]},
    }
    overall_status = "UP" if all(v["status"] == "UP" for v in components.values()) else "DEGRADED"

    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": {
            "overall_status": overall_status,
            "components": components,
            "risk_level": risk_data.get("risk_level", "UNKNOWN"),
            "risk_flags": risk_data.get("flags", []),
        },
    }


@mobile_router.post("/ask")
async def ask_mobile(payload: AskRequest, _: None = Depends(_require_mobile_api_secret)) -> dict[str, Any]:
    started = time.perf_counter()
    timeout_sec = _load_float_env("MOBILE_QUERY_TIMEOUT_SEC", 40.0)
    answer = await asyncio.wait_for(
        process_chat(payload.query.strip(), session_id=payload.session_id),
        timeout=timeout_sec,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latency_ms": latency_ms,
        "data": {"answer": answer},
    }


# ---------------------------------------------------------------------------
# Phase 3 엔드포인트 — Next.js 대시보드 실데이터 연동용
# Streamlit이 직접 SQL로 조회하던 데이터를 REST API로 제공
# ---------------------------------------------------------------------------


@mobile_router.get("/trades")
async def get_trades(
    _: None = Depends(_require_mobile_api_secret),
    symbol: str | None = Query(default=None, description="심볼 필터 (예: KRW-BTC)"),
    side: str | None = Query(default=None, description="사이드 필터 (BUY/SELL)"),
    limit: int = Query(default=50, ge=1, le=500, description="최대 조회 건수"),
    offset: int = Query(default=0, ge=0, description="오프셋 (페이징)"),
) -> dict[str, Any]:
    """
    거래 내역 조회 — History 탭용
    trading_history 테이블에서 FILLED 상태 거래를 페이징/필터링 지원으로 반환
    """
    def _query():
        # 동적 WHERE 절 구성 — 파라미터 바인딩으로 SQL injection 방지
        conditions = ["status = 'FILLED'"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if symbol:
            conditions.append("symbol = :symbol")
            params["symbol"] = symbol
        if side and side.upper() in ("BUY", "SELL"):
            conditions.append("side = :side")
            params["side"] = side.upper()

        where = " AND ".join(conditions)

        # 전체 건수 (페이징 메타 정보용)
        count_row = fetch_one(
            f"SELECT COUNT(*) AS cnt FROM trading_history WHERE {where}", params
        )
        total = int(count_row["cnt"]) if count_row else 0

        rows = fetch_all(
            f"""
            SELECT
                COALESCE(executed_at, created_at) + interval '9 hours' AS filled_at_kst,
                symbol, side, price, quantity, status,
                COALESCE(regime, 'UNKNOWN') AS regime,
                COALESCE(exit_reason, 'UNKNOWN') AS exit_reason,
                (signal_info->>'entry_avg_price')::numeric AS entry_avg_price
            FROM trading_history
            WHERE {where}
            ORDER BY COALESCE(executed_at, created_at) DESC
            LIMIT :limit OFFSET :offset
            """,
            params,
        )

        trades = []
        for r in rows:
            sell_price = float(r["price"]) if r.get("price") is not None else None
            qty = float(r["quantity"]) if r.get("quantity") is not None else None
            entry = float(r["entry_avg_price"]) if r.get("entry_avg_price") is not None else None
            pnl_krw = None
            pnl_pct = None
            if r.get("side") == "SELL" and sell_price and qty and entry and entry > 0:
                pnl_krw = (sell_price - entry) * qty
                pnl_pct = (sell_price - entry) / entry * 100.0

            trades.append({
                "filled_at_kst": str(r["filled_at_kst"]) if r.get("filled_at_kst") else None,
                "symbol": r.get("symbol"),
                "side": r.get("side"),
                "price": sell_price,
                "quantity": qty,
                "entry_avg_price": entry,
                "regime": r.get("regime"),
                "exit_reason": r.get("exit_reason"),
                "realized_pnl_krw": pnl_krw,
                "realized_pnl_pct": pnl_pct,
            })

        return {"trades": trades, "total": total, "limit": limit, "offset": offset}

    data = await asyncio.to_thread(_query)
    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


@mobile_router.get("/candles")
async def get_candles(
    _: None = Depends(_require_mobile_api_secret),
    symbol: str = Query(description="심볼 (예: KRW-BTC)"),
    interval: str = Query(default="15m", description="캔들 간격 (1m/5m/15m/1h/4h/1d)"),
    limit: int = Query(default=200, ge=10, le=500, description="캔들 수"),
) -> dict[str, Any]:
    """
    OHLCV 캔들 데이터 — Market 탭용
    TimescaleDB time_bucket 집계 (Streamlit 2_market.py와 동일 쿼리)
    """
    # 허용된 간격만 수용하여 SQL injection 방지
    interval_map = {"1m": "1 minute", "5m": "5 minutes", "15m": "15 minutes",
                    "1h": "1 hour", "4h": "4 hours", "1d": "1 day"}
    pg_interval = interval_map.get(interval)
    if not pg_interval:
        raise HTTPException(status_code=400, detail=f"Invalid interval: {interval}")

    def _query():
        rows = fetch_all(
            f"""
            SELECT
                time_bucket('{pg_interval}', timestamp) + interval '9 hours' AS bucket,
                FIRST(open_price, timestamp) AS open,
                MAX(high_price) AS high,
                MIN(low_price) AS low,
                LAST(close_price, timestamp) AS close,
                SUM(volume) AS volume
            FROM market_data
            WHERE symbol = :symbol
            GROUP BY bucket
            ORDER BY bucket DESC
            LIMIT :limit
            """,
            {"symbol": symbol, "limit": limit},
        )
        # 시간순 정렬 (과거 → 현재)
        candles = [
            {
                "time": str(r["bucket"]),
                "open": float(r["open"]) if r.get("open") is not None else 0,
                "high": float(r["high"]) if r.get("high") is not None else 0,
                "low": float(r["low"]) if r.get("low") is not None else 0,
                "close": float(r["close"]) if r.get("close") is not None else 0,
                "volume": float(r["volume"]) if r.get("volume") is not None else 0,
            }
            for r in reversed(rows)
        ]
        return candles

    candles = await asyncio.to_thread(_query)
    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": {"symbol": symbol, "interval": interval, "candles": candles},
    }


@mobile_router.get("/brain")
async def get_bot_brain(
    _: None = Depends(_require_mobile_api_secret),
    symbol: str = Query(default="KRW-BTC", description="심볼"),
) -> dict[str, Any]:
    """
    봇 브레인 상태 — Market 탭 Bot Brain 카드용
    Redis bot:status:{symbol} 키에서 레짐/RSI/HWM/추론 조회
    (Streamlit 2_market.py의 get_bot_status()와 동일)
    """
    async def _read_redis():
        try:
            client = await get_redis_client()
            # 원본 심볼로 시도
            data = await client.get(f"bot:status:{symbol}")
            if not data:
                # 심볼 형식 변환 시도 (KRW-BTC → BTC-KRW)
                if "-" in symbol:
                    parts = symbol.split("-")
                    reversed_sym = f"{parts[1]}-{parts[0]}"
                    data = await client.get(f"bot:status:{reversed_sym}")
            await client.aclose()
            return json.loads(data) if data else None
        except Exception as exc:
            logger.warning("Bot brain Redis read failed: %s", exc)
            return None

    bot_status = await _read_redis()
    if not bot_status:
        return {
            "ok": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data": {
                "available": False,
                "symbol": symbol,
                "regime": "UNKNOWN",
                "action": "UNKNOWN",
                "indicators": {},
                "reason": "봇 상태를 조회할 수 없습니다.",
                "timestamp": None,
            },
        }

    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": {
            "available": True,
            "symbol": symbol,
            "regime": bot_status.get("regime", "UNKNOWN"),
            "action": bot_status.get("action", "UNKNOWN"),
            "indicators": bot_status.get("indicators", {}),
            "reason": bot_status.get("reason", ""),
            "timestamp": bot_status.get("timestamp"),
        },
    }


@mobile_router.get("/ai-decisions")
async def get_ai_decisions(
    _: None = Depends(_require_mobile_api_secret),
    limit: int = Query(default=10, ge=1, le=100, description="최대 조회 건수"),
) -> dict[str, Any]:
    """
    AI 판단 로그 — System Health 탭용
    agent_decisions 테이블에서 최근 N건 조회 (Streamlit 5_system.py와 동일)
    """
    def _query():
        # 테이블 존재 여부 확인 (마이그레이션 미적용 환경 대비)
        exists = fetch_one(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_decisions') AS ok"
        )
        if not exists or not exists.get("ok"):
            return []

        rows = fetch_all(
            """
            SELECT
                created_at + interval '9 hours' AS created_at_kst,
                symbol, decision, reasoning, confidence, model_used,
                COALESCE(regime, 'UNKNOWN') AS regime
            FROM agent_decisions
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            {"limit": limit},
        )
        return [
            {
                "created_at_kst": str(r["created_at_kst"]) if r.get("created_at_kst") else None,
                "symbol": r.get("symbol"),
                "decision": r.get("decision"),
                "reasoning": r.get("reasoning"),
                "confidence": int(r["confidence"]) if r.get("confidence") is not None else None,
                "model_used": r.get("model_used"),
                "regime": r.get("regime"),
            }
            for r in rows
        ]

    decisions = await asyncio.to_thread(_query)
    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": {"decisions": decisions, "count": len(decisions)},
    }


@mobile_router.get("/exit-analysis")
async def get_exit_analysis(
    _: None = Depends(_require_mobile_api_secret),
    days: int = Query(default=30, ge=7, le=90, description="조회 기간 (일)"),
    limit: int = Query(default=800, ge=10, le=2000, description="최대 조회 건수"),
) -> dict[str, Any]:
    """
    매도 분석 데이터 — Exit Analysis 탭용
    Streamlit 07_exit_analysis.py와 동일 쿼리 + KPI/히트맵/포스트-exit 집계
    """
    def _query():
        since_ts = datetime.now(timezone.utc) - timedelta(days=days)
        rows = fetch_all(
            """
            SELECT
                COALESCE(executed_at, created_at) + interval '9 hours' AS sold_at,
                symbol,
                COALESCE(regime, 'UNKNOWN') AS regime,
                COALESCE(exit_reason, 'UNKNOWN') AS exit_reason,
                price, quantity,
                (signal_info->>'entry_avg_price')::numeric AS entry_avg_price,
                (post_exit_prices->'1h'->>'change_pct')::numeric AS post_1h_pct,
                (post_exit_prices->'4h'->>'change_pct')::numeric AS post_4h_pct,
                (post_exit_prices->'12h'->>'change_pct')::numeric AS post_12h_pct,
                (post_exit_prices->'24h'->>'change_pct')::numeric AS post_24h_pct
            FROM trading_history
            WHERE side = 'SELL'
              AND status = 'FILLED'
              AND COALESCE(executed_at, created_at) >= :since_ts
            ORDER BY COALESCE(executed_at, created_at) DESC
            LIMIT :limit
            """,
            {"since_ts": since_ts, "limit": limit},
        )

        sells = []
        pnl_values = []
        post_1h, post_4h, post_12h, post_24h = [], [], [], []
        # 히트맵용 집계: {(regime, exit_reason): [pnl_pct, ...]}
        heatmap_data: dict[tuple[str, str], list[float]] = {}

        for r in rows:
            price = float(r["price"]) if r.get("price") is not None else None
            qty = float(r["quantity"]) if r.get("quantity") is not None else None
            entry = float(r["entry_avg_price"]) if r.get("entry_avg_price") is not None else None
            pnl_pct = None
            if price and entry and entry > 0:
                pnl_pct = (price - entry) / entry * 100.0
                pnl_values.append(pnl_pct)
                key = (r.get("regime", "UNKNOWN"), r.get("exit_reason", "UNKNOWN"))
                heatmap_data.setdefault(key, []).append(pnl_pct)

            p1h = float(r["post_1h_pct"]) if r.get("post_1h_pct") is not None else None
            p4h = float(r["post_4h_pct"]) if r.get("post_4h_pct") is not None else None
            p12h = float(r["post_12h_pct"]) if r.get("post_12h_pct") is not None else None
            p24h = float(r["post_24h_pct"]) if r.get("post_24h_pct") is not None else None
            if p1h is not None: post_1h.append(p1h)
            if p4h is not None: post_4h.append(p4h)
            if p12h is not None: post_12h.append(p12h)
            if p24h is not None: post_24h.append(p24h)

            sells.append({
                "sold_at": str(r["sold_at"]) if r.get("sold_at") else None,
                "symbol": r.get("symbol"),
                "regime": r.get("regime"),
                "exit_reason": r.get("exit_reason"),
                "price": price,
                "quantity": qty,
                "entry_avg_price": entry,
                "pnl_pct": round(pnl_pct, 4) if pnl_pct is not None else None,
                "post_1h_pct": round(p1h, 4) if p1h is not None else None,
                "post_4h_pct": round(p4h, 4) if p4h is not None else None,
                "post_12h_pct": round(p12h, 4) if p12h is not None else None,
                "post_24h_pct": round(p24h, 4) if p24h is not None else None,
            })

        # KPI 집계
        total_sells = len(sells)
        pnl_computable = len(pnl_values)
        post_24h_samples = len(post_24h)
        avg_pnl = sum(pnl_values) / len(pnl_values) if pnl_values else None

        # Post-exit 윈도우별 평균
        def _avg(lst): return round(sum(lst) / len(lst), 4) if lst else None
        post_exit_avg = {
            "1h": {"avg_change_pct": _avg(post_1h), "samples": len(post_1h)},
            "4h": {"avg_change_pct": _avg(post_4h), "samples": len(post_4h)},
            "12h": {"avg_change_pct": _avg(post_12h), "samples": len(post_12h)},
            "24h": {"avg_change_pct": _avg(post_24h), "samples": len(post_24h)},
        }

        # 히트맵 집계: regime × exit_reason → 평균 PnL
        heatmap = [
            {"regime": k[0], "exit_reason": k[1], "avg_pnl_pct": round(sum(v) / len(v), 4)}
            for k, v in heatmap_data.items()
        ]

        return {
            "kpi": {
                "total_sells": total_sells,
                "pnl_computable": pnl_computable,
                "post_24h_samples": post_24h_samples,
                "avg_pnl_pct": round(avg_pnl, 4) if avg_pnl is not None else None,
            },
            "post_exit_avg": post_exit_avg,
            "heatmap": heatmap,
            "sells": sells,
            "filter": {"days": days, "limit": limit},
        }

    data = await asyncio.to_thread(_query)
    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
