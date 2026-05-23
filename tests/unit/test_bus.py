"""Tests for the Event Bus."""

from __future__ import annotations

import asyncio

import pytest

from agentos.kernel.events import Event, EventBus


class TestEventBus:
    @pytest.mark.asyncio
    async def test_publish_and_subscribe(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        await bus.subscribe("test.topic", handler)
        await bus.publish(Event(topic="test.topic", data="hello"))

        await asyncio.sleep(0.1)
        assert len(received) == 1
        assert received[0].data == "hello"

        await bus.stop()

    @pytest.mark.asyncio
    async def test_wildcard_subscription(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        await bus.subscribe("agent.*", handler)
        await bus.publish(Event(topic="agent.created", data="a1"))
        await bus.publish(Event(topic="agent.started", data="a1"))
        await bus.publish(Event(topic="workflow.started", data="w1"))  # Should NOT match

        await asyncio.sleep(0.1)
        assert len(received) == 2

        await bus.stop()

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self) -> None:
        bus = EventBus()
        await bus.start()
        received_a: list[Event] = []
        received_b: list[Event] = []

        async def handler_a(event: Event) -> None:
            received_a.append(event)

        async def handler_b(event: Event) -> None:
            received_b.append(event)

        await bus.subscribe("test.*", handler_a)
        await bus.subscribe("test.*", handler_b)

        count = await bus.publish(Event(topic="test.event"))
        assert count == 2

        await asyncio.sleep(0.1)
        assert len(received_a) == 1
        assert len(received_b) == 1

        await bus.stop()

    @pytest.mark.asyncio
    async def test_unsubscribe(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        sub_id = await bus.subscribe("test.*", handler)
        await bus.publish(Event(topic="test.event"))
        await asyncio.sleep(0.1)
        assert len(received) == 1

        await bus.unsubscribe(sub_id)
        await bus.publish(Event(topic="test.event"))
        await asyncio.sleep(0.1)
        assert len(received) == 1  # No new events

        assert bus.subscriber_count == 0
        await bus.stop()

    @pytest.mark.asyncio
    async def test_publish_when_stopped_returns_zero(self) -> None:
        bus = EventBus()
        # Not started
        count = await bus.publish(Event(topic="test.event"))
        assert count == 0

    @pytest.mark.asyncio
    async def test_event_has_id_and_timestamp(self) -> None:
        event = Event(topic="test", data="hello")
        assert event.event_id  # UUID string
        assert event.timestamp > 0

    @pytest.mark.asyncio
    async def test_handler_error_does_not_crash_bus(self) -> None:
        bus = EventBus()
        await bus.start()
        received: list[Event] = []

        async def bad_handler(event: Event) -> None:
            raise ValueError("boom")

        async def good_handler(event: Event) -> None:
            received.append(event)

        await bus.subscribe("test.*", bad_handler)
        await bus.subscribe("test.*", good_handler)

        await bus.publish(Event(topic="test.event"))
        await asyncio.sleep(0.2)

        # Good handler still received the event despite bad handler crashing
        assert len(received) == 1

        await bus.stop()
