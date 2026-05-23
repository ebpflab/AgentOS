"""Tests for the Lifecycle Manager."""

from __future__ import annotations

import pytest

from agentos.kernel.events import Event, EventBus
from agentos.kernel.lifecycle import LifecycleError, LifecycleManager
from agentos.kernel.registry import AgentMetadata, AgentRegistry, AgentRegistryError, AgentStatus


@pytest.fixture
async def setup():
    """Create lifecycle manager with dependencies."""
    registry = AgentRegistry(max_agents=10)
    bus = EventBus()
    await bus.start()

    # Register a test agent
    meta = AgentMetadata(agent_id="test-agent", name="TestAgent")
    registry.register(meta)

    manager = LifecycleManager(registry, bus)
    yield manager, registry, bus

    await bus.stop()


class TestLifecycleManager:
    @pytest.mark.asyncio
    async def test_start_agent(self, setup) -> None:
        manager, registry, bus = await setup.__anext__() if hasattr(setup, '__anext__') else setup
        result = await manager.start_agent("test-agent")
        assert result.status == AgentStatus.RUNNING

    @pytest.mark.asyncio
    async def test_stop_agent(self) -> None:
        registry = AgentRegistry(max_agents=10)
        bus = EventBus()
        await bus.start()
        registry.register(AgentMetadata(agent_id="a1", name="Agent1"))
        manager = LifecycleManager(registry, bus)

        await manager.start_agent("a1")
        assert registry.get("a1").status == AgentStatus.RUNNING

        await manager.stop_agent("a1")
        assert registry.get("a1").status == AgentStatus.STOPPED

        await bus.stop()

    @pytest.mark.asyncio
    async def test_invalid_transition_raises(self) -> None:
        registry = AgentRegistry(max_agents=10)
        bus = EventBus()
        await bus.start()
        registry.register(AgentMetadata(agent_id="a1", name="Agent1"))
        manager = LifecycleManager(registry, bus)

        # Can't stop an agent that isn't running
        with pytest.raises(LifecycleError, match="Invalid transition"):
            await manager.stop_agent("a1")

        await bus.stop()

    @pytest.mark.asyncio
    async def test_nonexistent_agent_raises(self) -> None:
        registry = AgentRegistry(max_agents=10)
        bus = EventBus()
        await bus.start()
        manager = LifecycleManager(registry, bus)

        with pytest.raises(AgentRegistryError, match="not found"):
            await manager.start_agent("nonexistent")

        await bus.stop()

    @pytest.mark.asyncio
    async def test_restart_running_agent(self) -> None:
        registry = AgentRegistry(max_agents=10)
        bus = EventBus()
        await bus.start()
        registry.register(AgentMetadata(agent_id="a1", name="Agent1"))
        manager = LifecycleManager(registry, bus)

        await manager.start_agent("a1")
        assert registry.get("a1").status == AgentStatus.RUNNING

        await manager.restart_agent("a1")
        assert registry.get("a1").status == AgentStatus.RUNNING

        await bus.stop()

    @pytest.mark.asyncio
    async def test_mark_error(self) -> None:
        registry = AgentRegistry(max_agents=10)
        bus = EventBus()
        await bus.start()
        registry.register(AgentMetadata(agent_id="a1", name="Agent1"))
        manager = LifecycleManager(registry, bus)

        await manager.start_agent("a1")
        await manager.mark_error("a1", error="Connection timeout")

        meta = registry.get("a1")
        assert meta.status == AgentStatus.ERROR
        assert meta.extra["last_error"] == "Connection timeout"

        await bus.stop()

    @pytest.mark.asyncio
    async def test_lifecycle_events_published(self) -> None:
        registry = AgentRegistry(max_agents=10)
        bus = EventBus()
        await bus.start()
        registry.register(AgentMetadata(agent_id="a1", name="Agent1"))
        manager = LifecycleManager(registry, bus)

        received_events: list[Event] = []

        async def handler(event: Event) -> None:
            received_events.append(event)

        await bus.subscribe("agent.*", handler)

        await manager.start_agent("a1")

        # Give event consumers time to process
        import asyncio
        await asyncio.sleep(0.1)

        assert len(received_events) == 2  # STARTING + RUNNING
        assert received_events[0].topic == "agent.starting"
        assert received_events[1].topic == "agent.running"

        await bus.stop()

    @pytest.mark.asyncio
    async def test_start_from_stopped(self) -> None:
        registry = AgentRegistry(max_agents=10)
        bus = EventBus()
        await bus.start()
        registry.register(AgentMetadata(agent_id="a1", name="Agent1"))
        manager = LifecycleManager(registry, bus)

        await manager.start_agent("a1")
        await manager.stop_agent("a1")
        assert registry.get("a1").status == AgentStatus.STOPPED

        # Restart from stopped
        await manager.start_agent("a1")
        assert registry.get("a1").status == AgentStatus.RUNNING

        await bus.stop()

    @pytest.mark.asyncio
    async def test_get_status(self) -> None:
        registry = AgentRegistry(max_agents=10)
        bus = EventBus()
        await bus.start()
        registry.register(AgentMetadata(agent_id="a1", name="Agent1"))
        manager = LifecycleManager(registry, bus)

        assert manager.get_status("a1") == AgentStatus.CREATED
        assert manager.get_status("nonexistent") is None

        await bus.stop()
