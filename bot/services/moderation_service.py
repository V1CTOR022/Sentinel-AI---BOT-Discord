"""Detecção de flood.

Contador em memória por (servidor, usuário). O bot apenas avisa a moderação:
punir automaticamente com base em uma janela de poucos segundos gera mais
falso positivo do que ajuda.
"""

from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic


class FloodDetector:
    def __init__(self, limit: int = 6, window_seconds: int = 8):
        self.limit = limit
        self.window_seconds = window_seconds
        self._messages: defaultdict[tuple[int, int], deque[float]] = defaultdict(deque)
        self._last_alert: dict[tuple[int, int], float] = {}

    def check(self, guild_id: int, user_id: int) -> bool:
        """True quando vale alertar a moderação sobre esse usuário."""
        now = monotonic()
        key = (guild_id, user_id)

        timestamps = self._messages[key]
        while timestamps and now - timestamps[0] > self.window_seconds:
            timestamps.popleft()
        timestamps.append(now)

        self._forget_idle(now)

        if len(timestamps) < self.limit:
            return False
        if now - self._last_alert.get(key, 0.0) < self.window_seconds:
            return False

        self._last_alert[key] = now
        return True

    def _forget_idle(self, now: float) -> None:
        """Sem isso o dicionário guarda para sempre todo mundo que já falou."""
        cutoff = now - self.window_seconds
        idle = [
            key
            for key, timestamps in self._messages.items()
            if not timestamps or timestamps[-1] < cutoff
        ]
        for key in idle:
            del self._messages[key]
            alerted = self._last_alert.get(key)
            if alerted is None or now - alerted > self.window_seconds * 10:
                self._last_alert.pop(key, None)

    @property
    def tracked_users(self) -> int:
        return len(self._messages)
