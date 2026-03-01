import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

import discord
import httpx
from discord import app_commands


logging.basicConfig(
    level=os.getenv("DISCORD_BOT_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
LOGGER = logging.getLogger("coinpilot.discord_bot")


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def _parse_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None and value != "" else default
    except (TypeError, ValueError):
        return default


def _parse_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None and value != "" else default
    except (TypeError, ValueError):
        return default


def _parse_id_set(raw: str | None) -> set[int]:
    if not raw:
        return set()
    parsed: set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if token.isdigit():
            parsed.add(int(token))
    return parsed


def _fmt_krw(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):,.0f} KRW"


def _truncate_message(text: str, max_chars: int = 1900) -> str:
    if len(text) <= max_chars:
        return text
    clipped = text[: max_chars - 32].rstrip()
    return f"{clipped}\n(길이 제한으로 일부 생략)"


@dataclass
class BotConfig:
    token: str
    api_base_url: str
    api_secret: str
    guild_id: int | None
    allowed_channel_ids: set[int]
    allowed_role_ids: set[int]
    rate_limit_per_min: int
    ephemeral_default: bool
    request_timeout_sec: float

    @classmethod
    def from_env(cls) -> "BotConfig":
        guild_raw = os.getenv("DISCORD_GUILD_ID", "").strip()
        guild_id = int(guild_raw) if guild_raw.isdigit() else None

        return cls(
            token=os.getenv("DISCORD_BOT_TOKEN", "").strip(),
            api_base_url=os.getenv("COINPILOT_API_BASE_URL", "http://bot:8000").rstrip("/"),
            api_secret=os.getenv("COINPILOT_API_SHARED_SECRET", "").strip(),
            guild_id=guild_id,
            allowed_channel_ids=_parse_id_set(os.getenv("DISCORD_ALLOWED_CHANNEL_IDS", "")),
            allowed_role_ids=_parse_id_set(os.getenv("DISCORD_ALLOWED_ROLE_IDS", "")),
            rate_limit_per_min=max(1, _parse_int(os.getenv("DISCORD_QUERY_RATE_LIMIT_PER_MIN"), 30)),
            ephemeral_default=_parse_bool(os.getenv("DISCORD_BOT_EPHEMERAL_DEFAULT", "true"), True),
            request_timeout_sec=_parse_float(os.getenv("DISCORD_API_TIMEOUT_SEC"), 8.0),
        )


class PerUserRateLimiter:
    """
    Discord Slash Command 폭주를 방지하기 위한 사용자 단위 1분 윈도우 제한기.
    실패 모드:
    - 메모리 기반이므로 프로세스 재시작 시 카운터는 리셋된다.
    - 단일 인스턴스 기준 제어이며, 수평 확장 시 Redis 기반 제한기로 교체가 필요하다.
    """

    def __init__(self, max_per_minute: int) -> None:
        self.max_per_minute = max_per_minute
        self._events: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, user_id: int) -> tuple[bool, int]:
        now = time.time()
        window = self._events[user_id]
        while window and (now - window[0]) > 60.0:
            window.popleft()
        if len(window) >= self.max_per_minute:
            retry_after = max(1, int(60 - (now - window[0])))
            return False, retry_after
        window.append(now)
        return True, 0


