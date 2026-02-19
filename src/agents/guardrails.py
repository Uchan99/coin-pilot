from datetime import datetime, timezone
from typing import Any, Dict, Tuple


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def is_low_credit_error(reasoning: str) -> bool:
    if not reasoning:
        return False
    lower = reasoning.lower()
    return (
        "credit balance is too low" in lower
        or "insufficient credits" in lower
        or "billing" in lower
    )


def is_ai_error_reason(reasoning: str) -> bool:
    if not reasoning:
        return False
    return ("AI Analysis Error" in reasoning) or ("Error code:" in reasoning)


def get_reject_cooldown_minutes(reject_count_30m: int, cfg: Dict[str, Any] | None) -> int:
    entry = cfg or {}
    lvl1 = _to_int(entry.get("ai_reject_cooldown_min_1"), 5)
    lvl2 = _to_int(entry.get("ai_reject_cooldown_min_2"), 10)
    lvl3 = _to_int(entry.get("ai_reject_cooldown_min_3"), 15)
    if reject_count_30m <= 1:
        return lvl1
    if reject_count_30m == 2:
        return lvl2
    return lvl3


async def should_block_ai_call(redis_client, symbol: str, cfg: Dict[str, Any] | None) -> Tuple[bool, str]:
    if redis_client is None:
        return False, ""

    entry = cfg or {}
    global_block_ttl = await redis_client.ttl("ai:guard:global:block")
    if global_block_ttl and global_block_ttl > 0:
        return True, f"Global AI block active ({global_block_ttl}s left)"

    symbol_cooldown_ttl = await redis_client.ttl(f"ai:guard:symbol:{symbol}:cooldown")
    if symbol_cooldown_ttl and symbol_cooldown_ttl > 0:
        return True, f"Symbol AI cooldown active ({symbol_cooldown_ttl}s left)"

    now = datetime.now(timezone.utc)
    hour_key = f"ai:usage:hour:{now.strftime('%Y%m%d%H')}"
    day_key = f"ai:usage:day:{now.strftime('%Y%m%d')}"

    hour_limit = _to_int(entry.get("ai_max_calls_per_hour"), 20)
    day_limit = _to_int(entry.get("ai_max_calls_per_day"), 120)

    hour_used = _to_int(await redis_client.get(hour_key), 0)
    if hour_used >= hour_limit:
        return True, f"Hourly AI budget exhausted ({hour_used}/{hour_limit})"

    day_used = _to_int(await redis_client.get(day_key), 0)
    if day_used >= day_limit:
        return True, f"Daily AI budget exhausted ({day_used}/{day_limit})"

    return False, ""


async def mark_ai_call_started(redis_client) -> None:
    if redis_client is None:
        return
    now = datetime.now(timezone.utc)
    hour_key = f"ai:usage:hour:{now.strftime('%Y%m%d%H')}"
    day_key = f"ai:usage:day:{now.strftime('%Y%m%d')}"

    await redis_client.incr(hour_key)
    await redis_client.expire(hour_key, 2 * 3600)
    await redis_client.incr(day_key)
    await redis_client.expire(day_key, 2 * 24 * 3600)


async def update_ai_guardrails_after_decision(
    redis_client,
    symbol: str,
    approved: bool,
    reasoning: str,
    cfg: Dict[str, Any] | None,
) -> None:
    if redis_client is None:
        return

    entry = cfg or {}

    if approved:
        await redis_client.delete(f"ai:guard:symbol:{symbol}:reject_count")
        await redis_client.delete("ai:guard:error_streak")
        return

    reject_window = _to_int(entry.get("ai_reject_cooldown_window_min"), 30)
    reject_count_key = f"ai:guard:symbol:{symbol}:reject_count"
    reject_count = await redis_client.incr(reject_count_key)
    await redis_client.expire(reject_count_key, max(60, reject_window * 60))

    cooldown_min = get_reject_cooldown_minutes(reject_count, entry)
    await redis_client.set(
        f"ai:guard:symbol:{symbol}:cooldown",
        str(cooldown_min),
        ex=max(60, cooldown_min * 60),
    )

    if is_low_credit_error(reasoning):
        block_min = _to_int(entry.get("ai_credit_block_minutes"), 60)
        await redis_client.set("ai:guard:global:block", "low_credit", ex=max(60, block_min * 60))
        return

    error_streak_key = "ai:guard:error_streak"
    if is_ai_error_reason(reasoning):
        streak = await redis_client.incr(error_streak_key)
        await redis_client.expire(error_streak_key, 3600)
        threshold = _to_int(entry.get("ai_error_streak_threshold"), 5)
        if streak >= threshold:
            block_min = _to_int(entry.get("ai_error_block_minutes"), 30)
            await redis_client.set("ai:guard:global:block", "error_streak", ex=max(60, block_min * 60))
    else:
        await redis_client.delete(error_streak_key)
