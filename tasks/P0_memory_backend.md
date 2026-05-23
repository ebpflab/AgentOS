# P0: Memory 后端实现（PostgreSQL）

## 背景

`src/agentos/memory/store.py` 只定义了 `MemoryStore` Protocol，没有任何后端实现。
`MemoryContextProvider.after_run()` 是空存根。
导致 Agent 无法持久化记忆，长会话无法工作。

## 相关文件

- `src/agentos/memory/store.py` — Protocol 定义
- `src/agentos/memory/context_providers.py` — MAF ContextProvider 接入
- `src/agentos/memory/shared_kb.py` — 命名空间作用域知识库
- `src/agentos/db/` — 数据库层

## 实现目标

- PostgreSQL 后端实现 `MemoryStore` Protocol
- 支持 TTL 过期清理
- 支持基于文本的搜索（向量搜索作为 P1 延后）
- 实现 `MemoryContextProvider.after_run()`，将 Agent 输出写回记忆

## 子任务

### 1. 新增 memory_entries 数据库 model

字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | uuid (PK) | 主键 |
| `namespace` | str | 例如 `{tenant_id}/shared/{key}` |
| `key` | str | 业务 key |
| `value` | JSON | 存储内容 |
| `tenant_id` | str | 租户 |
| `agent_id` | str \| null | 关联 Agent（可空，shared 时为空） |
| `expires_at` | datetime \| null | TTL 过期时间 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

- [ ] 在 `src/agentos/db/models.py` 中新增 `MemoryEntry` model
- [ ] 添加 `(namespace, key)` 联合唯一索引
- [ ] 添加 `expires_at` 索引（用于 TTL 清理任务）

**验收：** model 定义完整，alembic 可识别。

### 2. 生成 migration

```bash
alembic revision --autogenerate -m "add_memory_entries"
alembic upgrade head
```

### 3. 实现 PostgresMemoryStore

文件：`src/agentos/memory/backends/postgres.py`（新建）

```python
class PostgresMemoryStore:
    """PostgreSQL 实现 MemoryStore Protocol"""

    def __init__(self, session_factory): ...

    async def get(self, namespace: str, key: str) -> Any | None
    async def set(self, namespace: str, key: str, value: Any, ttl: int | None = None) -> None
    async def delete(self, namespace: str, key: str) -> bool
    async def list_keys(self, namespace: str, prefix: str = "") -> list[str]
    async def search(self, namespace: str, query: str, limit: int = 10) -> list[dict]
```

实现要求：

- [ ] `set()` 使用 PostgreSQL UPSERT（`ON CONFLICT (namespace, key) DO UPDATE`）
- [ ] `get()` 自动过滤 `expires_at < NOW()` 的记录（视作不存在）
- [ ] `ttl` 参数为秒数，`None` 表示永不过期
- [ ] `search()` 使用 PostgreSQL `to_tsvector` 全文搜索（限定 namespace）
- [ ] `list_keys()` 支持 prefix 过滤（`LIKE 'prefix%'`）

**验收：** 所有方法实现完整，行为符合接口约定。

### 4. 实现 TTL 清理任务

文件：`src/agentos/memory/backends/postgres.py` 同文件追加

- [ ] 新增 `async def cleanup_expired(self) -> int` — 删除所有过期记录，返回删除数量
- [ ] 在 `AgentOSRuntime` 启动时注册定时任务（每 5 分钟运行一次 `cleanup_expired`）
  - 使用 `asyncio.create_task` + 循环 + `asyncio.sleep`
  - 在 runtime 停止时取消任务

**验收：** 过期记录被定期清理。

### 5. 实现 MemoryContextProvider.after_run()

文件：`src/agentos/memory/context_providers.py`

- [ ] 阅读 MAF `ContextProvider.after_run` 接口签名（参考 MAF 文档或现有 `before_run`）
- [ ] 实现逻辑：从 Agent 的本次运行结果中提取要存储的内容（消息、状态等），调用 `store.set()` 写入
- [ ] 命名空间格式：`{tenant_id}/{agent_id}/history`
- [ ] 存储格式：列表形式追加最近 N 条消息（N 默认 50，可配）

**验收：** Agent 运行后，对应 namespace 下的 `history` key 包含本次交互。

### 6. 在 Runtime 中接入

文件：`src/agentos/kernel/runtime.py`

- [ ] 启动时实例化 `PostgresMemoryStore`（依赖 DB session_factory）
- [ ] 暴露为 `runtime.memory_store` 属性
- [ ] `AgentFactory` 创建 Agent 时，自动附加 `MemoryContextProvider(store=runtime.memory_store, ...)`

**验收：** 新创建的 Agent 自带 memory provider，无需额外配置。

### 7. 编写单元测试

文件：`tests/unit/test_postgres_memory.py`（新建）

- [ ] 测试 set + get 基本流程
- [ ] 测试 TTL 过期行为
- [ ] 测试 list_keys + prefix
- [ ] 测试 search 全文搜索
- [ ] 测试 cleanup_expired

可用 SQLite + simplified 实现，或 testcontainers 启 PostgreSQL，二选一。

**验收：** `PYTHONPATH=src pytest tests/unit/test_postgres_memory.py` 全部通过。