class CoinPilotDiscordBot(discord.Client):
    def __init__(self, config: BotConfig):
        intents = discord.Intents.none()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.config = config
        self.rate_limiter = PerUserRateLimiter(config.rate_limit_per_min)
        self.http_client = httpx.AsyncClient(timeout=httpx.Timeout(config.request_timeout_sec))

    async def setup_hook(self) -> None:
        self._register_commands()
        if self.config.guild_id:
            guild = discord.Object(id=self.config.guild_id)
            await self.tree.sync(guild=guild)
            LOGGER.info("Slash commands synced to guild=%s", self.config.guild_id)
        else:
            await self.tree.sync()
            LOGGER.info("Slash commands synced globally")

    async def close(self) -> None:
        await self.http_client.aclose()
        await super().close()

    async def on_ready(self) -> None:
        LOGGER.info("Discord bot connected as %s", self.user)

    def _register_commands(self) -> None:
        guild_scope = discord.Object(id=self.config.guild_id) if self.config.guild_id else None

        @self.tree.command(name="positions", description="현재 보유 포지션과 평가손익 조회", guild=guild_scope)
        async def positions_cmd(interaction: discord.Interaction) -> None:
            await self._handle_simple_command(interaction, endpoint="/positions", formatter=self._format_positions)

        @self.tree.command(name="pnl", description="당일/최근 손익 요약 조회", guild=guild_scope)
        async def pnl_cmd(interaction: discord.Interaction) -> None:
            await self._handle_simple_command(interaction, endpoint="/pnl", formatter=self._format_pnl)

        @self.tree.command(name="status", description="CoinPilot 서비스 상태 조회", guild=guild_scope)
        async def status_cmd(interaction: discord.Interaction) -> None:
            await self._handle_simple_command(interaction, endpoint="/status", formatter=self._format_status)

        @self.tree.command(name="risk", description="현재 리스크 진단 조회", guild=guild_scope)
        async def risk_cmd(interaction: discord.Interaction) -> None:
            await self._handle_simple_command(interaction, endpoint="/risk", formatter=self._format_risk)

        @self.tree.command(name="ask", description="CoinPilot 챗봇 질의", guild=guild_scope)
        @app_commands.describe(query="예: 지금 KRW-BTC는 관망이 좋을까?")
        async def ask_cmd(interaction: discord.Interaction, query: str) -> None:
            allowed, deny_message = self._check_access(interaction)
            if not allowed:
                await self._safe_respond(interaction, deny_message, ephemeral=True)
                return

            rate_ok, retry_after = self.rate_limiter.allow(interaction.user.id)
            if not rate_ok:
                await self._safe_respond(
                    interaction,
                    f"요청이 너무 많습니다. {retry_after}초 후 다시 시도해주세요.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=self.config.ephemeral_default, thinking=True)
            payload = await self._call_api("POST", "/ask", json_payload={"query": query})
            if not payload.get("ok"):
                await interaction.edit_original_response(content=self._format_api_error(payload))
                return

            answer = str(payload.get("data", {}).get("answer") or "응답이 비어 있습니다.")
            await interaction.edit_original_response(content=_truncate_message(answer))

    def _check_access(self, interaction: discord.Interaction) -> tuple[bool, str]:
        channel_id = interaction.channel_id
        if self.config.allowed_channel_ids and channel_id not in self.config.allowed_channel_ids:
            return False, "이 명령은 허용된 채널에서만 사용할 수 있습니다."

        if self.config.allowed_role_ids:
            member = interaction.user
            role_ids = {role.id for role in getattr(member, "roles", [])}
            if not (role_ids & self.config.allowed_role_ids):
                return False, "이 명령을 사용할 권한이 없습니다."

        return True, ""

    async def _handle_simple_command(
        self,
        interaction: discord.Interaction,
        endpoint: str,
        formatter,
    ) -> None:
        allowed, deny_message = self._check_access(interaction)
        if not allowed:
            await self._safe_respond(interaction, deny_message, ephemeral=True)
            return

        rate_ok, retry_after = self.rate_limiter.allow(interaction.user.id)
        if not rate_ok:
            await self._safe_respond(
                interaction,
                f"요청이 너무 많습니다. {retry_after}초 후 다시 시도해주세요.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=self.config.ephemeral_default, thinking=True)
        payload = await self._call_api("GET", endpoint)
        if not payload.get("ok"):
            await interaction.edit_original_response(content=self._format_api_error(payload))
            return

        await interaction.edit_original_response(content=_truncate_message(formatter(payload)))

    async def _call_api(
        self,
        method: str,
        endpoint: str,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.config.api_base_url}/api/mobile{endpoint}"
        headers = {"X-Api-Secret": self.config.api_secret}
        try:
            response = await self.http_client.request(method, url, headers=headers, json=json_payload)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            return {"ok": False, "error": "Invalid JSON payload type."}
        except Exception as exc:
            LOGGER.exception("API call failed: %s %s", method, url)
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _format_api_error(payload: dict[str, Any]) -> str:
        error = payload.get("error") or payload.get("detail") or "Unknown error"
        return f"조회 실패: {error}"

    @staticmethod
    def _format_positions(payload: dict[str, Any]) -> str:
        data = payload.get("data", {})
        holdings = data.get("holdings", [])

        lines = [
            "포트폴리오 요약",
            f"- 총 평가액: {_fmt_krw(data.get('total_valuation_krw'))}",
            f"- 현금 잔고: {_fmt_krw(data.get('cash_krw'))}",
            f"- 보유 자산 평가액: {_fmt_krw(data.get('holdings_value_krw'))}",
        ]

        if not holdings:
            lines.append("- 현재 보유 포지션이 없습니다.")
            return "\n".join(lines)

        lines.append("- 보유 포지션:")
        for row in holdings[:8]:
            pnl_pct = row.get("unrealized_pnl_pct")
            pnl_pct_text = "-" if pnl_pct is None else f"{float(pnl_pct):+.2f}%"
            lines.append(
                f"  {row.get('symbol')}: 평가 {_fmt_krw(row.get('valuation_krw'))}, "
                f"미실현 {pnl_pct_text} ({_fmt_krw(row.get('unrealized_pnl_krw'))})"
            )

        return "\n".join(lines)

    @staticmethod
    def _format_pnl(payload: dict[str, Any]) -> str:
        data = payload.get("data", {})
        last_sell = data.get("last_sell")

        lines = [
            "손익 요약",
            f"- 당일 손익: {_fmt_krw(data.get('daily_total_pnl_krw'))}",
            f"- 거래 횟수(BUY/SELL/총): {data.get('buy_count', 0)}/{data.get('sell_count', 0)}/{data.get('trade_count', 0)}",
            f"- 연속 손실: {data.get('consecutive_losses', 0)}회",
            f"- 거래 중단 상태: {'ON' if data.get('is_trading_halted') else 'OFF'}",
        ]

        if last_sell:
            pnl_pct = last_sell.get("realized_pnl_pct")
            pnl_pct_text = "-" if pnl_pct is None else f"{float(pnl_pct):+.2f}%"
            lines.extend(
                [
                    "- 마지막 SELL:",
                    f"  심볼 {last_sell.get('symbol')}, 손익 {pnl_pct_text} ({_fmt_krw(last_sell.get('realized_pnl_krw'))})",
                    f"  시각 {last_sell.get('filled_at_kst')}",
                ]
            )
        else:
            lines.append("- 마지막 SELL 데이터가 없습니다.")

        return "\n".join(lines)

    @staticmethod
    def _format_risk(payload: dict[str, Any]) -> str:
        data = payload.get("data", {})
        snapshot = data.get("snapshot", {})
        flags = data.get("flags", [])

        lines = [
            "리스크 진단",
            f"- 레벨: {data.get('risk_level', 'UNKNOWN')}",
            f"- 당일 손익: {_fmt_krw(snapshot.get('total_pnl'))}",
            f"- 연속 손실: {snapshot.get('consecutive_losses', 0)}회",
            f"- 포지션 집중도: {float(snapshot.get('position_concentration', 0.0)) * 100:.1f}%",
            f"- 최근 24h 리스크 이벤트: {snapshot.get('audit_events_24h', 0)}건",
        ]
        if flags:
            lines.append("- 주요 플래그:")
            for flag in flags[:4]:
                lines.append(f"  {flag}")

        return "\n".join(lines)

    @staticmethod
    def _format_status(payload: dict[str, Any]) -> str:
        data = payload.get("data", {})
        components = data.get("components", {})

        lines = [
            "시스템 상태",
            f"- Overall: {data.get('overall_status', 'UNKNOWN')}",
            f"- Risk Level: {data.get('risk_level', 'UNKNOWN')}",
            "- Components:",
        ]

        for name in ("bot", "db", "redis", "n8n"):
            component = components.get(name, {})
            status_text = component.get("status", "UNKNOWN")
            detail = component.get("detail")
            if detail:
                lines.append(f"  {name}: {status_text} ({detail})")
            else:
                lines.append(f"  {name}: {status_text}")

        flags = data.get("risk_flags", [])
        if flags:
            lines.append("- 리스크 플래그:")
            for flag in flags[:3]:
                lines.append(f"  {flag}")

        return "\n".join(lines)

    async def _safe_respond(self, interaction: discord.Interaction, content: str, ephemeral: bool) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(content=content, ephemeral=ephemeral)
            return
        await interaction.response.send_message(content=content, ephemeral=ephemeral)


def _validate_config(config: BotConfig) -> None:
    missing: list[str] = []
    if not config.token:
        missing.append("DISCORD_BOT_TOKEN")
    if not config.api_secret:
        missing.append("COINPILOT_API_SHARED_SECRET")
    if not config.api_base_url:
        missing.append("COINPILOT_API_BASE_URL")

    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")


def main() -> None:
    config = BotConfig.from_env()
    _validate_config(config)

    bot = CoinPilotDiscordBot(config)
    bot.run(config.token)


if __name__ == "__main__":
    main()
