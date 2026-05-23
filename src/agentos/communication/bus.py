"""Message Bus — inter-agent communication layer.

Provides direct messaging, broadcast, and topic-based pub/sub for agents.
Bridges to the kernel EventBus for system-wide event distribution.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine
from uuid import uuid4

from agentos.communication.protocols import AgentMessage, MessageType
from agentos.kernel.events import Event, EventBus

logger = logging.getLogger(__name__)

MessageHandler = Callable[[AgentMessage], Coroutine[Any, Any, None]]


class MessageBus:
    """Inter-agent message bus with direct messaging, broadcast, and request-reply.

    Integrates with the kernel EventBus for system event distribution.

    Usage:
        bus = MessageBus(event_bus)
        await bus.start()

        # Register agent inbox
        inbox = await bus.register_agent("agent-1")

        # Send direct message
        await bus.send(AgentMessage(content="Hello", sender="agent-2", receiver="agent-1"))

        # Broadcast
        await bus.broadcast(AgentMessage(content="Alert", sender="system"))

        # Request-reply
        response = await bus.request("agent-1", AgentMessage(content="What's 2+2?", sender="agent-2"))
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        # agent_id -> asyncio.Queue for incoming messages
        self._inboxes: dict[str, asyncio.Queue[AgentMessage]] = {}
        # agent_id -> list of message handlers
        self._handlers: dict[str, list[MessageHandler]] = defaultdict(list)
        # correlation_id -> Future for request/reply pattern
        self._pending_replies: dict[str, asyncio.Future[AgentMessage]] = {}
        self._running = False
        self._consumer_tasks: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        self._running = True
        logger.info("Message bus started")

    async def stop(self) -> None:
        self._running = False
        for task in self._consumer_tasks.values():
            task.cancel()
        if self._consumer_tasks:
            await asyncio.gather(*self._consumer_tasks.values(), return_exceptions=True)
        self._consumer_tasks.clear()

        # Cancel pending replies
        for future in self._pending_replies.values():
            if not future.done():
                future.cancel()
        self._pending_replies.clear()

        self._inboxes.clear()
        self._handlers.clear()
        logger.info("Message bus stopped")

    async def register_agent(
        self,
        agent_id: str,
        handler: MessageHandler | None = None,
        queue_size: int = 100,
    ) -> asyncio.Queue[AgentMessage]:
        """Register an agent to receive messages.

        Args:
            agent_id: The agent's unique ID.
            handler: Optional async handler called for each message.
            queue_size: Max inbox size.

        Returns:
            The agent's inbox queue (can also be consumed directly).
        """
        if agent_id in self._inboxes:
            logger.warning("Agent %s already registered on bus", agent_id[:8])
            return self._inboxes[agent_id]

        inbox: asyncio.Queue[AgentMessage] = asyncio.Queue(maxsize=queue_size)
        self._inboxes[agent_id] = inbox

        if handler:
            self._handlers[agent_id].append(handler)

        # Start consumer task for this agent
        task = asyncio.create_task(
            self._consume_inbox(agent_id, inbox),
            name=f"msg-consumer-{agent_id[:8]}",
        )
        self._consumer_tasks[agent_id] = task

        logger.debug("Agent %s registered on message bus", agent_id[:8])
        return inbox

    async def unregister_agent(self, agent_id: str) -> None:
        """Remove an agent from the message bus."""
        if agent_id in self._consumer_tasks:
            self._consumer_tasks[agent_id].cancel()
            del self._consumer_tasks[agent_id]
        self._inboxes.pop(agent_id, None)
        self._handlers.pop(agent_id, None)

    async def send(self, message: AgentMessage) -> bool:
        """Send a direct message to a specific agent.

        Returns:
            True if delivered, False if receiver not found.
        """
        if not message.receiver:
            logger.warning("Cannot send direct message without receiver")
            return False

        inbox = self._inboxes.get(message.receiver)
        if inbox is None:
            logger.warning("Agent %s not found on bus", message.receiver[:8])
            return False

        try:
            inbox.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("Inbox full for agent %s, dropping message", message.receiver[:8])
            return False

        # Publish to event bus for observability
        await self._event_bus.publish(Event(
            topic="message.sent",
            data=message.to_dict(),
            source="message_bus",
        ))

        return True

    async def broadcast(self, message: AgentMessage) -> int:
        """Broadcast a message to all registered agents.

        Args:
            message: Message to broadcast (receiver field is ignored).

        Returns:
            Number of agents that received the message.
        """
        message.message_type = MessageType.BROADCAST
        delivered = 0

        for agent_id, inbox in self._inboxes.items():
            if agent_id == message.sender:
                continue  # Don't send back to sender

            try:
                inbox.put_nowait(AgentMessage(
                    content=message.content,
                    sender=message.sender,
                    receiver=agent_id,
                    message_type=MessageType.BROADCAST,
                    correlation_id=message.correlation_id,
                    message_id=str(uuid4()),
                    metadata=message.metadata,
                ))
                delivered += 1
            except asyncio.QueueFull:
                logger.warning("Inbox full for agent %s during broadcast", agent_id[:8])

        await self._event_bus.publish(Event(
            topic="message.broadcast",
            data={"sender": message.sender, "delivered": delivered},
            source="message_bus",
        ))

        return delivered

    async def request(
        self,
        target_agent_id: str,
        message: AgentMessage,
        timeout: float = 30.0,
    ) -> AgentMessage:
        """Send a request and wait for a reply (request-reply pattern).

        Args:
            target_agent_id: Agent to send the request to.
            message: The request message.
            timeout: Max seconds to wait for reply.

        Returns:
            The reply AgentMessage.

        Raises:
            asyncio.TimeoutError: If no reply within timeout.
            ValueError: If target not found.
        """
        correlation_id = message.correlation_id or message.message_id
        message.correlation_id = correlation_id
        message.receiver = target_agent_id
        message.message_type = MessageType.REQUEST

        # Create future for the reply
        loop = asyncio.get_running_loop()
        future: asyncio.Future[AgentMessage] = loop.create_future()
        self._pending_replies[correlation_id] = future

        try:
            delivered = await self.send(message)
            if not delivered:
                raise ValueError(f"Agent {target_agent_id} not found on bus")

            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending_replies.pop(correlation_id, None)

    async def reply(self, original: AgentMessage, content: str, **kwargs: Any) -> bool:
        """Send a reply to a request message.

        Args:
            original: The original request message.
            content: Reply content.

        Returns:
            True if delivered.
        """
        reply_msg = original.create_reply(content, **kwargs)
        return await self.send(reply_msg)

    async def _consume_inbox(self, agent_id: str, inbox: asyncio.Queue[AgentMessage]) -> None:
        """Consumer loop for an agent's inbox."""
        while self._running:
            try:
                message = await asyncio.wait_for(inbox.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            # Check if this is a reply to a pending request
            if message.message_type == MessageType.RESPONSE and message.correlation_id:
                future = self._pending_replies.get(message.correlation_id)
                if future and not future.done():
                    future.set_result(message)
                    continue

            # Dispatch to registered handlers
            handlers = self._handlers.get(agent_id, [])
            for handler in handlers:
                try:
                    await handler(message)
                except Exception:
                    logger.exception(
                        "Error in message handler for agent %s", agent_id[:8],
                    )

    def add_handler(self, agent_id: str, handler: MessageHandler) -> None:
        """Add a message handler for an agent."""
        self._handlers[agent_id].append(handler)

    @property
    def registered_agent_count(self) -> int:
        return len(self._inboxes)

    def is_agent_registered(self, agent_id: str) -> bool:
        return agent_id in self._inboxes
