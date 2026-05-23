"""MAF ContextProvider implementations for memory injection.

These providers inject relevant memories into agent context before
each run and persist new facts after runs.
"""

from __future__ import annotations

import logging
from typing import Any

from agentos.memory.shared_kb import SharedKnowledgeBase

logger = logging.getLogger(__name__)


class MemoryContextProvider:
    """MAF-compatible ContextProvider that injects KB memories into agent context.

    Follows MAF's ContextProvider pattern:
    - before_run(): Loads relevant memories and extends agent instructions
    - after_run(): Optionally persists new facts extracted from the conversation

    Usage (with MAF Agent):
        provider = MemoryContextProvider(kb, tenant_id="t1", agent_id="a1")
        agent = client.as_agent(
            name="MyAgent",
            context_providers=[provider],
        )
    """

    def __init__(
        self,
        kb: SharedKnowledgeBase,
        tenant_id: str = "default",
        agent_id: str = "",
        memory_keys: list[str] | None = None,
        max_memories: int = 20,
    ) -> None:
        self._kb = kb
        self._tenant_id = tenant_id
        self._agent_id = agent_id
        self._memory_keys = memory_keys  # Specific keys to load, None = load all
        self._max_memories = max_memories

    async def before_run(self, agent: Any, session: Any, context: Any, state: dict) -> None:
        """Load relevant memories and inject into agent context.

        Called by MAF before each agent run. Extends the agent's
        instructions with relevant memory context.
        """
        memories: list[str] = []

        try:
            if self._memory_keys:
                # Load specific keys
                for key in self._memory_keys:
                    value = await self._kb.get_any(self._tenant_id, self._agent_id, key)
                    if value is not None:
                        memories.append(f"- {key}: {value}")
            else:
                # Load all shared memories
                shared_keys = await self._kb.list_shared(self._tenant_id)
                for key in shared_keys[:self._max_memories]:
                    value = await self._kb.get_shared(self._tenant_id, key)
                    if value is not None:
                        memories.append(f"- {key}: {value}")

                # Load agent-specific memories
                if self._agent_id:
                    agent_keys = await self._kb.list_agent_keys(self._tenant_id, self._agent_id)
                    remaining = self._max_memories - len(memories)
                    for key in agent_keys[:remaining]:
                        value = await self._kb.get_agent(self._tenant_id, self._agent_id, key)
                        if value is not None:
                            memories.append(f"- {key}: {value}")

        except Exception:
            logger.exception("Failed to load memories for agent %s", self._agent_id)
            return

        if memories:
            memory_block = "\n".join(memories)
            memory_instruction = (
                f"\n\n[Memory Context]\n"
                f"The following information is available from your memory:\n{memory_block}\n"
                f"Use this context to provide more relevant and personalized responses."
            )
            # Extend agent instructions with memory context
            if hasattr(context, 'extend_instructions'):
                context.extend_instructions(memory_instruction)

    async def after_run(self, agent: Any, session: Any, context: Any, state: dict) -> None:
        """Optionally persist new facts from the conversation.

        Override this in subclasses to implement automatic fact extraction.
        """
        pass


class SessionStateProvider:
    """Injects session state (user preferences, conversation metadata) into context."""

    def __init__(self, state_keys: list[str] | None = None) -> None:
        self._state_keys = state_keys

    async def before_run(self, agent: Any, session: Any, context: Any, state: dict) -> None:
        """Inject session state into agent context."""
        if not state:
            return

        parts = []
        keys = self._state_keys or list(state.keys())
        for key in keys:
            if key in state:
                parts.append(f"- {key}: {state[key]}")

        if parts and hasattr(context, 'extend_instructions'):
            context.extend_instructions(
                f"\n\n[Session State]\n" + "\n".join(parts)
            )
