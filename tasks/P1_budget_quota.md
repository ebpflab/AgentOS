# P1: Budget 与 Quota 联动

## 背景

当前 `BudgetManager`（按 Agent 扣减 Token）与 `QuotaManager`（定义租户级限额）完全独立，
`BudgetMiddleware` 只检查 Agent 级预算，不检查租户配额。
这导致单个租户可以通过多个 Agent 绕过总用量限制。

## 相关文件

- `src/agentos/resources/budget.py` — BudgetManager
- `src/agentos/resources/quota.py` — QuotaManager
- `src/agentos/resources/rate_limiter.py` — RateLimiter（参考）
- `src/agentos/middleware/budget_mw.py` — BudgetMiddleware（MAF 中间件）
- `src/agentos/config.py` — ResourcesConfig

## 子任务

### 1. 在 BudgetManager 中新增租户级聚合统计

文件：`src/agentos/resources/budget.py`

- [ ] 新增 `_tenant_usage: dict[str, int]` — 按 tenant_id 聚合的 token 消耗
- [ ] 修改 `consume()` 方法：在扣减 Agent 预算后同时更新 `_tenant_usage[tenant_id]`
  - `consume(agent_id, tokens, tenant_id=None)` — tenant_id 新增为可选参数
- [ ] 新增方法 `get_tenant_usage(tenant_id: str) -> int`
- [ ] 新增方法 `reset_tenant_usage(tenant_id: str) -> None`（用于账单周期重置）

**验收：** 多个 Agent 消耗后，`get_tenant_usage()` 返回正确累计值。

### 2. 在 BudgetMiddleware 中加入租户配额检查

文件：`src/agentos/middleware/budget_mw.py`

- [ ] `BudgetMiddleware` 构造函数新增 `quota_manager: QuotaManager | None = None` 参数
- [ ] 在 `wrap_call()` 前置检查中（消费前）：
  1. 先检查 Agent 级预算（现有逻辑）
  2. 再检查租户级每日/每月 Token 配额（通过 `quota_manager.get_quota(tenant_id)` 和 `budget_manager.get_tenant_usage(tenant_id)` 对比）
- [ ] 超过租户配额时抛出 `BudgetExceededError`，消息中注明 `reason="tenant_quota_exceeded"`

**验收：** 租户总 Token 超过 `max_tokens_per_day` 后，所有该租户的 Agent 调用均被拒绝。

### 3. 修复 BudgetMiddleware 中 usage 提取脆弱性

文件：`src/agentos/middleware/budget_mw.py`

- [ ] 读取当前 `_extract_usage()` 或类似方法的实现
- [ ] 当前可能有多个 try/except 猜测字段位置，改为：
  - 定义一个 `_safe_get_usage(response) -> int` 方法
  - 按优先级尝试标准字段（`response.usage.total_tokens`，`response.usage.input_tokens + response.usage.output_tokens`，`getattr` 方式）
  - 全部失败时返回 0 并 `logger.warning("Could not extract token usage from response")`
  - 不再使用嵌套 try/except

**验收：** 代码逻辑清晰，无嵌套 try/except 猜测。

### 4. 在 Runtime 中注入 QuotaManager 到 BudgetMiddleware

文件：`src/agentos/kernel/runtime.py`

- [ ] 确认 `QuotaManager` 实例在 runtime 中已初始化（或新增初始化）
- [ ] 创建 `BudgetMiddleware` 时传入 `quota_manager=self.quota_manager`

**验收：** 运行时 BudgetMiddleware 获得 QuotaManager 实例。

### 5. 新增配额接近阈值告警

文件：`src/agentos/resources/budget.py` 或 `quota.py`

- [ ] 当租户 token 使用量超过配额的 80% 时，发布事件 `tenant.quota.warning`
- [ ] 事件 payload：`{"tenant_id": ..., "usage_percent": ..., "quota_type": "tokens_per_day"}`
- [ ] 使用 `EventBus` 发布（需注入 EventBus 或通过 callback）

**验收：** 使用量到达 80% 时 EventBus 收到 `tenant.quota.warning` 事件。

### 6. 编写单元测试

文件：`tests/unit/test_budget_quota.py`（新建）

- [ ] 测试 `consume()` 正确更新租户累计
- [ ] 测试租户超额时 middleware 拒绝请求
- [ ] 测试 80% 阈值时触发事件
- [ ] 测试 `reset_tenant_usage()` 清零

**验收：** `PYTHONPATH=src pytest tests/unit/test_budget_quota.py` 全部通过。
