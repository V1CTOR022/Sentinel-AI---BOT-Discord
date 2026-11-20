"""Montagem dos relatórios de atividade.

O texto é gerado a partir do banco. A IA, quando configurada, só comenta o
resultado — os números nunca vêm do modelo.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.database import get_db
from core.stats import daily_timeline, guild_metrics, top_authors, top_channels


@dataclass
class ActivityReport:
    guild_id: str
    days: int
    metrics: dict
    channels: list[dict]
    authors: list[dict]
    timeline: list[dict]

    @property
    def is_empty(self) -> bool:
        return self.metrics["total_messages"] == 0

    def as_text(self) -> str:
        """Versão em texto, usada no embed e como entrada para a IA."""
        lines = [
            f"Período analisado: últimos {self.days} dias",
            f"Mensagens no período: {sum(day['message_count'] for day in self.timeline)}",
            f"Mensagens registradas no total: {self.metrics['total_messages']}",
            f"Mensagens nas últimas 24h: {self.metrics['messages_last_24h']}",
            f"Usuários distintos (histórico): {self.metrics['active_users']}",
            f"Canais distintos (histórico): {self.metrics['active_channels']}",
            "",
            "Canais mais ativos no período:",
        ]
        if self.channels:
            for position, channel in enumerate(self.channels, start=1):
                name = channel["channel_name"] or f"id {channel['channel_id']}"
                lines.append(
                    f"{position}. #{name} — {channel['message_count']} mensagens "
                    f"de {channel['unique_authors']} pessoas"
                )
        else:
            lines.append("nenhum canal com atividade no período")

        lines += ["", "Mensagens por dia:"]
        for day in self.timeline:
            lines.append(f"{day['day']}: {day['message_count']}")

        if self.authors:
            lines += ["", f"Participação concentrada: {len(self.authors)} membros no topo da lista"]
            for position, author in enumerate(self.authors, start=1):
                lines.append(
                    f"{position}. membro {author['author_id']} — {author['message_count']} mensagens"
                )
        return "\n".join(lines)


async def build_report(guild_id: int | str, days: int = 7) -> ActivityReport:
    guild_id = str(guild_id)
    db = await get_db()
    return ActivityReport(
        guild_id=guild_id,
        days=days,
        metrics=await guild_metrics(db, guild_id),
        channels=await top_channels(db, guild_id, limit=5, days=days),
        authors=await top_authors(db, guild_id, limit=3, days=days),
        timeline=await daily_timeline(db, guild_id, days=days),
    )
