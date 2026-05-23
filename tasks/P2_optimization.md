# P2: 性能优化、缓存、API 版本化

## 背景

以下优化项在 P0/P1 完成后执行，不阻塞功能上线。

---

## 子任务

### 1. Registry 能力搜索索引

**问题：** `find_by_capability()` 是 O(n×m) 线性扫描。

文件：`src/agentos/kernel/registry.py`

- [ ] 新增 `_capability_index: dict[str, set[str]]` — capability → agent_id set 的倒排索引
- [ ] `register()` 时更新索引（每个 capability 对应添加 agent_id）
- [ ] `unregister()` 时从索引移除
- [ ] `find_by_capability()` 改为直接查索引（O(1)）
- [ ] 确保索引与主数据一致（写操作同时更新两处）

**验收：** `find_by_capability()` 单元测试通过；1000 个 Agent 时查询耗时可接受。

### 2. RouterAgent 缓存失效

**问题：** `RouterAgent` 缓存 Agent 列表无失效策略，Registry 变化后路由错误。

文件：`src/agentos/agents/router.py`

- [ ] 订阅 `agent.registered` 和 `agent.unregistered` 事件
- [ ] 事件触发时清空对应 capability 的缓存
- [ ] 缓存条目增加 TTL（默认 60 秒）：超时强制重新查询

**验收：** Agent 注销后，RouterAgent 缓存在下次请求时失效，不路由到已注销 Agent。

### 3. API 版本前缀

**问题：** 当前所有路由无版本前缀（`/agents`），无法做 breaking change 的版本演进。

文件：`src/agentos/api/server.py`，`src/agentos/api/routes/`

- [ ] 将所有路由前缀从 `/agents` 改为 `/v1/agents`
- [ ] 同理：`/v1/workflows`、`/v1/metrics`、`/v1/auth`
- [ ] 保留 `/health`、`/metrics`（Prometheus）不加版本前缀
- [ ] 更新 `configs/agentos.yaml` 中的示例 URL（如有）

**验收：** `GET /v1/agents` 返回正常；`GET /agents` 返回 404。

### 4. API 列表端点分页

**问题：** `GET /v1/agents` 无分页，Agent 数量大时返回全量数据。

文件：`src/agentos/api/routes/agents.py`

- [ ] 添加 query 参数：`limit: int = 50`（最大 200）、`offset: int = 0`
- [ ] 响应体增加 `total` 字段：`{"items": [...], "total": 123, "limit": 50, "offset": 0}`
- [ ] Registry 的 `list_all()` 支持 `limit`/`offset` 参数（内存模式：切片；DB 模式：SQL LIMIT/OFFSET）

**验收：** `GET /v1/agents?limit=10&offset=0` 返回前 10 条和总数。

### 5. EventBus 背压配置化

**问题：** EventBus 每个订阅者队列大小硬编码为 1000，高吞吐时可能 OOM。

文件：`src/agentos/kernel/events.py`

- [ ] `EventBus.__init__` 新增 `max_queue_size: int = 1000` 参数
- [ ] 在 `subscribe()` 时使用配置值创建队列
- [ ] 队列满时不直接 block，改为丢弃最旧消息并输出 warning 日志（或按 policy 处理）
- [ ] 在 `configs/agentos.yaml` 新增：
  ```yaml
  events:
    max_queue_size: 1000
  ```

**验收：** 配置不同 queue size 后行为符合预期；队列满时有日志告警。

### 6. 健康检查增强

**问题：** 当前 `/health` 只返回 agent count，无子系统状态。

文件：`src/agentos/api/server.py` 或 `src/agentos/api/routes/`

- [ ] 新增 `/health/ready`（readiness：DB 连接、MAF 连接是否就绪）
- [ ] 新增 `/health/live`（liveness：进程存活即可）
- [ ] `/health/ready` 检查：DB 可查询、至少一个 Provider 可用
- [ ] 任一检查失败时返回 HTTP 503

**验收：** Kubernetes liveness/readiness probe 可配置对应端点。
