"""Session management API routes.

Sessions track multi-turn conversations.  They are stored in-memory
(via ``registry._sessions``) and optionally in the database when
PostgreSQL is available.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agentos.api.deps import require_permission
from agentos.api.server import get_runtime
from agentos.security.auth import UserInfo
from agentos.security.rbac import Permission

router = APIRouter()


class SessionResponse(BaseModel):
    session_id: str
    agent_id: str
    agent_name: str
    is_active: bool
    message_count: int = 0


class SessionMessage(BaseModel):
    role: str
    content: str


def _extract_text(msg: Any) -> str:
    """Extract plain text from a MAF Message, Content, or string."""
    if isinstance(msg, str):
        return msg
    if hasattr(msg, "text") and callable(getattr(msg, "text", None)):
        return msg.text()
    if hasattr(msg, "text") and not callable(msg.text):
        return str(msg.text)
    if hasattr(msg, "value"):
        val = msg.value if not callable(msg.value) else msg.value()
        return str(val) if val else ""
    return str(msg)


def _get_session_messages(session: Any) -> list[dict[str, str]]:
    """Extract messages from a MAF AgentSession's state."""
    state = getattr(session, "state", {}) or {}
    in_mem = state.get("in_memory", {})
    if not isinstance(in_mem, dict):
        return []

    raw_msgs = in_mem.get("messages", [])
    if not isinstance(raw_msgs, list):
        return []

    result: list[dict[str, str]] = []
    for m in raw_msgs:
        role = str(getattr(m, "role", "unknown"))
        contents = getattr(m, "contents", None)
        if contents and isinstance(contents, list):
            text = " ".join(_extract_text(c) for c in contents)
        else:
            text = _extract_text(m)
        result.append({"role": role, "content": text.strip()})
    return result


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    agent_id: str | None = None,
    user: UserInfo = Depends(require_permission(Permission.SESSION_READ)),
):
    """List all active sessions, optionally filtered by agent."""
    runtime = get_runtime()
    result: list[SessionResponse] = []

    for sid, session in runtime.registry._sessions.items():
        msgs = _get_session_messages(session)
        agent_name = "Agent"
        # Try to get agent name from first user message context
        if msgs:
            first_content = msgs[0].get("content", "")
            if len(first_content) > 30:
                agent_name = first_content[:30] + "..."

        result.append(SessionResponse(
            session_id=sid,
            agent_id=agent_id or "",
            agent_name=agent_name,
            is_active=True,
            message_count=len(msgs),
        ))

    return result


@router.get("/{session_id}/history")
async def get_session_history(
    session_id: str,
    user: UserInfo = Depends(require_permission(Permission.SESSION_READ)),
):
    """Get conversation history for a session."""
    runtime = get_runtime()
    session = runtime.registry._sessions.get(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "messages": _get_session_messages(session),
    }
