from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Tuple

import pandas as pd

from src.agents.tools._db import fetch_all


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return pd.to_datetime(value).to_pydatetime()
    except Exception:
        return None


def run_strategy_review_tool(days: int = 14, limit: int = 600) -> Dict[str, Any]:
    """
    최근 거래 내역을 기반으로 전략 성과를 진단합니다.

    핵심 불변조건:
    1) 실현손익은 SELL 체결 시점에만 계산합니다.
    2) BUY lot은 심볼별 FIFO(선입선출)로 매칭합니다.
    3) 매칭 불가능한 SELL(legacy 데이터 등)은 통계에서 제외하고 notes로 남깁니다.
    """
    rows = fetch_all(
        """
        SELECT
            id,
            COALESCE(executed_at, created_at) AS ts,
            symbol,
            side,
            price,
            quantity,
            regime,
            exit_reason,
            status
        FROM trading_history
        WHERE status = 'FILLED'
          AND COALESCE(executed_at, created_at) >= NOW() - (:days || ' days')::interval
        ORDER BY COALESCE(executed_at, created_at) ASC
        LIMIT :limit
        """,
        {"days": days, "limit": limit},
    )

    if not rows:
        return {
            "status": "NO_DATA",
            "message": f"최근 {days}일 데이터가 없어 전략 리뷰를 생성할 수 없습니다.",
            "summary": {},
        }

    buy_lots: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    sell_results: List[Dict[str, Any]] = []
    notes: List[str] = []

    # 한국어 유지보수 주석:
    # - SELL 한 건이 여러 BUY lot에 걸쳐 체결될 수 있으므로, lot 단위로 부분 매칭합니다.
    # - 이렇게 해야 평균단가 왜곡 없이 실현손익과 보유시간(hold_hours)을 계산할 수 있습니다.
    for row in rows:
        symbol = row.get("symbol")
        side = str(row.get("side") or "").upper()
        qty = float(row.get("quantity") or 0.0)
        price = float(row.get("price") or 0.0)
        ts = _to_datetime(row.get("ts"))

        if not symbol or qty <= 0 or price <= 0:
            continue

        if side == "BUY":
            buy_lots[symbol].append(
                {
                    "remaining_qty": qty,
                    "entry_price": price,
                    "opened_at": ts,
                    "regime": row.get("regime") or "UNKNOWN",
                }
            )
            continue

        if side != "SELL":
            continue

        remaining_sell = qty
        matched_qty = 0.0
        sell_pnl_krw = 0.0
        weighted_pnl_pct_numerator = 0.0
        weighted_hold_hours = 0.0

        lots = buy_lots[symbol]

        while remaining_sell > 1e-12 and lots:
            lot = lots[0]
            take_qty = min(remaining_sell, lot["remaining_qty"])

            entry_price = float(lot["entry_price"])
            pnl_krw = (price - entry_price) * take_qty
            pnl_pct = ((price - entry_price) / entry_price * 100.0) if entry_price > 0 else 0.0

            hold_hours = None
            if ts and lot.get("opened_at"):
                hold_delta = ts - lot["opened_at"]
                hold_hours = max(0.0, hold_delta.total_seconds() / 3600.0)

            sell_pnl_krw += pnl_krw
            weighted_pnl_pct_numerator += pnl_pct * take_qty
            if hold_hours is not None:
                weighted_hold_hours += hold_hours * take_qty

            matched_qty += take_qty
            remaining_sell -= take_qty
            lot["remaining_qty"] -= take_qty

            if lot["remaining_qty"] <= 1e-12:
                lots.pop(0)

        if matched_qty <= 0:
            notes.append(f"{symbol} SELL 매칭 실패: 선행 BUY lot 부족")
            continue

        avg_pnl_pct = weighted_pnl_pct_numerator / matched_qty
        avg_hold_hours = weighted_hold_hours / matched_qty if weighted_hold_hours > 0 else None

        sell_results.append(
            {
                "symbol": symbol,
                "sell_qty": matched_qty,
                "pnl_krw": sell_pnl_krw,
                "pnl_pct": avg_pnl_pct,
                "hold_hours": avg_hold_hours,
                "regime": row.get("regime") or "UNKNOWN",
                "exit_reason": row.get("exit_reason") or "UNKNOWN",
            }
        )

    if not sell_results:
        return {
            "status": "NO_REALIZED",
            "message": "SELL 실현손익을 계산할 수 있는 데이터가 없습니다.",
            "summary": {},
            "notes": notes,
        }

    total_pnl = sum(item["pnl_krw"] for item in sell_results)
    win_count = sum(1 for item in sell_results if item["pnl_krw"] > 0)
    loss_count = sum(1 for item in sell_results if item["pnl_krw"] < 0)
    total_count = len(sell_results)
    win_rate = win_count / total_count if total_count else 0.0

    by_regime: Dict[str, Dict[str, Any]] = {}
    for regime in sorted(set(item["regime"] for item in sell_results)):
        bucket = [item for item in sell_results if item["regime"] == regime]
        by_regime[regime] = {
            "count": len(bucket),
            "avg_pnl_pct": sum(x["pnl_pct"] for x in bucket) / len(bucket),
            "avg_hold_hours": sum((x["hold_hours"] or 0.0) for x in bucket) / len(bucket),
        }

    by_exit_reason: Dict[str, Dict[str, Any]] = {}
    for reason in sorted(set(item["exit_reason"] for item in sell_results)):
        bucket = [item for item in sell_results if item["exit_reason"] == reason]
        by_exit_reason[reason] = {
            "count": len(bucket),
            "avg_pnl_pct": sum(x["pnl_pct"] for x in bucket) / len(bucket),
        }

    # 연속 손실 길이 계산
    max_loss_streak = 0
    curr_streak = 0
    for item in sell_results:
        if item["pnl_krw"] < 0:
            curr_streak += 1
            max_loss_streak = max(max_loss_streak, curr_streak)
        else:
            curr_streak = 0

    strengths: List[str] = []
    weaknesses: List[str] = []
    improvements: List[str] = []

    if win_rate >= 0.55:
        strengths.append(f"최근 승률이 {win_rate * 100:.1f}%로 안정 구간입니다.")
    else:
        weaknesses.append(f"최근 승률이 {win_rate * 100:.1f}%로 낮아 진입 필터 재점검이 필요합니다.")

    if total_pnl > 0:
        strengths.append(f"최근 {days}일 누적 실현손익이 +{total_pnl:,.0f} KRW 입니다.")
    else:
        weaknesses.append(f"최근 {days}일 누적 실현손익이 {total_pnl:,.0f} KRW 입니다.")

    bear_stat = by_regime.get("BEAR")
    if bear_stat and bear_stat["avg_pnl_pct"] < 0:
        weaknesses.append("하락장(BEAR) 구간 평균 손익률이 음수입니다.")
        improvements.append("BEAR 레짐에서 포지션 비중/진입 횟수를 더 보수적으로 제한하세요.")

    if max_loss_streak >= 3:
        weaknesses.append(f"최대 연속 손실이 {max_loss_streak}회입니다.")
        improvements.append("연속 손실 2회 이후엔 강제 쿨다운 시간을 늘려 과매매를 방지하세요.")

    # 즉시 개선안은 항상 3개를 제공하도록 안전 채움
    if len(improvements) < 3:
        improvements.append("RSI/거래량 조건을 만족해도 변동성 급등 구간에서는 진입을 한 단계 보류하세요.")
    if len(improvements) < 3:
        improvements.append("승률보다 손익비를 우선 관리하도록 STOP_LOSS/TAKE_PROFIT 비율을 주간 점검하세요.")
    if len(improvements) < 3:
        improvements.append("동일 심볼 재진입 간격을 늘려 단기 노이즈 진입을 줄이세요.")

    return {
        "status": "OK",
        "summary": {
            "days": days,
            "sell_count": total_count,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": win_rate,
            "total_realized_pnl_krw": total_pnl,
            "avg_pnl_pct": sum(item["pnl_pct"] for item in sell_results) / total_count,
            "max_loss_streak": max_loss_streak,
        },
        "by_regime": by_regime,
        "by_exit_reason": by_exit_reason,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "improvements": improvements[:3],
        "notes": notes,
    }
