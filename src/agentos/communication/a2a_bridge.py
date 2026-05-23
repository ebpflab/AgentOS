"""A2A Protocol Bridge — bridges internal message bus to MAF A2A protocol.

Translates between AgentOS internal AgentMessage format and the MAF A2A
protocol for communication with remote agents.
"""

from __future__ import annotations

import logging
from typing import Any

from agentos.communication.bus import MessageBus
from agentos.communication.protocols import AgentMessage, MessageType
from agentos.kernel.events import Event, EventBus
from agentos.kernel.registry import AgentMetadata, AgentRegistry

logger = logging.getLogger(__name__)


class RemoteAgentInfo:
    """Information about a remote agent discovered via A2A."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        url: str,
        capabilities: list[str] | None = None,
        description: str = "",
    ) -> None:
        self.agent_id = agent_id
        self.name = name
        self.url = url
        self.capabilities = capabilities or []
        self.description = description


class A2ABridge:
    """Bridges internal message bus with MAF A2A protocol for remote agents.

    Responsibilities:
    - Discover remote agents via A2A agent cards
    - Register remote agents as proxies in the local registry
    - Route messages to remote agents via A2A protocol
    - Receive messages from remote agents and deliver to local agents

    Usage:
        bridge = A2ABridge(message_bus, registry, event_bus)
        await bridge.start()
        await bridge.register_remote_agent(RemoteAgentInfo(
            agent_id="remote-1", name="RemoteHelper", url="http://remote:8080/a2a"
        ))
    """

    def __init__(
        self,
        message_bus: MessageBus,
        registry: AgentRegistry,
        event_bus: EventBus,
    ) -> None:
        self._bus = message_bus
        self._registry = registry
        self._event_bus = event_bus
        self._remote_agents: dict[str, RemoteAgentInfo] = {}
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("A2A bridge started")

    async def stop(self) -> None:
        self._running = False
        self._remote_agents.clear()
        logger.info("A2A bridge stopped")

    async def register_remote_agent(self, info: RemoteAgentInfo) -> None:
        """Register a remote agent as a proxy in the local system.

        The remote agent appears in the registry and can receive messages
        via the message bus — the bridge handles A2A transport.
        """
        self._remote_agents[info.agent_id] = info

        # Register in local registry so it's discoverable
        metadata = AgentMetadata(
            agent_id=info.agent_id,
            name=info.name,
            description=info.description,
            capabilities=info.capabilities,
            tags={"remote": "true", "a2a_url": info.url},
        )
        self._registry.register(metadata)

        # Register on message bus with a handler that forwards to A2A
        async def _forward_handler(message: AgentMessage) -> None:
            await self._send_to_remote(info, message)

        await self._bus.register_agent(info.agent_id, handler=_forward_handler)

        await self._event_bus.publish(Event(
            topic="a2a.agent_registered",
            data={"agent_id": info.agent_id, "name": info.name, "url": info.url},
            source="a2a_bridge",
        ))

        logger.info("Registered remote agent '%s' at %s", info.name, info.url)

    async def unregister_remote_agent(self, agent_id: str) -> None:
        """Remove a remote agent proxy."""
        self._remote_agents.pop(agent_id, None)
        await self._bus.unregister_agent(agent_id)
        self._registry.unregister(agent_id)

    async def _send_to_remote(self, info: RemoteAgentInfo, message: AgentMessage) -> None:
        """Send a message to a remote agent via A2A protocol.

        In a full implementation, this uses MAF's agent-framework-a2a package
        to send the message via the A2A protocol (HTTP + SSE).
        """
        try:
            # TODO: Integrate with MAF A2A client
            # from agent_framework.a2a import A2AAgent
            # remote = A2AAgent(url=info.url)
            # response = await remote.run(message.content)

            logger.info(
                "A2A send: %s → %s (%s): %s",
                message.sender[:8] if message.sender else "?",
                info.name,
                info.url,
                message.content[:50],
            )

            await self._event_bus.publish(Event(
                topic="a2a.message_sent",
                data={
                    "sender": message.sender,
                    "receiver": info.agent_id,
                    "url": info.url,
                },
                source="a2a_bridge",
            ))

        except Exception:
            logger.exception("Failed to send A2A message to %s", info.url)
            await self._event_bus.publish(Event(
                topic="a2a.error",
                data={"agent_id": info.agent_id, "url": info.url},
                source="a2a_bridge",
            ))

    async def receive_from_remote(
        self,
        source_agent_id: str,
        target_agent_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Handle an incoming message from a remote agent via A2A.

        Called by the A2A server endpoint when a remote agent sends a message.
        """
        message = AgentMessage(
            content=content,
            sender=source_agent_id,
            receiver=target_agent_id,
            message_type=MessageType.REQUEST,
            metadata=metadata or {},
        )
        return await self._bus.send(message)

    def list_remote_agents(self) -> list[RemoteAgentInfo]:
        return list(self._remote_agents.values())

    @property
    def remote_agent_count(self) -> int:
        return len(self._remote_agents)
