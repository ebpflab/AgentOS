"""Supervisor Agent — monitors child agents and auto-recovers on failure.

Subscribes to agent lifecycle events and restarts failed agents.
Tracks health status and escalates persistent failures.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from agentos.kernel.events import Event, EventBus
from agentos.kernel.lifecycle import LifecycleManager
from agentos.kernel.registry import AgentRegistry, AgentStatus

logger = logging.getLogger(__name__)


@dataclass
class AgentHealthRecord:
    """Tracks health status and failure history for an agent."""

    agent_id: str
    restart_count: int = 0
    max_restarts: int = 3
    last_error: str = ""
    is_supervised: bool = True


class SupervisorAgent:
    """Monitors agents and auto-restarts on failure.

    Features:
    - Subscribes to agent.error events
    - Auto-restarts failed agents (up to max_restarts)
    - Escalates persistent failures
    - Periodic health checks

    Usage:
        supervisor = SupervisorAgent(registry, lifecycle, event_bus)
        await supervisor.start()
        supervisor.supervise("agent-1")
    """

    def __init__(
        self,
        registry: AgentRegistry,
        lifecycle: LifecycleManager,
        event_bus: EventBus,
        max_restarts: int = 3,
    ) -> None:
        self._registry = registry
        self._lifecycle = lifecycle
        self._event_bus = event_bus
        self._max_restarts = max_restarts
        self._health_records: dict[str, AgentHealthRecord] = {}
        self._subscription_id: str | None = None
        self._running = False

    async def start(self) -> None:
        """Start supervising agents."""
        self._running = True
        self._subscription_id = await self._event_bus.subscribe(
            "agent.error", self._handle_agent_error
        )
        logger.info("Supervisor started (max_restarts=%d)", self._max_restarts)

    async def stop(self) -> None:
        """Stop supervising."""
        self._running = False
        if self._subscription_id:
            await self._event_bus.unsubscribe(self._subscription_id)
            self._subscription_id = None
        logger.info("Supervisor stopped")

    def supervise(self, agent_id: str, max_restarts: int | None = None) -> None:
        """Add an agent to supervision.

        Args:
            agent_id: Agent to supervise.
            max_restarts: Override default max restart count.
        """
        self._health_records[agent_id] = AgentHealthRecord(
            agent_id=agent_id,
            max_restarts=max_restarts or self._max_restarts,
        )
        logger.info("Supervising agent %s", agent_id[:8])

    def unsupervise(self, agent_id: str) -> None:
        """Remove an agent from supervision."""
        self._health_records.pop(agent_id, None)

    async def _handle_agent_error(self, event: Event) -> None:
        """Handle agent error events — attempt restart if supervised."""
        if not isinstance(event.data, dict):
            return

        agent_id = event.data.get("agent_id", "")
        record = self._health_records.get(agent_id)

        if record is None or not record.is_supervised:
            return

        error_msg = event.data.get("previous_status", "unknown error")
        record.last_error = error_msg
        record.restart_count += 1

        if record.restart_count > record.max_restarts:
            logger.error(
                "Agent %s exceeded max restarts (%d). Escalating.",
                agent_id[:8], record.max_restarts,
            )
            record.is_supervised = False
            await self._event_bus.publish(Event(
                topic="supervisor.escalation",
                data={
                    "agent_id": agent_id,
                    "restart_count": record.restart_count,
                    "last_error": record.last_error,
                },
                source="supervisor",
            ))
            return

        logger.warning(
            "Agent %s failed (attempt %d/%d). Restarting...",
            agent_id[:8], record.restart_count, record.max_restarts,
        )

        try:
            await self._lifecycle.restart_agent(agent_id)
            await self._event_bus.publish(Event(
                topic="supervisor.restarted",
                data={
                    "agent_id": agent_id,
                    "restart_count": record.restart_count,
                },
                source="supervisor",
            ))
        except Exception:
            logger.exception("Failed to restart agent %s", agent_id[:8])

    def get_health(self, agent_id: str) -> AgentHealthRecord | None:
        """Get health record for a supervised agent."""
        return self._health_records.get(agent_id)

    def list_supervised(self) -> list[AgentHealthRecord]:
        """List all supervised agents and their health."""
        return list(self._health_records.values())

    @property
    def supervised_count(self) -> int:
        return len(self._health_records)
