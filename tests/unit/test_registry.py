"""Tests for the Agent Registry."""

from __future__ import annotations

import pytest

from agentos.kernel.registry import AgentMetadata, AgentRegistry, AgentRegistryError, AgentStatus


class TestAgentRegistry:
    def test_register_and_get(self) -> None:
        registry = AgentRegistry(max_agents=10)
        meta = AgentMetadata(
            agent_id="agent-1",
            name="TestAgent",
            capabilities=["coding", "review"],
            provider="openai",
            model="gpt-4.1",
        )
        registry.register(meta)

        result = registry.get("agent-1")
        assert result is not None
        assert result.name == "TestAgent"
        assert result.capabilities == ["coding", "review"]
        assert registry.count == 1

    def test_register_duplicate_raises(self) -> None:
        registry = AgentRegistry(max_agents=10)
        meta = AgentMetadata(agent_id="agent-1", name="TestAgent")
        registry.register(meta)

        with pytest.raises(AgentRegistryError, match="already registered"):
            registry.register(meta)

    def test_max_agents_limit(self) -> None:
        registry = AgentRegistry(max_agents=2)
        registry.register(AgentMetadata(agent_id="a1", name="Agent1"))
        registry.register(AgentMetadata(agent_id="a2", name="Agent2"))

        with pytest.raises(AgentRegistryError, match="Maximum agents"):
            registry.register(AgentMetadata(agent_id="a3", name="Agent3"))

    def test_unregister(self) -> None:
        registry = AgentRegistry(max_agents=10)
        meta = AgentMetadata(agent_id="agent-1", name="TestAgent")
        registry.register(meta)

        removed = registry.unregister("agent-1")
        assert removed is not None
        assert removed.name == "TestAgent"
        assert registry.count == 0
        assert registry.get("agent-1") is None

    def test_unregister_nonexistent_returns_none(self) -> None:
        registry = AgentRegistry(max_agents=10)
        assert registry.unregister("nonexistent") is None

    def test_find_by_capability(self) -> None:
        registry = AgentRegistry(max_agents=10)
        registry.register(AgentMetadata(
            agent_id="a1", name="Coder", capabilities=["coding", "python"],
        ))
        registry.register(AgentMetadata(
            agent_id="a2", name="Reviewer", capabilities=["review", "python"],
        ))
        registry.register(AgentMetadata(
            agent_id="a3", name="Writer", capabilities=["writing"],
        ))

        python_agents = registry.find_by_capability("python")
        assert len(python_agents) == 2
        names = {a.name for a in python_agents}
        assert names == {"Coder", "Reviewer"}

    def test_find_by_capability_with_tenant_filter(self) -> None:
        registry = AgentRegistry(max_agents=10)
        registry.register(AgentMetadata(
            agent_id="a1", name="Agent1", capabilities=["coding"], tenant_id="tenant-a",
        ))
        registry.register(AgentMetadata(
            agent_id="a2", name="Agent2", capabilities=["coding"], tenant_id="tenant-b",
        ))

        results = registry.find_by_capability("coding", tenant_id="tenant-a")
        assert len(results) == 1
        assert results[0].name == "Agent1"

    def test_find_by_name(self) -> None:
        registry = AgentRegistry(max_agents=10)
        registry.register(AgentMetadata(agent_id="a1", name="MyAgent"))

        assert registry.find_by_name("MyAgent") is not None
        assert registry.find_by_name("Nonexistent") is None

    def test_list_agents_filters(self) -> None:
        registry = AgentRegistry(max_agents=10)
        registry.register(AgentMetadata(
            agent_id="a1", name="Agent1", tenant_id="t1", status=AgentStatus.RUNNING,
        ))
        registry.register(AgentMetadata(
            agent_id="a2", name="Agent2", tenant_id="t2", status=AgentStatus.STOPPED,
        ))

        # Filter by tenant
        assert len(registry.list_agents(tenant_id="t1")) == 1
        # Filter by status
        assert len(registry.list_agents(status=AgentStatus.RUNNING)) == 1
        # No filter
        assert len(registry.list_agents()) == 2

    def test_update_status(self) -> None:
        registry = AgentRegistry(max_agents=10)
        meta = AgentMetadata(agent_id="a1", name="TestAgent")
        registry.register(meta)

        registry.update_status("a1", AgentStatus.RUNNING)
        assert registry.get("a1").status == AgentStatus.RUNNING

    def test_set_and_get_instance(self) -> None:
        registry = AgentRegistry(max_agents=10)
        meta = AgentMetadata(agent_id="a1", name="TestAgent")
        registry.register(meta)

        mock_instance = object()
        registry.set_instance("a1", mock_instance)
        assert registry.get_instance("a1") is mock_instance

    def test_set_instance_unregistered_raises(self) -> None:
        registry = AgentRegistry(max_agents=10)
        with pytest.raises(AgentRegistryError, match="not registered"):
            registry.set_instance("nonexistent", object())
