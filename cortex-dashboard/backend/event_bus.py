"""
event_bus.py — in-memory pub/sub for dashboard events.

Lightweight publish/subscribe primitive used by /api/stream/events to push
real-time updates (incidents, runs, jobs, gate decisions) to the frontend
over Server-Sent Events.

Why not Kafka or Redis Streams here:
  * Single-instance FastAPI backend, no horizontal scaling
  * No durability requirement (events are derived from JSON files / SSH polls)
  * Sensor must be able to clone-and-run without extra infrastructure

If a future iteration needs cross-process durability, swap the asyncio.Queue
fan-out below for an aioredis.Redis().xadd() / .xread() implementation. The
publish() / subscribe() contract stays identical.

Producer side  -> bus.publish(event_type, payload)
Consumer side  -> async for event in bus.subscribe(): ...
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, AsyncGenerator


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventBus:
    """
    Fan-out queue. Each subscriber gets its own asyncio.Queue; publish()
    enqueues into all live queues. A small ring buffer of recent events
    lets late subscribers backfill the last N seconds of history.
    """

    def __init__(self, history_size: int = 50) -> None:
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        self._history: deque[dict[str, Any]] = deque(maxlen=history_size)
        self._seq: int = 0
        self._lock = asyncio.Lock()

    def publish(self, kind: str, payload: dict[str, Any]) -> None:
        """
        Enqueue an event for every active subscriber. Safe to call from
        synchronous request handlers — uses non-blocking put_nowait. If a
        subscriber's queue is full, drop the event for that subscriber
        rather than blocking the publisher.
        """
        self._seq += 1
        event = {
            "seq":      self._seq,
            "ts":       _now_iso(),
            "kind":     kind,
            "payload":  payload,
        }
        self._history.append(event)
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Slow consumer; drop this event for them rather than block
                pass

    async def subscribe(
        self,
        replay_from_seq: int | None = None,
        ping_interval: float = 15.0,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Yield events to one subscriber. If replay_from_seq is provided, first
        replay any cached events newer than that seq, then stream live.
        A periodic ping keeps proxies from closing idle connections.
        """
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers.append(queue)

        try:
            # Backfill from ring buffer
            if replay_from_seq is not None:
                for e in list(self._history):
                    if e["seq"] > replay_from_seq:
                        yield e

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=ping_interval)
                    yield event
                except asyncio.TimeoutError:
                    yield {"kind": "ping", "ts": _now_iso(), "seq": -1, "payload": {}}
        finally:
            async with self._lock:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def last_seq(self) -> int:
        return self._seq

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        return list(self._history)[-n:]


def to_sse_frame(event: dict[str, Any]) -> str:
    """Serialise an event in the Server-Sent Events wire format."""
    data = json.dumps(event, separators=(",", ":"))
    return f"event: {event.get('kind', 'message')}\ndata: {data}\nid: {event.get('seq', 0)}\n\n"


# Module-level singleton — imported by server.py
bus = EventBus()
