from typing import Any, Dict, List

from src.agents.tools._db import fetch_all


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_sell_view(row: Dict[str, Any]) -> Dict[str, Any]:
    side = str(row.get("side") or "").upper()
    sell_price = _to_float(row.get("price"))
    qty = _to_float(row.get("quantity"))
    entry_avg_price = _to_float(row.get("entry_avg_price"))

    realized_pnl_krw = None
    realized_pnl_pct = None
    if side == "SELL" and sell_price is not None and qty is not None and entry_avg_price and entry_avg_price > 0:
        realized_pnl_krw = (sell_price - entry_avg_price) * qty
        realized_pnl_pct = (sell_price - entry_avg_price) / entry_avg_price * 100.0

    return {
        "filled_at_kst": row.get("filled_at_kst"),
        "symbol": row.get("symbol"),
        "side": side,
        "sell_price": sell_price,
        "quantity": qty,
        "entry_avg_price": entry_avg_price,
        "realized_pnl_krw": realized_pnl_krw,
        "realized_pnl_pct": realized_pnl_pct,
        "regime": row.get("regime") or "UNKNOWN",
        "exit_reason": row.get("exit_reason") or "UNKNOWN",
    }


def run_trade_history_tool(limit: int = 30) -> Dict[str, Any]:
    """
    최근 체결 이력을 조회하고 마지막 SELL 상세를 반환합니다.

    핵심 의도:
    - 사용자가 "마지막 SELL이 손해/이익이었는지"를 즉시 판단할 수 있도록,
      SELL 1건의 매수가/매도가/실현손익/수익률을 한 번에 제공합니다.
    """
    rows: List[Dict[str, Any]] = fetch_all(
        """
        SELECT
            COALESCE(executed_at, created_at) + interval '9 hours' AS filled_at_kst,
            symbol,
            side,
            price,
            quantity,
            status,
            COALESCE(regime, 'UNKNOWN') AS regime,
            COALESCE(exit_reason, 'UNKNOWN') AS exit_reason,
            (signal_info->>'entry_avg_price')::numeric AS entry_avg_price
        FROM trading_history
        WHERE status = 'FILLED'
        ORDER BY COALESCE(executed_at, created_at) DESC
        LIMIT :limit
        """,
        {"limit": limit},
    )

    if not rows:
        return {
            "status": "NO_DATA",
            "message": "체결 내역이 없어 마지막 SELL 정보를 확인할 수 없습니다.",
            "last_sell": None,
            "recent_sells": [],
            "filled_count": 0,
            "sell_count": 0,
        }

    filled_count = len(rows)
    sells = [_build_sell_view(r) for r in rows if str(r.get("side") or "").upper() == "SELL"]
    last_sell = sells[0] if sells else None

    return {
        "status": "OK",
        "filled_count": filled_count,
        "sell_count": len(sells),
        "last_sell": last_sell,
        "recent_sells": sells[:5],
    }
