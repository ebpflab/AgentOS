# P1: 测试覆盖 — 集成测试与缺失模块测试

## 背景

当前测试只覆盖 Registry、Lifecycle、MessageBus 三个模块（单元测试）。
缺失：API 路由测试、Workflow 执行测试、Security/RBAC 测试、Middleware 测试。
这些都是高风险代码路径，必须有测试保护重构。

## 相关文件

- `tests/unit/` — 已有单元测试
- `tests/conftest.py` — 公共 fixtures
- `src/agentos/api/routes/agents.py` — 待测 API
- `src/agentos/security/rbac.py` — 待测 RBAC
- `src/agentos/workflows/` — 待测 Workflows
- `src/agentos/middleware/` — 待测 Middleware

## 子任务

### 1. API 路由集成测试

文件：`tests/integration/test_api_agents.py`（新建）

使用 `httpx.AsyncClient` + FastAPI `TestClient` 或 `AsyncClient(app=app, base_url="http://test")`。

- [ ] 测试 `GET /agents` 返回空列表（无 Agent 时）
- [ ] 测试 `POST /agents` 创建 Agent（mock AgentFactory）
- [ ] 测试 `GET /agents/{id}` 找到和 404 两种情况
- [ ] 测试 `DELETE /agents/{id}` 成功和 404
- [ ] 测试 `POST /agents/{id}/start` 和 `stop`
- [ ] 测试租户隔离：tenant A 无法访问 tenant B 的 Agent（返回 404）
- [ ] 测试未认证请求在 `auth_enabled=True` 时返回 401

**验收：** `PYTHONPATH=src pytest tests/integration/test_api_agents.py` 全部通过。

### 2. RBAC 单元测试

文件：`tests/unit/test_rbac.py`（新建）

- [ ] 测试 ADMIN 角色拥有所有权限
- [ ] 测试 VIEWER 角色只有 READ 权限，无 CREATE/DELETE
- [ ] 测试 OPERATOR 角色可以 run workflow 但不能 admin
- [ ] 测试自定义 policy 授权
- [ ] 测试 `require_permission` 在无权限时抛出 `AccessDeniedError`
- [ ] 测试 AGENT 角色权限边界

**验收：** `PYTHONPATH=src pytest tests/unit/test_rbac.py` 全部通过。

### 3. Workflow 执行单元测试

文件：`tests/unit/test_workflows.py`（新建）

Mock 所有 Agent 调用（`AsyncMock`）。

**PipelineWorkflow：**
- [ ] 测试两步 pipeline，第一步输出正确传入第二步
- [ ] 测试某步失败后 pipeline 提前终止，result 包含 error

**ResearchWorkflow：**
- [ ] 测试并行 researcher 均成功，synthesizer 接收所有结果
- [ ] 测试部分 researcher 超时，workflow 继续（用可用结果合成）

**EscalationWorkflow：**
- [ ] 测试第一个 Agent 成功解决，不继续升级
- [ ] 测试第一个失败，第二个成功
- [ ] 测试全部失败，返回 `needs_human_review=True`

**验收：** `PYTHONPATH=src pytest tests/unit/test_workflows.py` 全部通过。

### 4. Middleware 单元测试

文件：`tests/unit/test_middleware.py`（新建）

- [ ] **BudgetMiddleware：** 预算不足时拒绝调用，不消耗 token
- [ ] **BudgetMiddleware：** 调用成功后正确扣减 token
- [ ] **AuditMiddleware：** 调用后 AuditLogger 收到正确的 action 记录
- [ ] **AuditMiddleware：** 调用失败时 outcome 为 `failure`
- [ ] **LoggingMiddleware：** 记录 operation 和 duration
- [ ] **AuthMiddleware：** 有效 token 时设置正确的 tenant context
- [ ] **AuthMiddleware：** 无效 token 时抛出 `AuthenticationError`

**验收：** `PYTHONPATH=src pytest tests/unit/test_middleware.py` 全部通过。

### 5. 改善 conftest.py

文件：`tests/conftest.py`

- [ ] 新增 `mock_runtime` fixture：返回有 mock subsystem 的 AgentOSRuntime
- [ ] 新增 `mock_agent` fixture：返回 ManagedAgent（不需要真实 MAF 连接）
- [ ] 新增 `test_user_info` fixture：返回 ADMIN 权限的 UserInfo
- [ ] 新增 `test_app` fixture：返回配置好的 FastAPI app（用于 API 测试）

**验收：** 以上 fixtures 可被 test 文件正确使用。

### 6. 配置 pytest 覆盖率报告

文件：`pyproject.toml`

- [ ] 新增 `[tool.pytest.ini_options]` 中 `addopts = "--cov=src/agentos --cov-report=term-missing"`
- [ ] 确认 `pytest-cov` 在 dev 依赖中

**验收：** `PYTHONPATH=src pytest tests/` 输出覆盖率报告，覆盖率 > 60%。
