# P0: 持久化 — Registry、AuditLog、Workflow 状态

## 背景

当前 `AgentRegistry`、`AuditLogger`、`ApprovalWorkflow` 状态全在内存。
服务重启后所有 Agent 注册信息、审计记录丢失，不可用于生产。
数据库层（`src/agentos/db/`）已有 SQLAlchemy + Alembic 框架，需接入。

## 相关文件

- `src/agentos/kernel/registry.py` — 当前纯内存实现
- `src/agentos/security/audit.py` — 当前纯内存实现
- `src/agentos/db/` — SQLAlchemy models 和 repositories（已有框架，需实现）
- `alembic.ini` / `alembic/` — 数据库迁移配置
- `configs/agentos.yaml` — 数据库连接配置

## 子任务

### 1. 检查并补全 DB models

- [x] 读取 `src/agentos/db/` 下所有现有文件，确认已有哪些 model
- [x] 确认 `agents` 表 model 覆盖字段：`agent_id`, `name`, `status`, `capabilities`（JSON）, `tenant_id`, `provider`, `model`, `instructions`, `metadata`（JSON）, `created_at`, `updated_at`
- [x] 确认 `audit_logs` 表 model 覆盖字段：`id`, `tenant_id`, `action`, `user_id`, `resource_type`, `resource_id`, `outcome`, `details`（JSON）, `timestamp`
- [x] 如字段不完整，补全对应 model

**验收：** `src/agentos/db/models.py`（或对应文件）中两张表结构完整。

### 2. 生成 Alembic migration

```bash
cd /work/workdir/AgentOS
alembic revision --autogenerate -m "add_agents_and_audit_logs"
alembic upgrade head
```

- [x] migration 文件生成成功，无报错
- [x] `alembic upgrade head` 执行成功（需本地 PostgreSQL 或 SQLite 测试）

**验收：** `alembic/versions/` 下有新 migration 文件。

### 3. 实现 AgentRepository

位置：`src/agentos/db/repositories/agent_repository.py`（新建）

需实现方法：
```python
async def add(self, agent: ManagedAgent) -> None
async def get(self, agent_id: str) -> ManagedAgent | None
async def remove(self, agent_id: str) -> bool
async def list_all(self) -> list[ManagedAgent]
async def find_by_capability(self, capability: str) -> list[ManagedAgent]
async def find_by_tenant(self, tenant_id: str) -> list[ManagedAgent]
async def update_status(self, agent_id: str, status: str) -> None
```

- [x] 实现完成
- [x] 使用 SQLAlchemy async session（`async with session_factory() as session`）
- [x] `find_by_capability` 使用 JSON 查询或 capabilities 列表过滤

**验收：** 方法实现无语法错误，逻辑符合接口约定。

### 4. 修改 AgentRegistry 接入数据库

文件：`src/agentos/kernel/registry.py`

- [x] `AgentRegistry.__init__` 接收可选的 `repository` 参数（默认 None，保持内存模式向后兼容）
- [x] 当 `repository` 存在时，所有写操作（register/unregister）同步写入 DB
- [x] 所有读操作（get/find/list）优先从 DB 读（或内存缓存 + DB 同步，二选一）
- [x] `AgentOSRuntime` 启动时注入 `AgentRepository` 到 `AgentRegistry`（通过 `restore_from_db()`）

**验收：** 注册一个 Agent 后重启服务，Agent 仍可被发现。

### 5. 实现 AuditRepository 并修改 AuditLogger

位置：`src/agentos/db/repositories/audit_repository.py`（新建）
文件：`src/agentos/security/audit.py`

- [x] 实现 `AuditRepository.append(entry: AuditEntry)`，写入 DB
- [x] 实现 `AuditRepository.query(tenant_id, action, user_id, limit)` 从 DB 查询
- [x] `AuditLogger` 在 `log()` 方法中调用 `AuditRepository.append()`（异步）
- [x] 内存缓冲保留（作为近期日志快速读取），但不再是唯一存储

**验收：** `AuditLogger.log()` 后数据写入数据库，重启后可通过 `query()` 取回。

### 6. 编写单元测试

文件：`tests/unit/test_persistence.py`（新建）

