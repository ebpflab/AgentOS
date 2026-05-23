"""Router Agent — capability-based task dispatch.

A meta-agent that queries the registry to find the best agent for a task,
then delegates the task to that agent. Uses MAF's .as_tool() composition
to expose registered agents as tools.
"""

from __future__ import annotations

import logging
from typing import Any

from agentos.agents.base import ManagedAgent
from agentos.kernel.events import Event, EventBus
from agentos.kernel.registry import AgentRegistry, AgentStatus

logger = logging.getLogger(__name__)


class RouterAgent:
    """Routes tasks to the best available agent based on capabilities.

    The router maintains a mapping of capabilities to agents and can:
    - Auto-discover agents from the registry
    - Route by explicit capability match
    - Fall back to a default agent
    - Track routing decisions for analytics

    Usage:
        router = RouterAgent(registry, event_bus)
        result = await router.route("Review this Python code", capabilities=["code-review", "python"])
    """

    def __init__(
        self,
        registry: AgentRegistry,
        event_bus: EventBus | None = None,
        default_agent_id: str | None = None,
    ) -> None:
        self._registry = registry
        self._event_bus = event_bus
        self._default_agent_id = default_agent_id
        # Cache of agent_id -> ManagedAgent for fast access
        self._agent_cache: dict[str, ManagedAgent] = {}

    def register_agent(self, agent: ManagedAgent) -> None:
        """Register an agent for routing."""
        self._agent_cache[agent.agent_id] = agent

    async def route(
        self,
        message: str,
        capabilities: list[str] | None = None,
        tenant_id: str | None = None,
        prefer_agent: str | None = None,
    ) -> str:
        """Route a message to the best available agent.

        Args:
            message: The task/message to process.
            capabilities: Required capabilities (at least one must match).
            tenant_id: Restrict to agents in this tenant.
            prefer_agent: Preferred agent name (used if available).

        Returns:
            The agent's response.

        Raises:
            ValueError: If no suitable agent found.
        """
        agent = await self._find_best_agent(capabilities, tenant_id, prefer_agent)

        if agent is None:
            raise ValueError(
                f"No agent found for capabilities={capabilities}, tenant={tenant_id}"
            )

        await self._publish_event("router.dispatched", {
            "target_agent": agent.name,
            "agent_id": agent.agent_id,
            "capabilities": capabilities,
        })

        logger.info("Routing to agent '%s' (capabilities=%s)", agent.name, capabilities)

        try:
            result = await agent.run(message)
            await self._publish_event("router.completed", {
                "target_agent": agent.name,
                "agent_id": agent.agent_id,
            })
            return result
        except Exception as e:
            await self._publish_event("router.failed", {
                "target_agent": agent.name,
                "agent_id": agent.agent_id,
                "error": str(e),
            })
            raise

    async def _find_best_agent(
        self,
        capabilities: list[str] | None,
        tenant_id: str | None,
        prefer_agent: str | None,
    ) -> ManagedAgent | None:
        """Find the best agent matching the criteria."""
        # Try preferred agent first
        if prefer_agent:
            meta = self._registry.find_by_name(prefer_agent, tenant_id=tenant_id)
            if meta and meta.status == AgentStatus.RUNNING:
                cached = self._agent_cache.get(meta.agent_id)
                if cached:
                    return cached

        # Search by capabilities
        if capabilities:
            for cap in capabilities:
                candidates = self._registry.find_by_capability(cap, tenant_id=tenant_id)
                for meta in candidates:
                    if meta.status == AgentStatus.RUNNING:
                        cached = self._agent_cache.get(meta.agent_id)
                        if cached:
                            return cached

        # Fall back to default
        if self._default_agent_id:
            return self._agent_cache.get(self._default_agent_id)

        return None

    def get_routing_table(self, tenant_id: str | None = None) -> dict[str, list[str]]:
        """Get a capability → agent names mapping for debugging.

        Returns:
            Dict mapping capability strings to lists of agent names.
        """
        table: dict[str, list[str]] = {}
        agents = self._registry.list_agents(tenant_id=tenant_id)
        for meta in agents:
            for cap in meta.capabilities:
                if cap not in table:
                    table[cap] = []
                table[cap].append(meta.name)
        return table

    async def _publish_event(self, topic: str, data: Any) -> None:
        if self._event_bus:
            await self._event_bus.publish(Event(topic=topic, data=data, source="router"))
