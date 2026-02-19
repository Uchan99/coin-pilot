from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from collections import defaultdict

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

from src.common.models import DailyRiskState, AccountState, TradingHistory
from src.common.notification import notifier
from src.analytics.performance import PerformanceAnalytics


class DailyReporter:
    """
    일간 리포트 생성기:
    1. DB에서 하루의 매매 요약 정보 조회
    2. LLM으로 정성 요약 생성
    3. n8n 웹훅으로 Discord 전송

    안전 fallback 원칙:
    - post-exit 데이터가 없어도 리포트 생성은 계속한다.
    - SELL의 entry_avg_price가 없으면 BUY 이력 기반 추정으로 보완한다.
    - 계산 불가능한 건은 제외하고 "데이터 부족"을 명시한다.
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

    async def generate_and_send(self):
        async with self.session_factory() as session:
            data = await self._fetch_daily_data(session)

        if not data:
            print("[DailyReporter] No data found for today.")
            return

        summary = await self._generate_llm_summary(data)

        payload = {
            "title": f"📅 CoinPilot Daily Report ({data['date']})",
            "pnl": f"{data['total_pnl']:,.0f} KRW",
            "trades": data["trade_count"],
            "sell_trades": data.get("sell_trade_count", 0),
            "win_rate": (
                f"{data['win_rate'] * 100:.1f}%"
                if data.get("sell_trade_count", 0) > 0
                else "N/A"
            ),
            "mdd": f"{data['mdd']:.2f}%",
            "exit_breakdown": data.get("exit_breakdown", {}),
            "notes": data.get("notes", []),
            "summary": summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await notifier.send_webhook("/webhook/daily-report", payload)
        print(f"[DailyReporter] Report sent: {payload['title']}")

    @staticmethod
    def _to_decimal(v: Any) -> Optional[Decimal]:
        if v is None:
            return None
        try:
            return Decimal(str(v))
        except Exception:
            return None

    @staticmethod
    def _safe_mean(values: List[float]) -> Optional[float]:
        if not values:
            return None
        return round(sum(values) / len(values), 4)

    @staticmethod
    def _extract_entry_avg_price(signal_info: Any) -> Optional[Decimal]:
        if isinstance(signal_info, dict):
            return DailyReporter._to_decimal(signal_info.get("entry_avg_price"))
        return None

    @staticmethod
    def _extract_post_exit_1h_change(signal_info: Any) -> Optional[float]:
        if not isinstance(signal_info, dict):
            return None
        point_1h = signal_info.get("1h")
        if not isinstance(point_1h, dict):
            return None
        val = point_1h.get("change_pct")
        try:
            return float(val)
        except Exception:
            return None

    @staticmethod
    def _consume_buy_lots(buy_lots: Dict[str, List[Dict[str, Decimal]]], symbol: str, sell_qty: Decimal) -> Optional[Decimal]:
        """
        FIFO 방식으로 BUY lot을 소모하여 추정 entry_avg_price를 계산.
        계산 불가 시 None 반환.
        """
        if sell_qty <= 0:
            return None

        lots = buy_lots.get(symbol, [])
        if not lots:
            return None

        remaining = sell_qty
        total_cost = Decimal("0")
        consumed = Decimal("0")

        while remaining > 0 and lots:
            lot = lots[0]
            lot_qty = lot["qty"]
            if lot_qty <= 0:
                lots.pop(0)
                continue

            use_qty = lot_qty if lot_qty <= remaining else remaining
            total_cost += lot["price"] * use_qty
            consumed += use_qty
            remaining -= use_qty

            lot["qty"] = lot_qty - use_qty
            if lot["qty"] <= 0:
                lots.pop(0)

        if consumed <= 0:
            return None
        return total_cost / consumed

    async def _fetch_daily_data(self, session: AsyncSession) -> Dict[str, Any]:
        today = datetime.now(timezone.utc).date()
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)

        # 1) 일일 리스크 상태
        state_stmt = select(DailyRiskState).where(DailyRiskState.date == today)
        state_result = await session.execute(state_stmt)
        state = state_result.scalar_one_or_none()
        if not state:
            return None

        # 2) 계좌 상태(없어도 fallback)
        account_stmt = select(AccountState).where(AccountState.id == 1)
        account_result = await session.execute(account_stmt)
        account = account_result.scalar_one_or_none()

        # 3) 오늘 체결 거래 (executed_at 우선, 없으면 created_at fallback)
        hist_stmt = (
            select(TradingHistory)
            .where(
                and_(
                    TradingHistory.status == "FILLED",
                    or_(
                        TradingHistory.executed_at >= today_start,
                        and_(TradingHistory.executed_at.is_(None), TradingHistory.created_at >= today_start),
                    ),
                )
            )
            .order_by(func.coalesce(TradingHistory.executed_at, TradingHistory.created_at))
        )
        hist_result = await session.execute(hist_stmt)
        trades = hist_result.scalars().all()

        # 4) SELL 기준 실현손익/승률/exit breakdown 계산
        buy_lots: Dict[str, List[Dict[str, Decimal]]] = defaultdict(list)
        realized_trades: List[Dict[str, Any]] = []
        exit_breakdown_raw: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: {"pnl_pct": [], "post_1h": [], "count": 0}
        )
        notes: List[str] = []

        for t in trades:
            side = (t.side or "").upper()
            symbol = t.symbol
            price = self._to_decimal(t.price)
            qty = self._to_decimal(t.quantity)

            if price is None or qty is None or qty <= 0:
                continue

            if side == "BUY":
                buy_lots[symbol].append({"price": price, "qty": qty})
                continue

            if side != "SELL":
                continue

            entry_avg = self._extract_entry_avg_price(t.signal_info)
            if entry_avg is None:
                entry_avg = self._consume_buy_lots(buy_lots, symbol, qty)

            if entry_avg is None or entry_avg <= 0:
                notes.append(f"{symbol}: entry_avg_price 부족으로 SELL PnL 계산 제외")
                continue

            pnl = (price - entry_avg) * qty
            pnl_pct = float((price - entry_avg) / entry_avg * Decimal("100"))

            realized_trades.append({
                "symbol": symbol,
                "pnl": float(pnl),
                "pnl_pct": pnl_pct,
            })

            exit_reason = t.exit_reason or "UNKNOWN"
            bucket = exit_breakdown_raw[exit_reason]
            bucket["count"] += 1
            bucket["pnl_pct"].append(pnl_pct)

            post_1h = self._extract_post_exit_1h_change(t.post_exit_prices)
            if post_1h is not None:
                bucket["post_1h"].append(post_1h)

        win_rate = PerformanceAnalytics.calculate_win_rate(realized_trades)

        # MDD fallback: 일간 손실을 현재 잔고로 근사
        mdd = 0.0
        bal = self._to_decimal(account.balance) if account else None
        pnl_dec = self._to_decimal(state.total_pnl) or Decimal("0")
        if bal and bal > 0 and pnl_dec < 0:
            mdd = float(abs(pnl_dec) / bal * Decimal("100"))

        exit_breakdown: Dict[str, Dict[str, Any]] = {}
        for reason, raw in exit_breakdown_raw.items():
            exit_breakdown[reason] = {
                "count": raw["count"],
                "avg_pnl_pct": self._safe_mean(raw["pnl_pct"]),
                "avg_post_1h_pct": self._safe_mean(raw["post_1h"]),
            }

        if not realized_trades and any((t.side or "").upper() == "SELL" for t in trades):
            notes.append("SELL 체결은 있으나 PnL 계산 가능한 entry 정보가 부족합니다.")

        return {
            "date": today.isoformat(),
            "total_pnl": float(pnl_dec),
            "trade_count": int(state.trade_count or len(trades)),
            "sell_trade_count": len(realized_trades),
            "win_rate": win_rate,
            "mdd": mdd,
            "exit_breakdown": exit_breakdown,
            "notes": notes,
        }

    async def _generate_llm_summary(self, data: Dict[str, Any]) -> str:
        exit_breakdown = data.get("exit_breakdown") or {}
        notes = data.get("notes") or []

        if exit_breakdown:
            lines = []
            for reason, v in sorted(exit_breakdown.items(), key=lambda kv: kv[1].get("count", 0), reverse=True):
                avg_pnl = v.get("avg_pnl_pct")
                avg_post = v.get("avg_post_1h_pct")
                lines.append(
                    f"- {reason}: {v.get('count', 0)}건, avg_pnl_pct={avg_pnl if avg_pnl is not None else 'N/A'}, "
                    f"avg_post_1h_pct={avg_post if avg_post is not None else 'N/A'}"
                )
            exit_breakdown_text = "\n".join(lines)
        else:
            exit_breakdown_text = "- 오늘은 exit_breakdown 데이터가 충분하지 않습니다."

        notes_text = "\n".join(f"- {n}" for n in notes) if notes else "- 없음"

        prompt = PromptTemplate(
            input_variables=[
                "date",
                "total_pnl",
                "trade_count",
                "sell_trade_count",
                "win_rate",
                "mdd",
                "exit_breakdown_text",
                "notes_text",
            ],
            template="""
