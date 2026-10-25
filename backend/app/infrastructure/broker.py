from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator


class StatusBroker:
    """Best-effort bounded status fan-out; REST state remains authoritative."""

    def __init__(self, queue_size: int = 100) -> None:
        self.queue_size = queue_size
        self._subscribers: dict[str, set[asyncio.Queue[dict]]] = defaultdict(set)
        self._sequences: dict[str, int] = defaultdict(int)

    async def publish(
        self,
        mission_id: str,
        message_type: str,
        *,
        operation_id: str | None = None,
        stage: str | None = None,
        payload: dict | None = None,
    ) -> dict:
        self._sequences[mission_id] += 1
        message = {
            "type": message_type,
            "mission_id": mission_id,
            "operation_id": operation_id,
            "sequence": self._sequences[mission_id],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "contract_version": "provisional-v1",
            "stage": stage,
            "payload": payload or {},
        }
        for queue in tuple(self._subscribers.get(mission_id, ())):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(message)
        return message

    @asynccontextmanager
    async def subscribe(self, mission_id: str) -> AsyncIterator[asyncio.Queue[dict]]:
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=self.queue_size)
        self._subscribers[mission_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[mission_id].discard(queue)
            if not self._subscribers[mission_id]:
                self._subscribers.pop(mission_id, None)
