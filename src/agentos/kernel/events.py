"""Async event bus for internal pub/sub communication.

Topic-based routing with asyncio.Queue per subscriber.
Topics use dot-notation: 'agent.created', 'agent.started', 'workflow.completed', etc.
Supports wildcard subscriptions: 'agent.*' matches all agent events.
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine
from uuid import uuid4

logger = logging.getLogger(__name__)

EventHandler = Callable[["Event"], Coroutine[Any, Any, None]]


@dataclass
class Event:
    """An event published on the event bus."""

    topic: str
    data: Any = None
    timestamp: float = field(default_factory=time.time)
    source: str = ""
    event_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class _Subscription:
    """Internal subscription record."""

    subscriber_id: str
    pattern: str  # Topic pattern (supports wildcards like 'agent.*')
    handler: EventHandler
    queue: asyncio.Queue[Event] = field(default_factory=lambda: asyncio.Queue(maxsize=1000))


class EventBus:
    """Async event bus with topic-based pub/sub.

    Usage:
        bus = EventBus()
        await bus.start()

        # Subscribe with handler
        sub_id = await bus.subscribe("agent.*", my_handler)

        # Publish events
        await bus.publish(Event(topic="agent.created", data={"agent_id": "abc"}))

        # Cleanup
        await bus.unsubscribe(sub_id)
        await bus.stop()
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, _Subscription] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False

    async def start(self) -> None:
        """Start the event bus."""
        self._running = True
        logger.info("Event bus started")

    async def stop(self) -> None:
        """Stop the event bus and cancel all consumer tasks."""
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        self._subscriptions.clear()
        logger.info("Event bus stopped")

    async def subscribe(self, pattern: str, handler: EventHandler) -> str:
        """Subscribe to events matching a topic pattern.

        Args:
            pattern: Topic pattern (e.g., 'agent.created', 'agent.*', '*').
            handler: Async callback invoked for each matching event.

        Returns:
            Subscriber ID for unsubscribing.
        """
        sub_id = str(uuid4())
        sub = _Subscription(subscriber_id=sub_id, pattern=pattern, handler=handler)
        self._subscriptions[sub_id] = sub

        # Start consumer task for this subscriber
        task = asyncio.create_task(self._consume(sub), name=f"event-consumer-{sub_id[:8]}")
        self._tasks[sub_id] = task

        logger.debug("Subscribed %s to pattern '%s'", sub_id[:8], pattern)
        return sub_id

    async def unsubscribe(self, subscriber_id: str) -> None:
        """Remove a subscription."""
        if subscriber_id in self._tasks:
            self._tasks[subscriber_id].cancel()
            del self._tasks[subscriber_id]
        self._subscriptions.pop(subscriber_id, None)
        logger.debug("Unsubscribed %s", subscriber_id[:8])

    async def publish(self, event: Event) -> int:
        """Publish an event to all matching subscribers.

        Args:
            event: The event to publish.

        Returns:
            Number of subscribers that received the event.
        """
        if not self._running:
            logger.warning("Event bus not running, dropping event: %s", event.topic)
            return 0

        matched = 0
        for sub in self._subscriptions.values():
            if fnmatch.fnmatch(event.topic, sub.pattern):
                try:
                    sub.queue.put_nowait(event)
                    matched += 1
                except asyncio.QueueFull:
                    logger.warning(
                        "Queue full for subscriber %s, dropping event %s",
                        sub.subscriber_id[:8],
                        event.topic,
                    )
        return matched

    async def _consume(self, sub: _Subscription) -> None:
        """Consumer loop: reads events from subscriber queue and calls handler."""
        while self._running:
            try:
                event = await asyncio.wait_for(sub.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            try:
                await sub.handler(event)
            except Exception:
                logger.exception(
                    "Error in event handler for subscriber %s, topic %s",
                    sub.subscriber_id[:8],
                    event.topic,
                )

    @property
    def subscriber_count(self) -> int:
        return len(self._subscriptions)

    @property
    def is_running(self) -> bool:
        return self._running
