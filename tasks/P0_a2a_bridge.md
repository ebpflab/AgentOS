# P0: A2A Bridge — 跨 Agent 通信实现

## 背景

`src/agentos/communication/a2a_bridge.py` 当前是骨架实现：
- `forward_message()` 只有 TODO 注释，消息实际不会被转发
- 远程 Agent 注册为本地代理但无法通信
- 导致所有跨服务的 Agent 调用静默失败

## 相关文件

- `src/agentos/communication/a2a_bridge.py` — 主要修改目标
- `src/agentos/communication/protocols.py` — AgentMessage 数据结构
- `src/agentos/communication/bus.py` — 本地 MessageBus（参考实现）
- `src/agentos/config.py` — 查看是否有 A2A 相关配置节

## 实现目标

实现基于 HTTP 的 A2A 消息转发（同步 request-reply 模式），满足以下约束：
- 使用 `httpx.AsyncClient` 做 HTTP 调用（已在依赖中或新增）
- 远程端点格式：`{base_url}/agents/{agent_id}/messages`
- 消息序列化：`AgentMessage.to_dict()` → JSON

## 子任务

### 1. 确认当前 A2ABridge 骨架结构

- [ ] 读取 `src/agentos/communication/a2a_bridge.py` 全文
- [ ] 记录：已有哪些方法、哪些是存根、`_remote_agents` 字典结构
- [ ] 读取 `src/agentos/communication/protocols.py`，确认 `AgentMessage.to_dict()` / `from_dict()` 已实现

### 2. 在配置中新增 A2A 节（如不存在）

文件：`src/agentos/config.py`，`configs/agentos.yaml`

- [ ] `A2AConfig` 新增字段：
  ```python
  enabled: bool = False
  timeout_seconds: float = 30.0
  retry_attempts: int = 3
  ```
- [ ] `configs/agentos.yaml` 新增示例：
  ```yaml
  a2a:
    enabled: false
    timeout_seconds: 30
    retry_attempts: 3
  ```

### 3. 实现 forward_message()

文件：`src/agentos/communication/a2a_bridge.py`

```python
async def forward_message(self, message: AgentMessage) -> AgentMessage | None:
    """转发消息到远程 Agent，返回响应或 None（fire-and-forget）"""
```

- [ ] 从 `self._remote_agents` 取得目标 Agent 的 `base_url`
- [ ] 使用 `httpx.AsyncClient` POST 到 `{base_url}/agents/{agent_id}/messages`
- [ ] 请求 body 为 `message.to_dict()` JSON
- [ ] 包含重试逻辑（最多 `config.a2a.retry_attempts` 次，指数退避）
- [ ] 超时使用 `config.a2a.timeout_seconds`
- [ ] 收到响应后反序列化为 `AgentMessage.from_dict(response.json())`
- [ ] 网络错误时记录日志并抛出自定义异常 `A2AForwardError`

**验收：** 单元测试中 mock httpx 后，`forward_message()` 正确序列化请求并返回反序列化结果。

### 4. 在 API 层添加消息接收端点

文件：`src/agentos/api/routes/agents.py`（或新建 `messages.py`）

- [ ] 新增路由：`POST /agents/{agent_id}/messages`
- [ ] 请求体为 `AgentMessage` JSON（使用 `AgentMessage.from_dict()`）
- [ ] 将消息投递到本地 `MessageBus`（通过 `runtime.message_bus.send()`）
- [ ] 返回处理结果（同步等待回复，超时 30s）或 `202 Accepted`（异步模式）

**验收：** 可通过 curl/httpx 向该端点 POST 消息，本地 Agent 收到并处理。

### 5. 为 A2AForwardError 添加异常类

文件：`src/agentos/exceptions.py`（或已有异常文件）

- [ ] 新增 `class A2AForwardError(AgentOSError): ...`
- [ ] 包含字段：`agent_id`, `reason`

### 6. 编写单元测试

文件：`tests/unit/test_a2a_bridge.py`（新建）

- [ ] 测试 `forward_message()` 正常路径（mock httpx 返回 200）
- [ ] 测试网络超时抛出 `A2AForwardError`
- [ ] 测试重试逻辑（前两次失败，第三次成功）
- [ ] 测试目标 Agent 未注册时的错误处理

**验收：** `PYTHONPATH=src pytest tests/unit/test_a2a_bridge.py` 全部通过。
