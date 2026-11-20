"""Acesso ao SQLite.

Uma conexão por processo, criada sob demanda. Abrir uma conexão por mensagem
funciona em teste e cai em "database is locked" assim que o servidor fica
movimentado, porque a API lê o mesmo arquivo ao mesmo tempo. WAL resolve a
maior parte desse conflito.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite

from core.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS activity_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id     TEXT NOT NULL,
    channel_id   TEXT NOT NULL,
    channel_name TEXT,
    author_id    TEXT NOT NULL,
    event_type   TEXT NOT NULL DEFAULT 'message',
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activity_guild_created
    ON activity_events (guild_id, created_at);

CREATE INDEX IF NOT EXISTS idx_activity_guild_channel
    ON activity_events (guild_id, channel_id);

CREATE INDEX IF NOT EXISTS idx_activity_guild_author
    ON activity_events (guild_id, author_id);
"""

_connection: aiosqlite.Connection | None = None
_lock = asyncio.Lock()


async def get_db() -> aiosqlite.Connection:
    """Devolve a conexão compartilhada, abrindo-a na primeira chamada."""
    global _connection
    if _connection is not None:
        return _connection

    async with _lock:
        if _connection is None:
            _connection = await _open()
    return _connection


async def _open() -> aiosqlite.Connection:
    path = Path(get_settings().database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = await aiosqlite.connect(path)
    connection.row_factory = aiosqlite.Row
    await connection.execute("PRAGMA journal_mode=WAL")
    await connection.execute("PRAGMA synchronous=NORMAL")
    await connection.execute("PRAGMA busy_timeout=5000")
    await connection.executescript(SCHEMA)
    await _migrate(connection)
    await connection.commit()
    return connection


async def _migrate(connection: aiosqlite.Connection) -> None:
    """Migrações simples, suficientes para um banco de arquivo único."""
    cursor = await connection.execute("PRAGMA table_info(activity_events)")
    columns = {row["name"] for row in await cursor.fetchall()}
    if "channel_name" not in columns:
        await connection.execute("ALTER TABLE activity_events ADD COLUMN channel_name TEXT")


async def close_db() -> None:
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None
