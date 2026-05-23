"""Unit tests for persistence layer: AgentRepository, AuditRepository, AgentRegistry.

Compatible with both pytest and unittest.
"""

from __future__ import annotations

import asyncio
import unittest
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from agentos.db.repositories.agent_repository import AgentRepository
from agentos.db.repositories.audit_repository import AuditRepository
from agentos.kernel.registry import AgentMetadata, AgentRegistry, AgentStatus
from agentos.security.audit import AuditEntry, AuditLogger


# ---------------------------------------------------------------------------
# Helpers: lightweight in-memory "DB" via a fake session
# ---------------------------------------------------------------------------

class _FakeSession:
    """Minimal async session that stores objects in a list."""

    def __init__(self, store: list) -> None:
        self._store = store
        self._added: list = []
        self._deleted_ids: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    def add(self, obj: Any) -> None:
        self._added.append(obj)

    async def merge(self, obj: Any) -> Any:
        """Upsert: replace existing by id or append."""
        existing = next((o for o in self._store if hasattr(o, "id") and o.id == obj.id), None)
        if existing is not None:
            self._store.remove(existing)
        self._added.append(obj)
        return obj

    async def commit(self) -> None:
        self._store.extend(self._added)
        self._added.clear()
        # Apply pending deletes
        for del_id in self._deleted_ids:
            self._store[:] = [o for o in self._store if getattr(o, "id", None) != del_id]
        self._deleted_ids.clear()

    async def get(self, model_cls, pk: str) -> Any | None:
        for obj in self._store:
            if isinstance(obj, model_cls) and obj.id == pk:
                return obj
        return None

    async def execute(self, stmt: Any) -> Any:
        """Handle both SELECT (return store contents) and DELETE (return rowcount)."""
        from sqlalchemy.sql.dml import Delete
        result = MagicMock()
        if isinstance(stmt, Delete):
            # Extract the id from the WHERE clause comparison
            where = stmt.whereclause
            if where is not None:
                # The right side of the WHERE clause has the value
                pk_val = where.right.value if hasattr(where, "right") else None
                matched = sum(1 for o in self._store if getattr(o, "id", None) == pk_val)
                result.rowcount = matched
                if pk_val is not None:
                    self._deleted_ids.append(pk_val)
            else:
                result.rowcount = len(self._store)
        else:
            result.rowcount = 0
            result.scalars.return_value.all.return_value = list(self._store)
        return result


def _make_session_factory(store: list):
    @asynccontextmanager
    async def factory():
        yield _FakeSession(store)
    return factory


