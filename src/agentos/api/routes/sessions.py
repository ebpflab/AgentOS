"""Session management API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from agentos.api.deps import require_permission
from agentos.security.auth import UserInfo
from agentos.security.rbac import Permission

router = APIRouter()


class SessionResponse(BaseModel):
    session_id: str
    agent_id: str
    is_active: bool
    message_count: int = 0


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    agent_id: str | None = None,
    user: UserInfo = Depends(require_permission(Permission.SESSION_READ)),
):
    """List sessions."""
    return []  # Populated when DB integration is active


@router.get("/{session_id}/history")
async def get_session_history(
    session_id: str,
    user: UserInfo = Depends(require_permission(Permission.SESSION_READ)),
):
    """Get conversation history for a session."""
    return {"session_id": session_id, "messages": []}
