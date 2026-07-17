"""Cola de render con rate limits (directiva Nico M11, como TokenBudget en M5).

Techo global (`RENDER_MAX_CONCURRENCY`) + techo por cliente
(`RENDER_MAX_PER_CLIENT`): un cliente no monopoliza la cola. FIFO natural de
asyncio; el caller marca `queued` antes de pedir slot y `rendering` al obtenerlo.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager


class RenderQueue:
    def __init__(self, max_concurrency: int, max_per_client: int) -> None:
        if max_concurrency < 1 or max_per_client < 1:
            raise ValueError("los límites de la cola deben ser >= 1")
        self._global = asyncio.Semaphore(max_concurrency)
        self._max_per_client = max_per_client
        self._clients: dict[str, asyncio.Semaphore] = {}

    def _client_sem(self, client_id: str) -> asyncio.Semaphore:
        if client_id not in self._clients:
            self._clients[client_id] = asyncio.Semaphore(self._max_per_client)
        return self._clients[client_id]

    @asynccontextmanager
    async def slot(self, client_id: str):
        """Adquiere primero el cupo del cliente (no retiene cupo global esperando)."""
        client = self._client_sem(client_id)
        await client.acquire()
        try:
            await self._global.acquire()
            try:
                yield
            finally:
                self._global.release()
        finally:
            client.release()
