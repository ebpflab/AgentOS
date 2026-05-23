# P1: Observability — Prometheus Metrics 接入

## 背景

`src/agentos/observability/` 有 OpenTelemetry 和 Prometheus 的基础设施，但未接入实际代码路径：
- Middleware 中有 timing 记录但未 emit metrics
- EventBus/MessageBus 吞吐量未度量
- Agent 运行耗时、Token 消耗无 Prometheus metrics 暴露

## 相关文件

- `src/agentos/observability/` — 现有 metrics 定义（先读取确认已有什么）
- `src/agentos/middleware/logging_mw.py` — 有 timing，需接入 metrics
- `src/agentos/middleware/budget_mw.py` — Token 消耗，需接入 metrics
- `src/agentos/api/server.py` — 需添加 `/metrics` 端点
- `src/agentos/kernel/events.py` — 事件吞吐量
- `src/agentos/communication/bus.py` — 消息吞吐量

## 子任务

### 1. 读取并确认现有 observability 基础设施

- [ ] 读取 `src/agentos/observability/` 所有文件
- [ ] 确认已有哪些 Counter/Histogram/Gauge 定义
- [ ] 确认 prometheus_client 是否已在依赖中

### 2. 定义核心 Metrics（如未存在）

文件：`src/agentos/observability/metrics.py`（新建或补充）

需要的 metrics：

```python
# Agent 调用
agent_runs_total = Counter("agentos_agent_runs_total", "...", ["agent_id", "tenant_id", "status"])
agent_run_duration_seconds = Histogram("agentos_agent_run_duration_seconds", "...", ["agent_id"])

# Token 消耗
token_usage_total = Counter("agentos_token_usage_total", "...", ["agent_id", "tenant_id", "token_type"])

# 消息总线
messages_sent_total = Counter("agentos_messages_sent_total", "...", ["message_type"])
message_queue_size = Gauge("agentos_message_queue_size", "...", ["agent_id"])

# 系统
active_agents = Gauge("agentos_active_agents_total", "...", ["tenant_id"])
```

- [ ] 定义以上 metrics（或确认已存在等效定义）
- [ ] 提供统一 `get_metrics()` 函数返回 metrics 注册表

### 3. 在 LoggingMiddleware 中 emit 耗时 metrics

文件：`src/agentos/middleware/logging_mw.py`

- [ ] 在 operation 完成后调用 `agent_run_duration_seconds.observe(duration)`
- [ ] 在 operation 完成后调用 `agent_runs_total.inc(labels={"status": "success" / "error"})`
- [ ] 确保 metrics 对象通过参数或 module-level singleton 传入（不要导致循环依赖）

**验收：** Agent 运行后，对应 metrics counter 增加。

### 4. 在 BudgetMiddleware 中 emit token metrics

文件：`src/agentos/middleware/budget_mw.py`

- [ ] 在 `_safe_get_usage()` 提取到 usage 后，调用 `token_usage_total.inc(amount, labels={...})`

**验收：** Token 消耗后，对应 counter 增加。

### 5. 添加 /metrics 端点

文件：`src/agentos/api/server.py`

- [ ] 新增路由 `GET /metrics`，返回 Prometheus text format
- [ ] 使用 `prometheus_client.generate_latest()` 生成内容
- [ ] 响应 Content-Type: `text/plain; version=0.0.4`
- [ ] 该端点**不需要**认证（Prometheus scraper 无 token）

**验收：** `curl http://localhost:8000/metrics` 返回 Prometheus 格式文本。

### 6. 在 active_agents Gauge 中接入 Registry 事件

文件：`src/agentos/kernel/registry.py` 或 `src/agentos/observability/metrics.py`

- [ ] 订阅 `agent.registered` 和 `agent.unregistered` 事件
- [ ] 事件处理中更新 `active_agents` gauge（按 tenant_id 分组）

**验收：** Agent 注册/注销后，gauge 值变化正确。

### 7. 配置说明

文件：`configs/agentos.yaml`

- [ ] 确认 `observability.metrics.enabled` 配置项存在
- [ ] 添加注释说明如何配置 Prometheus scrape

**验收：** 配置文件中 metrics 相关配置有清晰注释。