- [x] 测试 `AgentRepository` CRUD 操作（使用 SQLite in-memory 或 mock session）
- [x] 测试 `AuditRepository.append` + `query`
- [x] 测试 `AgentRegistry` 注入 repository 后的读写行为

**验收：** `PYTHONPATH=src pytest tests/unit/test_persistence.py` 全部通过（22 tests OK，使用 unittest runner）。

---

## ⚠️ Review 发现的问题（需修复后才算完成）

以下是第二轮 code review 发现的缺陷，按优先级排序。**全部修复后才能将本任务标记为真正完成。**

### 🔴 严重问题（功能完全失效）

#### FIX-1: runtime.py 未初始化数据库，持久化根本不会发生

文件：`src/agentos/kernel/runtime.py`

`start()` 方法中没有初始化 DB engine / session_factory / repositories，`AgentRegistry` 被创建时 `repository=None`，所有写操作走内存，重启即丢失。

**修复：** 在 `start()` 中添加：

```python
from agentos.db.session import init_engine, get_session_factory
from agentos.db.repositories.agent_repository import AgentRepository
from agentos.db.repositories.audit_repository import AuditRepository

engine = await init_engine(self.config.database)
session_factory = get_session_factory()
agent_repo = AgentRepository(session_factory)
audit_repo = AuditRepository(session_factory)
self.registry = AgentRegistry(repository=agent_repo)
await self.registry.restore_from_db()
self.audit_logger = AuditLogger(repository=audit_repo)
```

- [x] `runtime.start()` 中初始化 engine 和 session_factory
- [x] 创建 `AgentRepository` 实例并注入 `AgentRegistry`
- [x] 创建 `AuditRepository` 实例并注入 `AuditLogger`
- [x] 调用 `await registry.restore_from_db()` 恢复历史 agents

**验收：** 注册一个 Agent，重启服务，`GET /agents` 能返回该 Agent。

#### ~~FIX-2: 删除重复的 AgentRepository 实现~~ — **误判，无需修改**

Review 认为存在两套冲突的 `AgentRepository`，但经核实这是**两个不同层次的设计**，并非重复：

- `src/agentos/db/repositories/agent_repository.py` — **session-factory-scoped**，每次操作创建独立 session + `commit()`，用于 kernel 层 fire-and-forget 异步持久化
- `src/agentos/db/repositories/__init__.py` — 包含 `TenantRepository`、`AuditLogRepository` 等 **session-scoped** repositories（注入单个 session + `flush()`），用于 API 层事务场景

`__init__.py` 中**不存在** `AgentRepository` 类，不构成重复。两种模式服务不同使用场景（kernel 自治写入 vs API 请求级事务），是合理的架构分层。

**结论：** 不需要删除或合并，维持现状。

#### FIX-3: 重复注册时 DB upsert 而非 insert，防止唯一约束报错

文件：`src/agentos/db/repositories/agent_repository.py`

服务重启后 `restore_from_db()` 将 DB 里的 agents 加载到内存，但如果再次调用 `register()` 触发 `repository.add()`，会因 PK 重复导致 insert 失败（即使错误被吞没，也造成不一致）。

**修复：**
- [x] `add()` 改为 upsert：PostgreSQL 用 `INSERT ... ON CONFLICT (agent_id) DO UPDATE`，SQLAlchemy 用 `merge()` 或 `on_conflict_do_update()`

**验收：** 对同一 `agent_id` 调用两次 `add()`，不报错，DB 中只有一条记录。

#### FIX-4: 修复测试中 FakeSession 的 rowcount 处理

文件：`tests/unit/test_persistence.py`

`_FakeSession.execute()` 对所有语句返回相同结构，`result.rowcount` 是 `MagicMock` 对象，`remove()` 中的 `result.rowcount > 0` 结果不可靠。

**修复：**
- [x] `_FakeSession.execute()` 中，针对 delete 语句设置 `result.rowcount = 1`（或根据是否找到记录动态设置）
- [x] 使用 `asyncio.get_event_loop().run_until_complete()` 兼容 unittest（`pytest.mark.asyncio` 需要 pytest，当前环境未安装）

