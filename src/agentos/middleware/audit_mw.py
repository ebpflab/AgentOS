"""Audit trail middleware for tool invocations.

Logs all tool/function calls for compliance tracking.
Designed as a MAF @function_middleware.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

from agentos.security.audit import AuditEntry, AuditLogger
from agentos.security.tenant import get_current_tenant

logger = logging.getLogger(__name__)


class AuditMiddleware:
    """Middleware that logs all tool invocations to the audit trail.

    Usage:
        mw = AuditMiddleware(audit_logger)
        result = await mw.wrap_tool_call(agent_id, tool_name, call_func, *args)
    """

    def __init__(self, audit_logger: AuditLogger) -> None:
        self._audit = audit_logger

    async def wrap_tool_call(
        self,
        agent_id: str,
        tool_name: str,
        call_func: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Wrap a tool call with audit logging."""
        tenant_ctx = get_current_tenant()
        tenant_id = tenant_ctx.tenant_id if tenant_ctx else "default"
        user_id = tenant_ctx.user_id if tenant_ctx else ""

        try:
            result = await call_func(*args, **kwargs)

            self._audit.log(AuditEntry(
                action=f"tool:{tool_name}",
                tenant_id=tenant_id,
                user_id=user_id,
                agent_id=agent_id,
                resource_type="tool",
                resource_id=tool_name,
                outcome="success",
                details={"args_count": len(args)},
            ))

            return result

        except Exception as e:
            self._audit.log(AuditEntry(
                action=f"tool:{tool_name}",
                tenant_id=tenant_id,
                user_id=user_id,
                agent_id=agent_id,
                resource_type="tool",
                resource_id=tool_name,
                outcome="failure",
                details={"error": str(e)},
            ))
            raise
