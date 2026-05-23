"""Shared test fixtures for AgentOS tests."""

from __future__ import annotations

import asyncio

import pytest

from agentos.config import AgentOSConfig
from agentos.kernel.events import EventBus
from agentos.kernel.registry import AgentRegistry


@pytest.fixture
def config() -> AgentOSConfig:
    """Create a test configuration."""
    return AgentOSConfig()


@pytest.fixture
def registry() -> AgentRegistry:
    """Create a test registry."""
    return AgentRegistry(max_agents=10)


@pytest.fixture
async def event_bus() -> EventBus:
    """Create and start a test event bus."""
    bus = EventBus()
    await bus.start()
    yield bus
    await bus.stop()
