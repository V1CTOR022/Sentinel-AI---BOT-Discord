"""Gravação de atividade em lote.

O on_message é caminho quente: um INSERT com commit por mensagem trava o
banco em servidor movimentado. Aqui a mensagem entra em uma lista na memória
e o flush acontece a cada poucos segundos, ou quando o buffer enche.
"""

from __future__ import annotations

import asyncio
import logging

from core.database import get_db
from core.stats import utc_now

logger = logging.getLogger(__name__)

INSERT = """
INSERT INTO activity_events (guild_id, channel_id, channel_name, author_id, event_type, created_at)
VALUES (?, ?, ?, ?, ?, ?)
"""


class ActivityRecorder:
    def __init__(self, flush_interval: float = 5.0, max_buffer: int = 500):
        self.flush_interval = flush_interval
        self.max_buffer = max_buffer
        self._buffer: list[tuple] = []
        self._task: asyncio.Task | None = None
        self._wake = asyncio.Event()

    def record(
        self,
        guild_id: int,
        channel_id: int,
        author_id: int,
        channel_name: str | None = None,
        event_type: str = "message",
    ) -> None:
        """Só metadados: nada do conteúdo da mensagem entra aqui."""
        self._buffer.append(
            (
                str(guild_id),
                str(channel_id),
                channel_name,
                str(author_id),
                event_type,
                utc_now().isoformat(timespec="seconds"),
            )
        )
        if len(self._buffer) >= self.max_buffer:
            self._wake.set()

    async def flush(self) -> int:
        if not self._buffer:
            return 0
        pending, self._buffer = self._buffer, []
        try:
            db = await get_db()
            await db.executemany(INSERT, pending)
            await db.commit()
        except Exception:
            # Devolve os eventos ao buffer para tentar de novo no próximo ciclo.
            self._buffer = pending + self._buffer
            raise
        return len(pending)

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="activity-flush")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        try:
            await self.flush()
        except Exception:
            logger.exception("Perdi eventos de atividade no encerramento.")

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self.flush_interval)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()
            try:
                await self.flush()
            except Exception:
                logger.exception("Falha ao gravar atividade; tentando no próximo ciclo.")
