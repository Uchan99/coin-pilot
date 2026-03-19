import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.agents.router import process_chat
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


@mobile_router.get("/pnl")
async def get_pnl(_: None = Depends(_require_mobile_api_secret)) -> dict[str, Any]:
    portfolio_data, trade_history = await asyncio.gather(
        asyncio.to_thread(run_portfolio_tool),
        asyncio.to_thread(run_trade_history_tool),
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