당신은 가상자산 매매 시스템 CoinPilot의 운영 리포트 작성자입니다.
아래 데이터를 기반으로 3~5줄의 짧고 구체적인 일간 브리핑을 작성하세요.

[기본 데이터]
- 날짜: {date}
- 총 손익: {total_pnl} KRW
- 총 체결 수: {trade_count}
- SELL 기준 분석 가능 거래 수: {sell_trade_count}
- 승률: {win_rate}%
- MDD(근사): {mdd}%

[Exit Breakdown]
{exit_breakdown_text}

[데이터 품질 메모]
{notes_text}

작성 규칙:
1) 숫자 근거를 1개 이상 포함
2) 데이터 부족 항목은 추정하지 말고 명시
3) 파라미터 조정 제안이 있으면 1개만 제시
""",
        )

        chain = prompt | self.llm
        try:
            response = await chain.ainvoke({
                "date": data["date"],
                "total_pnl": f"{data['total_pnl']:.2f}",
                "trade_count": data["trade_count"],
                "sell_trade_count": data.get("sell_trade_count", 0),
                "win_rate": (
                    f"{data['win_rate'] * 100:.1f}"
                    if data.get("sell_trade_count", 0) > 0
                    else "N/A"
                ),
                "mdd": f"{data['mdd']:.2f}",
                "exit_breakdown_text": exit_breakdown_text,
                "notes_text": notes_text,
            })
            return response.content
        except Exception as e:
            # LLM 실패 시에도 일간 리포트 전송은 계속한다.
            return (
                f"LLM 요약 생성 실패 ({e}). "
                f"기본 요약: trades={data.get('trade_count', 0)}, "
                f"win_rate={data.get('win_rate', 0) * 100:.1f}%, "
                f"total_pnl={data.get('total_pnl', 0):,.0f} KRW"
            )
