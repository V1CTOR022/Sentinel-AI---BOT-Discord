"""Configuração lida uma única vez, na subida do processo.

A ideia é falhar cedo e com mensagem clara: se alguém escrever
MOD_LOG_CHANNEL_ID="canal-mod" no .env, é melhor descobrir agora do que
tomar um ValueError silencioso no meio do on_message.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

DEFAULT_AI_BASE_URL = "https://api.openai.com/v1"


class ConfigError(RuntimeError):
    """Variável de ambiente ausente ou com valor inválido."""


def _int_or_none(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as error:
        raise ConfigError(f"{name} deve ser um ID numérico do Discord (recebi {raw!r}).") from error


def _int_with_default(name: str, default: int) -> int:
    value = _int_or_none(name)
    return default if value is None else value


@dataclass(frozen=True)
class Settings:
    database_path: str
    discord_token: str | None
    guild_id: int | None
    mod_log_channel_id: int | None
    report_channel_id: int | None
    report_interval_hours: int
    flood_limit: int
    flood_window_seconds: int
    ai_api_key: str | None
    ai_model: str | None
    ai_base_url: str
    api_key: str | None
    dashboard_origins: tuple[str, ...]

    @property
    def ai_enabled(self) -> bool:
        # Sem modelo não há como chamar o provedor, então a IA fica desligada
        # em vez de falhar na primeira pergunta.
        return bool(self.ai_api_key and self.ai_model)

    def require_token(self) -> str:
        if not self.discord_token:
            raise ConfigError("DISCORD_TOKEN não está definido. Copie .env.example para .env e preencha.")
        return self.discord_token


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    origins = os.getenv("DASHBOARD_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return Settings(
        database_path=os.getenv("DATABASE_PATH", "data/sentinel.db"),
        discord_token=os.getenv("DISCORD_TOKEN") or None,
        guild_id=_int_or_none("DISCORD_GUILD_ID"),
        mod_log_channel_id=_int_or_none("MOD_LOG_CHANNEL_ID"),
        report_channel_id=_int_or_none("REPORT_CHANNEL_ID"),
        report_interval_hours=_int_with_default("REPORT_INTERVAL_HOURS", 24),
        flood_limit=_int_with_default("FLOOD_LIMIT", 6),
        flood_window_seconds=_int_with_default("FLOOD_WINDOW_SECONDS", 8),
        ai_api_key=os.getenv("AI_API_KEY") or None,
        ai_model=os.getenv("AI_MODEL") or None,
        ai_base_url=os.getenv("AI_BASE_URL") or DEFAULT_AI_BASE_URL,
        api_key=os.getenv("SENTINEL_API_KEY") or None,
        dashboard_origins=tuple(item.strip() for item in origins.split(",") if item.strip()),
    )
