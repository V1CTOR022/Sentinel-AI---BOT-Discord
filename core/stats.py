"""Consultas de leitura usadas pela API e pelos relatórios do bot.

Ficam em um lugar só para que o endpoint e o comando /relatorio nunca
discordem sobre o que é "mensagem na última semana".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiosqlite


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_days_ago(days: int) -> str:
    return (utc_now() - timedelta(days=days)).isoformat(timespec="seconds")


async def list_guilds(db: aiosqlite.Connection) -> list[dict]:
    cursor = await db.execute(
        """
        SELECT guild_id,
               COUNT(*) AS total_messages,
               MAX(created_at) AS last_activity
        FROM activity_events
        GROUP BY guild_id
        ORDER BY total_messages DESC
        """
    )
    return [dict(row) for row in await cursor.fetchall()]


async def guild_metrics(db: aiosqlite.Connection, guild_id: str) -> dict:
    cursor = await db.execute(
        """
        SELECT COUNT(*) AS total_messages,
               COUNT(DISTINCT author_id) AS active_users,
               COUNT(DISTINCT channel_id) AS active_channels,
               MAX(created_at) AS last_activity
        FROM activity_events
        WHERE guild_id = ?
        """,
        (guild_id,),
    )
    row = await cursor.fetchone()

    cursor = await db.execute(
        "SELECT COUNT(*) AS c FROM activity_events WHERE guild_id = ? AND created_at >= ?",
        (guild_id, iso_days_ago(1)),
    )
    last_24h = (await cursor.fetchone())["c"]

    cursor = await db.execute(
        "SELECT COUNT(*) AS c FROM activity_events WHERE guild_id = ? AND created_at >= ?",
        (guild_id, iso_days_ago(7)),
    )
    last_7d = (await cursor.fetchone())["c"]

    return {
        "total_messages": row["total_messages"],
        "active_users": row["active_users"],
        "active_channels": row["active_channels"],
        "last_activity": row["last_activity"],
        "messages_last_24h": last_24h,
        "messages_last_7d": last_7d,
    }


async def top_channels(db: aiosqlite.Connection, guild_id: str, limit: int = 10, days: int | None = None) -> list[dict]:
    params: list = [guild_id]
    window = ""
    if days is not None:
        window = "AND created_at >= ?"
        params.append(iso_days_ago(days))
    params.append(limit)

    cursor = await db.execute(
        f"""
        SELECT channel_id,
               MAX(channel_name) AS channel_name,
               COUNT(*) AS message_count,
               COUNT(DISTINCT author_id) AS unique_authors,
               MAX(created_at) AS last_activity
        FROM activity_events
        WHERE guild_id = ? {window}
        GROUP BY channel_id
        ORDER BY message_count DESC
        LIMIT ?
        """,
        params,
    )
    return [dict(row) for row in await cursor.fetchall()]


async def top_authors(db: aiosqlite.Connection, guild_id: str, limit: int = 10, days: int | None = None) -> list[dict]:
    params: list = [guild_id]
    window = ""
    if days is not None:
        window = "AND created_at >= ?"
        params.append(iso_days_ago(days))
    params.append(limit)

    cursor = await db.execute(
        f"""
        SELECT author_id,
               COUNT(*) AS message_count,
               COUNT(DISTINCT channel_id) AS channels_used
        FROM activity_events
        WHERE guild_id = ? {window}
        GROUP BY author_id
        ORDER BY message_count DESC
        LIMIT ?
        """,
        params,
    )
    return [dict(row) for row in await cursor.fetchall()]


async def daily_timeline(db: aiosqlite.Connection, guild_id: str, days: int = 14) -> list[dict]:
    """Mensagens por dia, preenchendo com zero os dias sem atividade."""
    cursor = await db.execute(
        """
        SELECT substr(created_at, 1, 10) AS day,
               COUNT(*) AS message_count,
               COUNT(DISTINCT author_id) AS active_users
        FROM activity_events
        WHERE guild_id = ? AND created_at >= ?
        GROUP BY day
        """,
        (guild_id, iso_days_ago(days)),
    )
    counted = {row["day"]: dict(row) for row in await cursor.fetchall()}

    today = utc_now().date()
    timeline = []
    for offset in range(days - 1, -1, -1):
        day = (today - timedelta(days=offset)).isoformat()
        entry = counted.get(day)
        timeline.append(
            {
                "day": day,
                "message_count": entry["message_count"] if entry else 0,
                "active_users": entry["active_users"] if entry else 0,
            }
        )
    return timeline