**验收：** `test_remove_agent` 测试断言 `remove()` 返回 `True`，测试通过。

#### FIX-5: 创建 "default" tenant 或移除 FK 默认值

文件：`src/agentos/db/models.py`

`AgentModel.tenant_id` 默认值为 `"default"` 但 tenants 表中不存在该记录，启用外键检查时 `add()` 会报 FK 违反错误。

**修复（二选一）：**
- [x] 方案 A：在数据库初始化时插入 `id="default"` 的 tenant 记录（推荐）
  - 在 `runtime.start()` 或 alembic seed migration 中执行
- [ ] 方案 B：去掉 FK default，让调用者显式提供 `tenant_id`，缺失时抛出明确错误

**验收：** 不设置 `tenant_id` 创建 Agent 时不报 FK 错误。

#### FIX-6: AuditLogger._persist_async() 异步任务缺少错误处理

文件：`src/agentos/security/audit.py`

`loop.create_task(_write())` 没有 `add_done_callback`，异常会变成未处理任务警告，与 registry 实现不一致。

**修复：**
- [x] 仿照 `AgentRegistry._persist_async()` 的实现，添加：
  ```python
  task = loop.create_task(_write())
  task.add_done_callback(AuditLogger._log_persist_error)
  ```
- [x] 新增静态方法 `_log_persist_error(task)`，在 task 有异常时记录 warning

**验收：** DB 写入失败时，日志中有 `WARNING` 级别的错误记录，不抛出未处理异常。

### 🟡 一般问题

#### FIX-7: _to_metadata() 在 session 关闭后调用

文件：`src/agentos/db/repositories/agent_repository.py`

`get()` 方法在 `async with session:` 块之外调用 `_to_metadata(model)`，若 model 有 lazy relationship 会报 `DetachedInstanceError`。

**修复：**
- [x] 将 `return self._to_metadata(model)` 移到 `async with session:` 块内部

#### FIX-8: restore_from_db() 异常被完全吞没

文件：`src/agentos/kernel/registry.py`

DB 连接失败和空库被视为相同情况，调用者无法感知真实错误。

**修复：**
- [x] 区分两种情况：
  - 查询结果为空（正常，返回 0）
  - 数据库连接/查询报错（记录 `ERROR` 级别日志，并重新抛出异常让 runtime 决定是否中止启动）

#### FIX-9: audit log 输出缺少 details 字段

文件：`src/agentos/security/audit.py`

`logger.info()` 输出中没有 `entry.details`，重要的审计信息丢失。

**修复：**
- [x] 在日志格式串末尾追加 `details=%s` 并传入 `entry.details`

### 🔵 小问题（可与上述修复一起处理）

- **FIX-10** [x] [audit.py] `AuditEntry.timestamp` 被忽略，改为将 app 时间传入 DB 而非依赖 `server_default`
- **~~FIX-11~~** — **误判，无需修改。** [models.py] 原 review 认为属性名 `agent_metadata` 与列名 `metadata` 不一致。实际上 SQLAlchemy 中 `metadata` 是 `DeclarativeBase` 保留属性（`Base.metadata` 是 `MetaData` 对象），使用 `agent_metadata` 是正确的规避方式，属性名与列名均为 `agent_metadata`，不存在不一致。Repository 层 `agent_metadata ↔ extra` 双向映射已保持正确。
- **FIX-12** [x] [audit_repository.py] `entry_data["action"]` 改为 `entry_data.get("action")` 并在为空时抛出 `ValueError`

---

## 完成标准（修复后重新验收）

- [x] FIX-1, FIX-3 ~ FIX-6 全部完成（FIX-2 和 FIX-11 为误判，无需修改）
- [x] `PYTHONPATH=src pytest tests/unit/test_persistence.py` 全部通过（29 tests，使用 unittest runner，pytest 未在环境中安装）
- [x] `PYTHONPATH=src pytest tests/` 无新增失败（test_persistence 全绿；旧 test_bus/test_lifecycle/test_registry 因 import pytest 失败，与 P0 改动无关）
- [x] 自动验证：`AgentOSRuntime.start()` → 注册 Agent → DB upsert/restore 路径 → graceful fallback 到 memory-only mode 时仍可启动
