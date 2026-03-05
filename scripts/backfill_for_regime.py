"""
레짐 판단/백테스트용 과거 1분봉 데이터 수집 스크립트
파일: scripts/backfill_for_regime.py

기본 실행(호환 모드):
  PYTHONPATH=. python scripts/backfill_for_regime.py
  -> 심볼별 12,000개(약 8.3일) 백필

장기 실행 예시:
  PYTHONPATH=. python scripts/backfill_for_regime.py --days 120
  PYTHONPATH=. python scripts/backfill_for_regime.py --days 240 --symbols KRW-BTC,KRW-ETH
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable

import httpx
from sqlalchemy.dialects.postgresql import insert

from src.common.db import get_db_session
from src.common.models import MarketData

# 대상 심볼 목록 (설정 로딩 실패와 무관하게 항상 동작하도록 고정)
DEFAULT_SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE"]

UPBIT_MINUTE_API = "https://api.upbit.com/v1/candles/minutes/1"
MAX_BATCH_SIZE = 200  # 업비트 분봉 API 최대치
DEFAULT_TARGET_MINUTES = 12000  # 기존 동작 호환: 200시간치


@dataclass
class BackfillStats:
    symbol: str
    requested: int = 0
    fetched: int = 0
    inserted: int = 0
    duplicate: int = 0
    api_errors: int = 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upbit 1분봉 장기 백필 스크립트")
    parser.add_argument(
        "--symbols",
        default=",".join(DEFAULT_SYMBOLS),
        help="쉼표 구분 심볼 목록 (예: KRW-BTC,KRW-ETH)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="심볼당 백필 일수(1일=1440분). 지정 시 --target-minutes보다 우선",
    )
    parser.add_argument(
        "--target-minutes",
        type=int,
        default=DEFAULT_TARGET_MINUTES,
        help="심볼당 목표 1분봉 개수(기본: 12000)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=MAX_BATCH_SIZE,
        help="API 1회 호출 캔들 수(최대 200)",
    )
    parser.add_argument(
        "--sleep-sec",
        type=float,
        default=0.15,
        help="API 호출 간 대기(초). 업비트 제한 대응용",
    )
    parser.add_argument(
        "--http-timeout-sec",
        type=float,
        default=30.0,
        help="HTTP 타임아웃(초)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="429/5xx/네트워크 오류 재시도 횟수",
    )
    parser.add_argument(
        "--status-every",
        type=int,
        default=10,
        help="진행 로그 출력 간격(배치 단위)",
    )
    return parser.parse_args()


def _parse_symbols(raw_symbols: str) -> list[str]:
    symbols = [item.strip().upper() for item in raw_symbols.split(",") if item.strip()]
    if not symbols:
        raise ValueError("최소 1개 이상의 심볼이 필요합니다.")
    return symbols


def _target_minutes(args: argparse.Namespace) -> int:
    if args.days is not None:
        if args.days <= 0:
            raise ValueError("--days는 1 이상이어야 합니다.")
        return args.days * 1440
    if args.target_minutes <= 0:
        raise ValueError("--target-minutes는 1 이상이어야 합니다.")
    return args.target_minutes


def _to_kst(dt: datetime) -> str:
    return dt.astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S %Z")


def _candle_to_row(candle: dict) -> dict:
    # Upbit UTC 문자열(candle_date_time_utc)은 timezone 정보가 없으므로 UTC를 명시해야 한다.
    ts_utc = datetime.fromisoformat(candle["candle_date_time_utc"]).replace(tzinfo=timezone.utc)
    return {
        "symbol": candle["market"],
        "interval": "1m",
        "open_price": Decimal(str(candle["opening_price"])),
        "high_price": Decimal(str(candle["high_price"])),
        "low_price": Decimal(str(candle["low_price"])),
        "close_price": Decimal(str(candle["trade_price"])),
        "volume": Decimal(str(candle["candle_acc_trade_volume"])),
        "timestamp": ts_utc,
    }


async def _fetch_candles_batch(
    client: httpx.AsyncClient,
    *,
    symbol: str,
    count: int,
    to_time: datetime | None,
    max_retries: int,
) -> list[dict]:
    params = {"market": symbol, "count": count}
    if to_time:
        params["to"] = to_time.strftime("%Y-%m-%dT%H:%M:%S")

    for attempt in range(1, max_retries + 1):
        try:
            response = await client.get(UPBIT_MINUTE_API, params=params)

            if response.status_code == 429 or response.status_code >= 500:
                # 임시 장애/레이트리밋은 지수 백오프로 재시도한다.
                await asyncio.sleep(min(2.0, 0.25 * attempt))
                continue

            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError(f"예상치 못한 API 응답 형식: {type(payload)!r}")
            return payload
        except (httpx.HTTPError, ValueError):
            if attempt == max_retries:
                raise
            await asyncio.sleep(min(2.0, 0.25 * attempt))

    return []


async def _save_candles(candles: Iterable[dict]) -> tuple[int, int]:
    rows = [_candle_to_row(candle) for candle in candles]
    if not rows:
        return 0, 0

    async with get_db_session() as session:
        stmt = insert(MarketData).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_market_data_symbol_interval_ts"
        ).returning(MarketData.timestamp)
        result = await session.execute(stmt)
        inserted = len(result.fetchall())
        await session.commit()

    attempted = len(rows)
    duplicate = max(0, attempted - inserted)
    return inserted, duplicate


async def _backfill_symbol(
    *,
    client: httpx.AsyncClient,
    symbol: str,
    target_minutes: int,
    batch_size: int,
    sleep_sec: float,
    max_retries: int,
    status_every: int,
) -> BackfillStats:
    stats = BackfillStats(symbol=symbol, requested=target_minutes)
    to_time: datetime | None = None
    prev_oldest: datetime | None = None
    iteration = 0

    while stats.fetched < target_minutes:
        count = min(batch_size, target_minutes - stats.fetched)
        iteration += 1

        try:
            candles = await _fetch_candles_batch(
                client,
                symbol=symbol,
                count=count,
                to_time=to_time,
                max_retries=max_retries,
            )
        except Exception as exc:
            stats.api_errors += 1
            print(f"[{symbol}] [WARN] API 호출 실패(iter={iteration}): {exc}")
            await asyncio.sleep(min(2.0, sleep_sec * 4))
            continue

        if not candles:
            print(f"[{symbol}] [INFO] 더 이상 가져올 캔들이 없습니다. fetched={stats.fetched}")
            break

        inserted, duplicate = await _save_candles(candles)
        stats.fetched += len(candles)
        stats.inserted += inserted
        stats.duplicate += duplicate

        oldest = datetime.fromisoformat(candles[-1]["candle_date_time_utc"]).replace(
            tzinfo=timezone.utc
        )
        if prev_oldest and oldest >= prev_oldest:
            # API 응답 경계가 겹치면 동일 구간만 반복될 수 있어 강제 종료한다.
            print(
                f"[{symbol}] [WARN] oldest 역행 없음 감지(반복 가능성). "
                f"oldest={oldest.isoformat()}, prev={prev_oldest.isoformat()}"
            )
            break

        prev_oldest = oldest
        # Upbit `to`는 inclusive 성격으로 동일 timestamp 재포함 가능성이 있어 1초 차감.
        to_time = oldest - timedelta(seconds=1)

        if iteration % max(1, status_every) == 0 or stats.fetched >= target_minutes:
            print(
                f"[{symbol}] [{iteration}] fetched={stats.fetched}/{target_minutes}, "
                f"inserted={stats.inserted}, dup={stats.duplicate}, "
                f"oldest_utc={oldest.isoformat()} ({_to_kst(oldest)})"
            )

        await asyncio.sleep(max(0.0, sleep_sec))

    return stats


async def main() -> None:
    args = _parse_args()
    symbols = _parse_symbols(args.symbols)
    target = _target_minutes(args)
    batch_size = min(MAX_BATCH_SIZE, max(1, args.batch_size))

    print("=" * 70)
    print("장기 1분봉 백필 시작")
    print("=" * 70)
    print(f"심볼: {symbols}")
    print(f"목표: 심볼당 {target}개 (약 {target / 60:.1f}시간, {target / 1440:.1f}일)")
    print(
        f"옵션: batch={batch_size}, sleep={args.sleep_sec}s, timeout={args.http_timeout_sec}s, "
        f"max_retries={args.max_retries}"
    )
    print()

    async with httpx.AsyncClient(timeout=args.http_timeout_sec) as client:
        results = []
        for symbol in symbols:
            print(f"\n[{symbol}] 백필 시작")
            stats = await _backfill_symbol(
                client=client,
                symbol=symbol,
                target_minutes=target,
                batch_size=batch_size,
                sleep_sec=args.sleep_sec,
                max_retries=args.max_retries,
                status_every=args.status_every,
            )
            results.append(stats)
            print(
                f"[{symbol}] 완료: fetched={stats.fetched}, inserted={stats.inserted}, "
                f"dup={stats.duplicate}, api_errors={stats.api_errors}"
            )

    total_fetched = sum(item.fetched for item in results)
    total_inserted = sum(item.inserted for item in results)
    total_dup = sum(item.duplicate for item in results)
    total_api_errors = sum(item.api_errors for item in results)

    print("\n" + "=" * 70)
    print("백필 요약")
    print("=" * 70)
    for item in results:
        print(
            f"- {item.symbol}: fetched={item.fetched}, inserted={item.inserted}, "
            f"dup={item.duplicate}, api_errors={item.api_errors}"
        )
    print(
        f"TOTAL: fetched={total_fetched}, inserted={total_inserted}, "
        f"dup={total_dup}, api_errors={total_api_errors}"
    )
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
