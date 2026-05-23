"""Tests for the Message Bus and inter-agent communication."""

from __future__ import annotations

import asyncio

from agentos.communication.bus import MessageBus
from agentos.communication.protocols import AgentMessage, MessageType
from agentos.kernel.events import EventBus


async def test_direct_messaging():
    """Test sending a direct message between agents."""
    event_bus = EventBus()
    await event_bus.start()
    bus = MessageBus(event_bus)
    await bus.start()

    received: list[AgentMessage] = []

    async def handler(msg: AgentMessage) -> None:
        received.append(msg)

    await bus.register_agent("agent-a")
    await bus.register_agent("agent-b", handler=handler)

    msg = AgentMessage(content="Hello B!", sender="agent-a", receiver="agent-b")
    delivered = await bus.send(msg)

    assert delivered is True
    await asyncio.sleep(0.1)
    assert len(received) == 1
    assert received[0].content == "Hello B!"
    assert received[0].sender == "agent-a"

    await bus.stop()
    await event_bus.stop()


async def test_broadcast():
    """Test broadcasting a message to all agents."""
    event_bus = EventBus()
    await event_bus.start()
    bus = MessageBus(event_bus)
    await bus.start()

    received_b: list[AgentMessage] = []
    received_c: list[AgentMessage] = []

    await bus.register_agent("agent-a")
    await bus.register_agent("agent-b", handler=lambda m: received_b.append(m) or asyncio.sleep(0))
    await bus.register_agent("agent-c", handler=lambda m: received_c.append(m) or asyncio.sleep(0))

    # Create proper async handlers
    async def handler_b(m: AgentMessage) -> None:
        received_b.append(m)

    async def handler_c(m: AgentMessage) -> None:
        received_c.append(m)

    # Re-register with proper handlers
    await bus.stop()
    await bus.start()
    bus._inboxes.clear()
    bus._handlers.clear()
    bus._consumer_tasks.clear()

    await bus.register_agent("agent-a")
    await bus.register_agent("agent-b", handler=handler_b)
    await bus.register_agent("agent-c", handler=handler_c)

    count = await bus.broadcast(AgentMessage(content="Alert!", sender="agent-a"))
    assert count == 2  # b and c, not a (sender excluded)

    await asyncio.sleep(0.2)
    assert len(received_b) == 1
    assert len(received_c) == 1
    assert received_b[0].content == "Alert!"

    await bus.stop()
    await event_bus.stop()


async def test_request_reply():
    """Test request-reply pattern between agents."""
    event_bus = EventBus()
    await event_bus.start()
    bus = MessageBus(event_bus)
    await bus.start()

    # Agent B auto-replies to requests
    async def auto_reply_handler(msg: AgentMessage) -> None:
        if msg.message_type == MessageType.REQUEST:
            reply = msg.create_reply(f"Reply to: {msg.content}")
            await bus.send(reply)

    await bus.register_agent("agent-a")
    await bus.register_agent("agent-b", handler=auto_reply_handler)

    request = AgentMessage(content="What is 2+2?", sender="agent-a")
    response = await bus.request("agent-b", request, timeout=5.0)

    assert response.content == "Reply to: What is 2+2?"
    assert response.message_type == MessageType.RESPONSE
    assert response.sender == "agent-b"

    await bus.stop()
    await event_bus.stop()


async def test_send_to_nonexistent_agent():
    """Test sending to an agent that doesn't exist."""
    event_bus = EventBus()
    await event_bus.start()
    bus = MessageBus(event_bus)
    await bus.start()

    msg = AgentMessage(content="Hello", receiver="nonexistent")
    delivered = await bus.send(msg)
    assert delivered is False

    await bus.stop()
    await event_bus.stop()


async def test_unregister_agent():
    """Test unregistering an agent from the bus."""
    event_bus = EventBus()
    await event_bus.start()
    bus = MessageBus(event_bus)
    await bus.start()

    await bus.register_agent("agent-a")
    assert bus.is_agent_registered("agent-a")

    await bus.unregister_agent("agent-a")
    assert not bus.is_agent_registered("agent-a")

    await bus.stop()
    await event_bus.stop()


async def test_message_serialization():
    """Test message to_dict/from_dict round-trip."""
    from agentos.communication.protocols import AgentMessage, MessageType

    msg = AgentMessage(
        content="Hello",
        sender="agent-a",
        receiver="agent-b",
        message_type=MessageType.REQUEST,
        metadata={"key": "value"},
    )

    data = msg.to_dict()
    restored = AgentMessage.from_dict(data)

    assert restored.content == msg.content
    assert restored.sender == msg.sender
    assert restored.receiver == msg.receiver
    assert restored.message_type == MessageType.REQUEST
    assert restored.metadata == {"key": "value"}


async def test_conversation_context():
    """Test ConversationContext tracking."""
    from agentos.communication.protocols import ConversationContext

    ctx = ConversationContext()
    msg1 = AgentMessage(content="Hi", sender="a", receiver="b")
    msg2 = AgentMessage(content="Hello", sender="b", receiver="a")

    ctx.add_message(msg1)
    ctx.add_message(msg2)

    assert ctx.message_count == 2
    assert set(ctx.participants) == {"a", "b"}
    assert ctx.last_message.content == "Hello"


# Run all tests
async def main():
    await test_direct_messaging()
    print("  direct_messaging PASSED")

    await test_broadcast()
    print("  broadcast PASSED")

    await test_request_reply()
    print("  request_reply PASSED")

    await test_send_to_nonexistent_agent()
    print("  send_to_nonexistent PASSED")

    await test_unregister_agent()
    print("  unregister_agent PASSED")

    await test_message_serialization()
    print("  message_serialization PASSED")

    await test_conversation_context()
    print("  conversation_context PASSED")


if __name__ == "__main__":
    asyncio.run(main())
