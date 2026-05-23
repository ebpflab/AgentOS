"""Agent Lifecycle Manager — state machine for agent lifecycle.

Manages agent state transitions: CREATED → STARTING → RUNNING → STOPPING → STOPPED.
Integrates with the event bus to publish lifecycle events.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agentos.kernel.events import Event, EventBus
from agentos.kernel.registry import AgentMetadata, AgentRegistry, AgentRegistryError, AgentStatus

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Valid state transitions
_TRANSITIONS: dict[AgentStatus, set[AgentStatus]] = {
    AgentStatus.CREATED: {AgentStatus.STARTING, AgentStatus.ERROR},
    AgentStatus.STARTING: {AgentStatus.RUNNING, AgentStatus.ERROR},
    AgentStatus.RUNNING: {AgentStatus.STOPPING, AgentStatus.ERROR},
    AgentStatus.STOPPING: {AgentStatus.STOPPED, AgentStatus.ERROR},
    AgentStatus.STOPPED: {AgentStatus.STARTING},  # Allow restart
    AgentStatus.ERROR: {AgentStatus.STARTING, AgentStatus.STOPPED},  # Allow recovery or cleanup
}


class LifecycleError(Exception):
    """Raised for invalid lifecycle transitions."""


class LifecycleManager:
    """Manages agent lifecycle state transitions and publishes events.

    Usage:
        manager = LifecycleManager(registry, event_bus)
        await manager.start_agent("agent-id")
        await manager.stop_agent("agent-id")
    """

    def __init__(self, registry: AgentRegistry, event_bus: EventBus) -> None:
        self._registry = registry
        self._event_bus = event_bus

    def _validate_transition(self, agent_id: str, target: AgentStatus) -> AgentMetadata:
        """Validate a state transition is allowed."""
        metadata = self._registry.get(agent_id)
        if metadata is None:
            raise AgentRegistryError(f"Agent not found: {agent_id}")

        current = metadata.status
        allowed = _TRANSITIONS.get(current, set())
        if target not in allowed:
            raise LifecycleError(
                f"Invalid transition for agent '{metadata.name}': {current.value} → {target.value}. "
                f"Allowed: {', '.join(s.value for s in allowed)}"
            )
        return metadata

    async def _transition(self, agent_id: str, target: AgentStatus) -> AgentMetadata:
        """Execute a state transition and publish event."""
        metadata = self._validate_transition(agent_id, target)
        previous = metadata.status
        self._registry.update_status(agent_id, target)

        await self._event_bus.publish(Event(
            topic=f"agent.{target.value}",
            data={
                "agent_id": agent_id,
                "name": metadata.name,
                "previous_status": previous.value,
                "new_status": target.value,
            },
            source="lifecycle_manager",
        ))

        logger.info(
            "Agent '%s' (%s): %s → %s",
            metadata.name, agent_id[:8], previous.value, target.value,
        )
        return metadata

    async def start_agent(self, agent_id: str) -> AgentMetadata:
        """Start an agent (CREATED/STOPPED/ERROR → STARTING → RUNNING).

        Performs the two-step transition: first to STARTING, then to RUNNING.
        In a full implementation, the STARTING state would involve initializing
        the agent's MAF resources before transitioning to RUNNING.
        """
        await self._transition(agent_id, AgentStatus.STARTING)
        # In production, agent initialization happens here (connect to LLM, load tools, etc.)
        return await self._transition(agent_id, AgentStatus.RUNNING)

    async def stop_agent(self, agent_id: str) -> AgentMetadata:
        """Stop an agent (RUNNING → STOPPING → STOPPED)."""
        await self._transition(agent_id, AgentStatus.STOPPING)
        # In production, graceful shutdown happens here (finish current task, cleanup)
        return await self._transition(agent_id, AgentStatus.STOPPED)

    async def mark_error(self, agent_id: str, error: str = "") -> AgentMetadata:
        """Transition agent to ERROR state."""
        metadata = self._validate_transition(agent_id, AgentStatus.ERROR)
        metadata.extra["last_error"] = error
        return await self._transition(agent_id, AgentStatus.ERROR)

    async def restart_agent(self, agent_id: str) -> AgentMetadata:
        """Restart an agent: stop (if running) then start."""
        metadata = self._registry.get(agent_id)
        if metadata is None:
            raise AgentRegistryError(f"Agent not found: {agent_id}")

        if metadata.status == AgentStatus.RUNNING:
            await self.stop_agent(agent_id)

        return await self.start_agent(agent_id)

    def get_status(self, agent_id: str) -> AgentStatus | None:
        """Get current agent status."""
        metadata = self._registry.get(agent_id)
        return metadata.status if metadata else None
