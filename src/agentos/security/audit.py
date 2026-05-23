"""Structured audit logging for compliance and security.

Logs all significant operations with who/what/when/where/outcome.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from agentos.db.repositories.audit_repository import AuditRepository

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """A structured audit log entry."""

    action: str                       # e.g., "agent:create", "workflow:run"
    tenant_id: str = "default"
    user_id: str = ""
    agent_id: str = ""
    resource_type: str = ""           # e.g., "agent", "workflow", "session"
    resource_id: str = ""
    outcome: str = "success"          # "success", "failure", "denied"
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    entry_id: str = field(default_factory=lambda: str(uuid4()))


class AuditLogger:
    """Collects and dispatches audit entries.

    Entries are written to an in-memory buffer (always) and optionally
    persisted to the database via an ``AuditRepository``.

    Usage:
        audit = AuditLogger(repository=repo)
        audit.log(AuditEntry(action="agent:create", tenant_id="t1", user_id="u1"))
    """

    def __init__(
        self,
        buffer_size: int = 1000,
        repository: AuditRepository | None = None,
    ) -> None:
        self._buffer: list[AuditEntry] = []
        self._buffer_size = buffer_size
        self._repository = repository

    def log(self, entry: AuditEntry) -> None:
        """Log an audit entry (in-memory + optional DB persistence)."""
        self._buffer.append(entry)
        if len(self._buffer) > self._buffer_size:
            self._buffer = self._buffer[-self._buffer_size:]

        logger.info(
            "AUDIT: %s | tenant=%s user=%s resource=%s:%s outcome=%s details=%s",
            entry.action,
            entry.tenant_id,
            entry.user_id,
            entry.resource_type,
            entry.resource_id,
            entry.outcome,
            entry.details,
        )

        if self._repository is not None:
            self._persist_async(entry)

    def query(
        self,
        tenant_id: str | None = None,
        action: str | None = None,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Query recent audit entries (from in-memory buffer)."""
        results = self._buffer
        if tenant_id:
            results = [e for e in results if e.tenant_id == tenant_id]
        if action:
            results = [e for e in results if e.action == action]
        if user_id:
            results = [e for e in results if e.user_id == user_id]
        return results[-limit:]

    def clear(self) -> None:
        self._buffer.clear()

    @property
    def count(self) -> int:
        return len(self._buffer)

    def _persist_async(self, entry: AuditEntry) -> None:
        """Fire-and-forget DB write — failures are logged, not raised."""
        repository = self._repository

        async def _write() -> None:
            if repository is None:
                return
            await repository.add({
                "tenant_id": entry.tenant_id,
                "agent_id": entry.agent_id,
                "user_id": entry.user_id,
                "action": entry.action,
                "resource_type": entry.resource_type,
                "resource_id": entry.resource_id,
                "details": entry.details,
                "outcome": entry.outcome,
                "timestamp": entry.timestamp,
            })

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(_write())
            task.add_done_callback(AuditLogger._log_persist_error)
        except RuntimeError:
            pass  # No running event loop — skip DB write

    @staticmethod
    def _log_persist_error(task: asyncio.Task) -> None:  # type: ignore[type-arg]
        """Log audit-persist exceptions so they don't surface as unhandled task warnings."""
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return
        if exc:
            logger.warning("Audit DB persist failed (non-fatal): %s", exc)
