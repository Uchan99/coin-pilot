from typing import Any, Dict, List

from src.agents.tools._db import fetch_all, fetch_one


def run_portfolio_tool() -> Dict[str, Any]:
    """
    현재 포트폴리오 상태(잔고/포지션/당일 리스크 상태)를 요약합니다.
    """
    balance_row = fetch_one(
        """
        SELECT balance, updated_at
        FROM account_state
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )
    risk_row = fetch_one(
        """
        SELECT date, total_pnl, buy_count, sell_count, trade_count, consecutive_losses, is_trading_halted
        FROM daily_risk_state
        ORDER BY date DESC
        LIMIT 1
        """
    )
    position_rows: List[Dict[str, Any]] = fetch_all(
        """
        SELECT
            p.symbol,
            p.quantity,
            p.avg_price,
            m.close_price AS current_price
        FROM positions p
        LEFT JOIN (
            SELECT DISTINCT ON (symbol) symbol, close_price
            FROM market_data
            ORDER BY symbol, timestamp DESC
        ) m ON p.symbol = m.symbol
        ORDER BY p.symbol
        """
    )

    cash_krw = float(balance_row["balance"]) if balance_row and balance_row.get("balance") is not None else 0.0

    holdings: List[Dict[str, Any]] = []
    holdings_value = 0.0

    for row in position_rows:
        qty = float(row.get("quantity") or 0.0)
        avg = float(row.get("avg_price") or 0.0)
        cur = float(row.get("current_price") or 0.0)

        invested = qty * avg
        valuation = qty * cur if cur > 0 else 0.0
        pnl_krw = valuation - invested
        pnl_pct = (pnl_krw / invested * 100.0) if invested > 0 else None

        holdings_value += valuation
        holdings.append(
            {
                "symbol": row.get("symbol"),
                "quantity": qty,
                "avg_price": avg,
                "current_price": cur if cur > 0 else None,
                "invested_krw": invested,
                "valuation_krw": valuation,
                "unrealized_pnl_krw": pnl_krw,
                "unrealized_pnl_pct": pnl_pct,
            }
        )

    total_valuation = cash_krw + holdings_value

    return {
        "cash_krw": cash_krw,
        "holdings_value_krw": holdings_value,
        "total_valuation_krw": total_valuation,
        "holdings": holdings,
        "risk_snapshot": {
            "date": str(risk_row.get("date")) if risk_row else None,
            "total_pnl": float(risk_row.get("total_pnl") or 0.0) if risk_row else 0.0,
            "buy_count": int(risk_row.get("buy_count") or 0) if risk_row else 0,
            "sell_count": int(risk_row.get("sell_count") or 0) if risk_row else 0,
            "trade_count": int(risk_row.get("trade_count") or 0) if risk_row else 0,
            "consecutive_losses": int(risk_row.get("consecutive_losses") or 0) if risk_row else 0,
            "is_trading_halted": bool(risk_row.get("is_trading_halted") or False) if risk_row else False,
        },
    }