def _run(coro):
    """Run an async coroutine synchronously (test helper)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# AgentRepository
# ---------------------------------------------------------------------------

class TestAgentRepository(unittest.TestCase):
    def setUp(self):
        self.store = []
        self.repo = AgentRepository(_make_session_factory(self.store))

    def _meta(self, agent_id="a1", name="TestAgent", capabilities=None, tenant_id="t1"):
        return AgentMetadata(
            agent_id=agent_id,
            name=name,
            capabilities=capabilities or ["cap1"],
            tenant_id=tenant_id,
        )

    def test_add_persists_model(self):
        _run(self.repo.add(self._meta()))
        self.assertEqual(len(self.store), 1)
        self.assertEqual(self.store[0].id, "a1")
        self.assertEqual(self.store[0].name, "TestAgent")

    def test_get_returns_metadata(self):
        _run(self.repo.add(self._meta()))
        result = _run(self.repo.get("a1"))
        self.assertIsNotNone(result)
        self.assertEqual(result.agent_id, "a1")
        self.assertEqual(result.capabilities, ["cap1"])

    def test_get_missing_returns_none(self):
        result = _run(self.repo.get("nonexistent"))
        self.assertIsNone(result)

    def test_list_all(self):
        _run(self.repo.add(self._meta("a1")))
        _run(self.repo.add(self._meta("a2", name="B")))
        all_agents = _run(self.repo.list_all())
        self.assertEqual(len(all_agents), 2)

    def test_find_by_capability_match(self):
        _run(self.repo.add(self._meta("a1", capabilities=["code-review"])))
        _run(self.repo.add(self._meta("a2", capabilities=["summarize"])))
        found = _run(self.repo.find_by_capability("code-review"))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].agent_id, "a1")

    def test_find_by_capability_no_match(self):
        _run(self.repo.add(self._meta("a1", capabilities=["summarize"])))
        found = _run(self.repo.find_by_capability("missing-cap"))
        self.assertEqual(found, [])

    def test_remove_agent(self):
        """remove() deletes the agent and returns True if it existed."""
        _run(self.repo.add(self._meta("del1")))
        self.assertEqual(len(self.store), 1)
        existed = _run(self.repo.remove("del1"))
        self.assertTrue(existed)
        self.assertEqual(len(self.store), 0)

    def test_remove_nonexistent_returns_false(self):
        """remove() returns False when the agent is not in the DB."""
        result = _run(self.repo.remove("ghost"))
        self.assertFalse(result)

    def test_upsert_does_not_duplicate(self):
        """Calling add() twice with the same agent_id results in one row."""
        meta = self._meta("dup1")
        _run(self.repo.add(meta))
        _run(self.repo.add(meta))
        self.assertEqual(len(self.store), 1)

    def test_to_metadata_invalid_status_falls_back(self):
        from agentos.db.models import AgentModel
        model = AgentModel(
            id="x1", name="Test", capabilities=["a"], status="unknown_status",
            tenant_id="default", provider="", model="", description="",
            tags={}, config={}, agent_metadata={},
        )
        meta = AgentRepository._to_metadata(model)
        self.assertEqual(meta.status, AgentStatus.CREATED)

    def test_to_metadata_valid_status(self):
        from agentos.db.models import AgentModel
        model = AgentModel(
            id="x2", name="Test2", capabilities=[], status="running",
            tenant_id="default", provider="", model="", description="",
            tags={}, config={}, agent_metadata={},
        )
        meta = AgentRepository._to_metadata(model)
        self.assertEqual(meta.status, AgentStatus.RUNNING)


# ---------------------------------------------------------------------------
# AuditRepository
# ---------------------------------------------------------------------------

class TestAuditRepository(unittest.TestCase):
    def setUp(self):
        self.store = []
        self.repo = AuditRepository(_make_session_factory(self.store))

    def _entry(self, tenant_id="t1", action="agent:create", user_id="u1"):
        return {
            "tenant_id": tenant_id, "agent_id": "a1", "user_id": user_id,
            "action": action, "resource_type": "agent",
            "resource_id": "a1", "details": {}, "outcome": "success",
        }

    def test_add_persists(self):
        _run(self.repo.add(self._entry()))
        self.assertEqual(len(self.store), 1)
        self.assertEqual(self.store[0].action, "agent:create")
        self.assertEqual(self.store[0].tenant_id, "t1")

    def test_query_returns_list(self):
        for i in range(3):
            _run(self.repo.add(self._entry(user_id=f"u{i}")))
        results = _run(self.repo.query(tenant_id="t1", limit=10))
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r["action"] == "agent:create" for r in results))

    def test_add_missing_optional_fields_defaults(self):
        """add() should not raise if optional fields are absent."""
        _run(self.repo.add({"action": "minimal:action"}))
        self.assertEqual(self.store[0].tenant_id, "default")
        self.assertEqual(self.store[0].outcome, "success")

    def test_add_missing_action_raises(self):
        """add() must raise ValueError if action is missing or empty."""
        with self.assertRaises(ValueError):
            _run(self.repo.add({"tenant_id": "t1"}))

    def test_add_empty_action_raises(self):
        with self.assertRaises(ValueError):
            _run(self.repo.add({"action": ""}))

    def test_add_preserves_timestamp(self):
        """add() should store the app-level timestamp, not just server_default."""
        import time
        ts = time.time() - 3600  # 1 hour ago
        _run(self.repo.add({"action": "old:event", "timestamp": ts}))
        from datetime import datetime, timezone
        expected = datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
        # Allow 1-second tolerance for floating-point rounding
        self.assertAlmostEqual(
            self.store[0].timestamp.timestamp(),
            expected.timestamp(),
            delta=1,
        )


# ---------------------------------------------------------------------------
# AgentRegistry + repository
# ---------------------------------------------------------------------------

class TestAgentRegistryWithRepository(unittest.TestCase):
    def setUp(self):
        self.store = []
        self.repo = AgentRepository(_make_session_factory(self.store))
        self.registry = AgentRegistry(repository=self.repo)

    def test_register_schedules_persist(self):
        persisted = []

        def fake_persist(coro):
            if coro is not None:
                try:
                    coro.close()  # prevent unawaited coroutine warning
                except Exception:
                    pass
            persisted.append(True)

        meta = AgentMetadata(agent_id="r1", name="Reg1", capabilities=["c1"])
        with patch.object(AgentRegistry, "_persist_async", staticmethod(fake_persist)):
            self.registry.register(meta)

        self.assertEqual(self.registry.count, 1)
        self.assertEqual(len(persisted), 1)

    def test_register_without_repo_works(self):
        reg = AgentRegistry(repository=None)
        meta = AgentMetadata(agent_id="m1", name="MemOnly")
        reg.register(meta)
        self.assertIsNotNone(reg.get("m1"))

    def test_update_status_schedules_persist(self):
        persisted = []

        def fake_persist(coro):
            if coro is not None:
                try:
                    coro.close()
                except Exception:
                    pass
            persisted.append(True)

        meta = AgentMetadata(agent_id="r2", name="R2")
        with patch.object(AgentRegistry, "_persist_async", staticmethod(fake_persist)):
            self.registry.register(meta)
            self.registry.update_status("r2", AgentStatus.RUNNING)

        self.assertEqual(len(persisted), 2)  # add + update_status

    def test_unregister_schedules_persist(self):
        persisted = []

        def fake_persist(coro):
            if coro is not None:
                try:
                    coro.close()
                except Exception:
                    pass
            persisted.append(True)

        meta = AgentMetadata(agent_id="r3", name="R3")
        with patch.object(AgentRegistry, "_persist_async", staticmethod(fake_persist)):
            self.registry.register(meta)
            self.registry.unregister("r3")

        self.assertEqual(len(persisted), 2)  # add + remove

    def test_restore_from_db(self):
        from agentos.db.models import AgentModel
        self.store.append(AgentModel(
            id="db1", name="FromDB", capabilities=["restore-test"],
            status="running", tenant_id="default", provider="", model="",
            description="", tags={}, config={}, agent_metadata={},
        ))
        count = _run(self.registry.restore_from_db())
        self.assertEqual(count, 1)
        agent = self.registry.get("db1")
        self.assertIsNotNone(agent)
        self.assertEqual(agent.name, "FromDB")

    def test_restore_skips_existing(self):
        from agentos.db.models import AgentModel
        meta = AgentMetadata(agent_id="dup1", name="AlreadyThere")
        self.registry._agents["dup1"] = meta
        self.store.append(AgentModel(
            id="dup1", name="FromDB_DUP", capabilities=[],
            status="created", tenant_id="default", provider="", model="",
            description="", tags={}, config={}, agent_metadata={},
        ))
        _run(self.registry.restore_from_db())
        self.assertEqual(self.registry.get("dup1").name, "AlreadyThere")

    def test_restore_without_repo_returns_zero(self):
        reg = AgentRegistry(repository=None)
        count = _run(reg.restore_from_db())
        self.assertEqual(count, 0)

    def test_restore_from_db_propagates_db_error(self):
        """restore_from_db() re-raises DB errors so runtime can decide to abort."""
        failing_repo = MagicMock()
        failing_repo.list_all = AsyncMock(side_effect=RuntimeError("DB unreachable"))
        reg = AgentRegistry(repository=failing_repo)
        with self.assertRaises(RuntimeError):
            _run(reg.restore_from_db())


# ---------------------------------------------------------------------------
# AuditLogger + repository wiring
# ---------------------------------------------------------------------------

class TestAuditLoggerWithRepository(unittest.TestCase):
    def test_log_without_repo_buffers_only(self):
        logger = AuditLogger(repository=None)
        logger.log(AuditEntry(action="x", tenant_id="t1"))
        self.assertEqual(logger.count, 1)

    def test_log_with_repo_calls_persist(self):
        mock_repo = MagicMock()
        mock_repo.add = AsyncMock()
        audit = AuditLogger(repository=mock_repo)
        called_with = []

        def capture_persist(entry: AuditEntry) -> None:
            called_with.append(entry)

        with patch.object(audit, "_persist_async", side_effect=capture_persist):
            audit.log(AuditEntry(action="agent:create", tenant_id="t2", user_id="u1"))

        self.assertEqual(audit.count, 1)
        self.assertEqual(len(called_with), 1)
        self.assertEqual(called_with[0].action, "agent:create")

    def test_query_filters_by_tenant(self):
        audit = AuditLogger()
        audit.log(AuditEntry(action="a", tenant_id="t1"))
        audit.log(AuditEntry(action="b", tenant_id="t2"))
        results = audit.query(tenant_id="t1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, "a")

    def test_buffer_overflow_trimmed(self):
        audit = AuditLogger(buffer_size=3)
        for i in range(5):
            audit.log(AuditEntry(action=f"a{i}"))
        self.assertEqual(audit.count, 3)
        self.assertEqual(audit.query()[0].action, "a2")


if __name__ == "__main__":
    unittest.main()
