"""Shared memory for multi-agent workflows.

Each agent maintains its own isolated session memory (via MAF sessions).
This module adds **shared memory** — a key-value store scoped by namespace
(typically the workflow ID or tenant) that all agents in a workflow can
read and write.

Usage in a pipeline workflow::

    # Agent A (product) writes a spec
    await shared.set("workflow-1", "spec", "Build a chat app")

    # Agent B (developer) reads the spec and writes its result
    spec = await shared.get("workflow-1", "spec")
    await shared.set("workflow-1", "code", "const app = ...")

    # Agent C (tester) reads both
    spec = await shared.get("workflow-1", "spec")
    code = await shared.get("workflow-1", "code")

Each agent still uses its own MAF session for conversation memory,
so ``agent.run("...", session=session)`` continues to work normally.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SharedMemory:
    """In-memory shared context for workflows.

    Scoped by **namespace** (typically ``workflow:<id>`` or ``tenant:<id>``).
    Agents within the same namespace can read and write shared facts.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}  # namespace -> {key: value}

    async def set(self, namespace: str, key: str, value: Any) -> None:
        """Store a value in the shared memory namespace."""
        if namespace not in self._store:
            self._store[namespace] = {}
        self._store[namespace][key] = value
        logger.debug("Shared memory [%s] %s = %s", namespace, key, str(value)[:80])

    async def get(self, namespace: str, key: str, default: Any = None) -> Any:
        """Retrieve a value from the shared memory namespace."""
        ns = self._store.get(namespace, {})
        return ns.get(key, default)

    async def get_all(self, namespace: str) -> dict[str, Any]:
        """Return all key-value pairs in a namespace."""
        return dict(self._store.get(namespace, {}))

    async def delete(self, namespace: str, key: str) -> bool:
        """Remove a key. Returns True if it existed."""
        ns = self._store.get(namespace, {})
        existed = key in ns
        ns.pop(key, None)
        return existed

    async def clear_namespace(self, namespace: str) -> None:
        """Remove all entries for a namespace."""
        self._store.pop(namespace, None)
        logger.info("Cleared shared memory namespace '%s'", namespace)

    def namespaces(self) -> list[str]:
        """List active namespace names."""
        return list(self._store.keys())

    def inject_into_prompt(self, namespace: str, base_prompt: str) -> str:
        """Prepend shared context to a prompt so the LLM sees it.

        Usage::

            ctx = shared.inject_into_prompt("workflow-1", "Write code")
            # ctx = "Shared context:\n  spec: Build a chat app\n\nWrite code"
        """
        facts = self._store.get(namespace, {})
        if not facts:
            return base_prompt

        lines = ["Shared context:"]
        for k, v in facts.items():
            lines.append(f"  {k}: {v}")
        lines.append("")
        lines.append(base_prompt)
        return "\n".join(lines)
