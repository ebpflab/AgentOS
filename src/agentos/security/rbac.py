"""Role-Based Access Control (RBAC) for AgentOS.

Policy-based: can(subject, action, resource) → bool.
Roles and permissions stored in config, evaluated by middleware.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """Standard permissions."""

    # Agent operations
    AGENT_CREATE = "agent:create"
    AGENT_READ = "agent:read"
    AGENT_UPDATE = "agent:update"
    AGENT_DELETE = "agent:delete"
    AGENT_RUN = "agent:run"

    # Workflow operations
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_RUN = "workflow:run"

    # Session operations
    SESSION_READ = "session:read"

    # Metrics
    METRICS_READ = "metrics:read"

    # Admin
    ADMIN_TENANTS = "admin:tenants"
    ADMIN_USERS = "admin:users"
    ADMIN_RBAC = "admin:rbac"


class Role(str, Enum):
    """Built-in roles."""

    ADMIN = "admin"         # Full access
    OPERATOR = "operator"   # Manage agents and workflows
    VIEWER = "viewer"       # Read-only access
    AGENT = "agent"         # Agent-level access (for service accounts)


# Default role → permissions mapping
DEFAULT_ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    Role.ADMIN: set(Permission),  # All permissions
    Role.OPERATOR: {
        Permission.AGENT_CREATE, Permission.AGENT_READ, Permission.AGENT_UPDATE,
        Permission.AGENT_DELETE, Permission.AGENT_RUN,
        Permission.WORKFLOW_CREATE, Permission.WORKFLOW_READ, Permission.WORKFLOW_RUN,
        Permission.SESSION_READ, Permission.METRICS_READ,
    },
    Role.VIEWER: {
        Permission.AGENT_READ, Permission.WORKFLOW_READ,
        Permission.SESSION_READ, Permission.METRICS_READ,
    },
    Role.AGENT: {
        Permission.AGENT_READ, Permission.AGENT_RUN,
        Permission.SESSION_READ,
    },
}


class AccessDeniedError(Exception):
    """Raised when access is denied."""


@dataclass
class RBACPolicy:
    """RBAC policy configuration."""

    role_permissions: dict[str, set[Permission]] = field(
        default_factory=lambda: dict(DEFAULT_ROLE_PERMISSIONS)
    )


class RBACManager:
    """Evaluates access control decisions.

    Usage:
        rbac = RBACManager()
        rbac.check("user-1", ["operator"], Permission.AGENT_CREATE)  # OK
        rbac.check("user-2", ["viewer"], Permission.AGENT_CREATE)    # Raises AccessDeniedError
    """

    def __init__(self, policy: RBACPolicy | None = None) -> None:
        self._policy = policy or RBACPolicy()

    def check(self, user_id: str, roles: list[str], permission: Permission) -> None:
        """Check if a user with given roles has a permission.

        Raises:
            AccessDeniedError: If access is denied.
        """
        if self.can(roles, permission):
            return
        raise AccessDeniedError(
            f"User '{user_id}' with roles {roles} lacks permission '{permission.value}'"
        )

    def can(self, roles: list[str], permission: Permission) -> bool:
        """Check if any of the roles grants the permission."""
        for role in roles:
            perms = self._policy.role_permissions.get(role, set())
            if permission in perms:
                return True
        return False

    def get_permissions(self, roles: list[str]) -> set[Permission]:
        """Get all permissions for a set of roles."""
        perms: set[Permission] = set()
        for role in roles:
            perms.update(self._policy.role_permissions.get(role, set()))
        return perms

    def add_role(self, role: str, permissions: set[Permission]) -> None:
        """Add or update a custom role."""
        self._policy.role_permissions[role] = permissions

    def add_permission_to_role(self, role: str, permission: Permission) -> None:
        """Grant an additional permission to a role."""
        if role not in self._policy.role_permissions:
            self._policy.role_permissions[role] = set()
        self._policy.role_permissions[role].add(permission)
