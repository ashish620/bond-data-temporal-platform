"""
Day 4 — Async in-process event bus.

Simple pub/sub backed by asyncio.Queue.  All subscribers receive every event
published while the bus is running.  The singleton `event_bus` is used by the
ingestor (publisher) and the reconciliation handler (subscriber).
"""

import asyncio
import logging
from typing import Callable

from day4.models import ReconciliationEvent

logger = logging.getLogger(__name__)


class EventBus:
    """
    Async in-process publish/subscribe bus for ReconciliationEvent messages.

    Usage::

        event_bus.subscribe(my_handler)
        await event_bus.start()        # begin processing loop
        await event_bus.publish(event) # enqueue an event
        await event_bus.stop()         # drain and stop
    """

    def __init__(self) -> None:
        # Queue is created lazily in start() so it always binds to the
        # correct running event loop (important in test environments).
        self._queue: asyncio.Queue | None = None
        self._subscribers: list[Callable] = []
        self._task: asyncio.Task | None = None

    def subscribe(self, handler: Callable) -> None:
        """Register an async handler.  Called before start()."""
        self._subscribers.append(handler)

    async def publish(self, event: ReconciliationEvent) -> None:
        """Enqueue an event — all subscribers will receive it."""
        if self._queue is None:
            # Bus not started yet — start it implicitly so that tests and
            # standalone usage work without an explicit start() call.
            await self.start()
        await self._queue.put(event)
        logger.debug("EventBus: published event %s for ISIN %s", event.event_id, event.isin)

    async def _process_loop(self) -> None:
        """Background task: dequeue events and fan them out to all subscribers."""
        while True:
            item = await self._queue.get()
            if item is None:
                # Sentinel: drain remaining items then exit
                self._queue.task_done()
                break
            try:
                await asyncio.gather(*(handler(item) for handler in self._subscribers))
            except asyncio.CancelledError:
                self._queue.task_done()
                raise
            except Exception:  # noqa: BLE001
                logger.exception("EventBus: subscriber raised an exception for event %s", item.event_id)
            finally:
                self._queue.task_done()

    async def start(self) -> None:
        """Start the background processing loop."""
        if self._task is None or self._task.done():
            # Always create a fresh queue bound to the current event loop
            self._queue = asyncio.Queue()
            self._task = asyncio.ensure_future(self._process_loop())
            logger.info("EventBus: started")

    async def stop(self) -> None:
        """Send a sentinel, wait for the queue to drain, then cancel the task."""
        if self._queue is None or self._task is None or self._task.done():
            logger.info("EventBus: already stopped or never started")
            return
        await self._queue.put(None)
        try:
            await asyncio.wait_for(self._task, timeout=10.0)
        except asyncio.TimeoutError:
            self._task.cancel()
        finally:
            self._queue = None
            self._task = None
        logger.info("EventBus: stopped")


# Singleton used across the application
event_bus = EventBus()
