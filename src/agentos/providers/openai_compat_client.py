"""MAF-compatible chat client for OpenAI-compatible APIs.

MAF v1.6 hardcodes ``responses_mode=True`` which uses the ``/v1/responses``
endpoint. Most domestic LLM providers (DeepSeek, Qwen, Zhipu, Moonshot,
Doubao) only support the Chat Completions API (``/v1/chat/completions``).

This module provides ``OpenAICompatChatClient`` which wraps the OpenAI Python
SDK directly using the Chat Completions endpoint, while exposing the same
``as_agent()`` interface used by ``LifecycleManager._instantiate_agent()``.
"""

from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OpenAICompatChatClient:
    """A chat client for OpenAI-compatible APIs using Chat Completions.

    Usage::

        client = OpenAICompatChatClient(
            model="deepseek-chat",
            api_key="sk-...",
            base_url="https://api.deepseek.com/v1",
        )
        agent = client.as_agent(name="MyAgent", instructions="You are helpful.")
    """

    def __init__(
        self,
        model: str,
        api_key: str = "",
        base_url: str = "",
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.api_key = api_key
        self._async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def as_agent(
        self,
        name: str,
        instructions: str = "",
    ) -> Any:
        """Create a MAF Agent backed by this client.

        Uses the standard MAF agent lifecycle — the returned Agent supports
        ``run()`` / ``run_stream()`` / ``get_response()`` etc.
        """
        try:
            from agent_framework import Agent
        except ImportError:
            from agentos.kernel.registry import AgentRegistryError
            raise ImportError(
                "agent-framework not installed. Run: pip install agent-framework"
            )

        agent = Agent(
            name=name,
            instructions=instructions,
            client=self,
        )
        return agent

    async def get_response(self, messages: list[Any], **kwargs: Any) -> Any:
        """Send messages to the LLM and return a response.

        Uses the standard ``/v1/chat/completions`` endpoint.  Only passes
        parameters the Chat Completions API actually accepts; MAF-internal
        keys (instructions, compaction_strategy, etc.) are ignored.
        """
        openai_messages = self._normalize_messages(messages)

        # Only pass known Chat Completion params; ignore MAF internals.
        _CHAT_PARAMS = {
            "temperature", "top_p", "max_tokens", "max_completion_tokens",
            "stop", "stream", "frequency_penalty", "presence_penalty",
            "seed", "logit_bias", "logprobs", "top_logprobs", "n",
            "user", "tools", "tool_choice",
        }
        chat_kwargs: dict[str, Any] = {}
        for k, v in kwargs.items():
            if k in _CHAT_PARAMS:
                chat_kwargs[k] = v

        completion = await self._async_client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            **chat_kwargs,
        )
        # Wrap in MAF-compatible response so Agent.run() can process it
        from agent_framework import Message, ChatResponse

        msg = Message(role="assistant", contents=completion.choices[0].message.content or "")
        return ChatResponse(messages=[msg])

    @staticmethod
    def _extract_text(msg: Any) -> str:
        """Extract plain text from a MAF Message, Content, or string."""
        if isinstance(msg, str):
            return msg
        # MAF Content objects have a .text property or .value
        if hasattr(msg, "text") and callable(getattr(msg, "text", None)):
            return msg.text()
        if hasattr(msg, "text") and not callable(msg.text):
            return str(msg.text)
        if hasattr(msg, "value"):
            val = msg.value if not callable(msg.value) else msg.value()
            return str(val) if val else ""
        return str(msg)

    @staticmethod
    def _normalize_messages(messages: list[Any]) -> list[dict[str, str]]:
        """Convert MAF message objects or strings to OpenAI dict format."""
        result: list[dict[str, str]] = []
        for msg in messages:
            if isinstance(msg, dict):
                result.append(msg)
                continue
            if isinstance(msg, str):
                result.append({"role": "user", "content": msg})
                continue
            # MAF Message: has .role (str) and .contents (list of Content objects)
            if hasattr(msg, "role") and hasattr(msg, "contents"):
                # Flatten Content list into a single text string
                text_parts = []
                for c in (getattr(msg, "contents", None) or []):
                    text_parts.append(OpenAICompatChatClient._extract_text(c))
                content = " ".join(text_parts) if text_parts else str(msg)
                result.append({"role": str(msg.role), "content": content})
                continue
            # Fallback: try common attributes
            if hasattr(msg, "role") and hasattr(msg, "content"):
                result.append({"role": str(msg.role), "content": str(msg.content)})
                continue
            result.append({"role": "user", "content": str(msg)})
        return result
