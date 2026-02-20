from typing import Any, Dict, List

from src.agents.tools._db import fetch_all, fetch_one


def run_risk_diagnosis_tool() -> Dict[str, Any]:
    """
    당일 리스크 상태/감사 로그/포지션 집중도를 결합해 위험 수준을 진단합니다.
    """
    risk_row = fetch_one(
        """
        SELECT date, total_pnl, buy_count, sell_count, trade_count, consecutive_losses, is_trading_halted
        FROM daily_risk_state
        ORDER BY date DESC
        LIMIT 1
        """
    )
    balance_row = fetch_one(
        """
        SELECT balance
        FROM account_state
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )
    position_rows = fetch_all(
        """
        SELECT
            p.symbol,
            p.quantity,
            m.close_price
        FROM positions p
        LEFT JOIN (
            SELECT DISTINCT ON (symbol) symbol, close_price
            FROM market_data
            ORDER BY symbol, timestamp DESC
        ) m ON p.symbol = m.symbol
        ORDER BY p.symbol
        """
    )
    audit_rows = fetch_all(
        """
        SELECT violation_type, description, timestamp
        FROM risk_audit
        WHERE timestamp >= NOW() - interval '24 hours'
        ORDER BY timestamp DESC
        LIMIT 20
        """
    )

    total_balance = float(balance_row["balance"]) if balance_row and balance_row.get("balance") is not None else 0.0

    position_values: List[Dict[str, Any]] = []
    for row in position_rows:
        qty = float(row.get("quantity") or 0.0)
        px = float(row.get("close_price") or 0.0)
        value = qty * px
        position_values.append(
            {
                "symbol": row.get("symbol"),
                "value_krw": value,
            }
        )

    total_position_value = sum(item["value_krw"] for item in position_values)
    denominator = total_balance + total_position_value

    concentration = 0.0
    if denominator > 0 and position_values:
        concentration = max(item["value_krw"] / denominator for item in position_values)

    flags: List[str] = []
    risk_level = "SAFE"

    if risk_row and bool(risk_row.get("is_trading_halted")):
        risk_level = "HIGH_RISK"
        flags.append("현재 거래 중단 상태입니다.")

    consecutive_losses = int(risk_row.get("consecutive_losses") or 0) if risk_row else 0
    if consecutive_losses >= 3:
        risk_level = "HIGH_RISK"
        flags.append(f"연속 손실 {consecutive_losses}회로 쿨다운 필요 구간입니다.")

    buy_count = int(risk_row.get("buy_count") or 0) if risk_row else 0
    if buy_count >= 8 and risk_level != "HIGH_RISK":
        risk_level = "WARNING"
        flags.append(f"당일 BUY 횟수 {buy_count}회로 한도(10회)에 근접했습니다.")

    if concentration >= 0.30 and risk_level == "SAFE":
        risk_level = "WARNING"
        flags.append(f"단일 포지션 집중도 {concentration * 100:.1f}%로 분산이 부족합니다.")

    if len(audit_rows) >= 5 and risk_level == "SAFE":
        risk_level = "WARNING"
        flags.append(f"최근 24시간 리스크 이벤트가 {len(audit_rows)}건으로 증가했습니다.")

    if not flags:
        flags.append("핵심 리스크 지표는 현재 정상 범위입니다.")

    return {
        "risk_level": risk_level,
        "flags": flags,
        "snapshot": {
            "date": str(risk_row.get("date")) if risk_row else None,
            "total_pnl": float(risk_row.get("total_pnl") or 0.0) if risk_row else 0.0,
            "buy_count": buy_count,
            "sell_count": int(risk_row.get("sell_count") or 0) if risk_row else 0,
            "trade_count": int(risk_row.get("trade_count") or 0) if risk_row else 0,
            "consecutive_losses": consecutive_losses,
            "is_trading_halted": bool(risk_row.get("is_trading_halted") or False) if risk_row else False,
            "position_concentration": concentration,
            "audit_events_24h": len(audit_rows),
        },
        "recent_audits": audit_rows[:5],
    }
