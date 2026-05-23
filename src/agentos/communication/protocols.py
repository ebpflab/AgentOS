"""Message protocols and schemas for inter-agent communication.

Defines the standard message format used across the AgentOS message bus,
A2A bridge, and workflow data passing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class MessageType(str, Enum):
    """Types of inter-agent messages."""

    REQUEST = "request"          # Task request to an agent
    RESPONSE = "response"        # Response from an agent
    NOTIFICATION = "notification" # Fire-and-forget notification
    BROADCAST = "broadcast"      # Message to all agents
    SYSTEM = "system"            # System-level message (lifecycle, errors)
    STREAM = "stream"            # Streaming partial response


class MessagePriority(str, Enum):
    """Message priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class AgentMessage:
    """Standard message format for agent communication.

    Used for:
    - Direct agent-to-agent messaging
    - Bus pub/sub messages
    - Workflow data passing
    - A2A protocol bridging
    """

    content: str
    sender: str = ""                  # sender agent_id or "system"
    receiver: str = ""                # receiver agent_id, "" for broadcast
    message_type: MessageType = MessageType.REQUEST
    priority: MessagePriority = MessagePriority.NORMAL
    correlation_id: str = ""          # Links request/response pairs
    reply_to: str = ""                # Message ID this replies to
    message_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Workflow context
    workflow_id: str = ""
    step_name: str = ""

    def create_reply(self, content: str, **kwargs: Any) -> AgentMessage:
        """Create a reply message to this message."""
        return AgentMessage(
            content=content,
            sender=self.receiver,
            receiver=self.sender,
            message_type=MessageType.RESPONSE,
            correlation_id=self.correlation_id or self.message_id,
            reply_to=self.message_id,
            workflow_id=self.workflow_id,
            step_name=self.step_name,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "message_id": self.message_id,
            "content": self.content,
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type.value,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "workflow_id": self.workflow_id,
            "step_name": self.step_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMessage:
        """Deserialize from dictionary."""
        return cls(
            message_id=data.get("message_id", str(uuid4())),
            content=data["content"],
            sender=data.get("sender", ""),
            receiver=data.get("receiver", ""),
            message_type=MessageType(data.get("message_type", "request")),
            priority=MessagePriority(data.get("priority", "normal")),
            correlation_id=data.get("correlation_id", ""),
            reply_to=data.get("reply_to", ""),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
            workflow_id=data.get("workflow_id", ""),
            step_name=data.get("step_name", ""),
        )


@dataclass
class ConversationContext:
    """Tracks multi-turn conversation state between agents."""

    conversation_id: str = field(default_factory=lambda: str(uuid4()))
    participants: list[str] = field(default_factory=list)
    messages: list[AgentMessage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, message: AgentMessage) -> None:
        self.messages.append(message)
        for agent_id in (message.sender, message.receiver):
            if agent_id and agent_id not in self.participants:
                self.participants.append(agent_id)

    @property
    def last_message(self) -> AgentMessage | None:
        return self.messages[-1] if self.messages else None

    @property
    def message_count(self) -> int:
        return len(self.messages)
