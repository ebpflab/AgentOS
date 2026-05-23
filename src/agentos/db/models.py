"""SQLAlchemy async models for AgentOS persistent storage.

All core entities are stored in PostgreSQL: agents, tenants, sessions,
audit logs, token usage, workflow runs, and messages.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all AgentOS models."""
    pass


class TenantModel(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    agents: Mapped[list[AgentModel]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class AgentModel(Base):
    __tablename__ = "agents"
    __table_args__ = (
        Index("ix_agents_tenant_name", "tenant_id", "name"),
        Index("ix_agents_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="created")
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id"), default="default")
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    agent_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    tenant: Mapped[TenantModel] = relationship(back_populates="agents")
    sessions: Mapped[list[SessionModel]] = relationship(back_populates="agent", cascade="all, delete-orphan")


class SessionModel(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_agent", "agent_id"),
        Index("ix_sessions_tenant", "tenant_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    agent_id: Mapped[str] = mapped_column(String(64), ForeignKey("agents.id"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default")
    service_session_id: Mapped[str] = mapped_column(String(255), default="")
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    messages: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    agent: Mapped[AgentModel] = relationship(back_populates="sessions")


class TokenUsageModel(Base):
    __tablename__ = "token_usage"
    __table_args__ = (
        Index("ix_token_usage_agent", "agent_id"),
        Index("ix_token_usage_tenant_time", "tenant_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default")
    provider: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    extra_data: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditLogModel(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_tenant_time", "tenant_id", "timestamp"),
        Index("ix_audit_agent", "agent_id"),
        Index("ix_audit_action", "action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default")
    agent_id: Mapped[str] = mapped_column(String(64), default="")
    user_id: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), default="")
    resource_id: Mapped[str] = mapped_column(String(255), default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    outcome: Mapped[str] = mapped_column(String(32), default="success")
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WorkflowRunModel(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_workflow_runs_tenant", "tenant_id"),
        Index("ix_workflow_runs_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    workflow_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default")
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/running/completed/failed/suspended
    input_data: Mapped[dict] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    agents_involved: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MessageModel(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_sender", "sender"),
        Index("ix_messages_receiver", "receiver"),
        Index("ix_messages_correlation", "correlation_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sender: Mapped[str] = mapped_column(String(64), default="")
    receiver: Mapped[str] = mapped_column(String(64), default="")
    message_type: Mapped[str] = mapped_column(String(32), default="request")
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    correlation_id: Mapped[str] = mapped_column(String(64), default="")
    reply_to: Mapped[str] = mapped_column(String(64), default="")
    workflow_id: Mapped[str] = mapped_column(String(64), default="")
    extra_data: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
