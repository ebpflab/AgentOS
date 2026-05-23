# P0: 审批工作流持久化

## 背景

`src/agentos/workflows/approval.py` 中待审批状态存储在内存字典：
```python
self._pending_approvals: dict[str, asyncio.Event] = {}
```
服务重启后所有待审批工单丢失，审批者无法完成已提交的审批请求。

## 相关文件

- `src/agentos/workflows/approval.py` — 主要修改目标
- `src/agentos/db/` — 数据库层（已有框架）
- `src/agentos/workflows/templates.py` — BaseWorkflow 基类

## 数据模型

待审批记录需持久化的字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `workflow_id` | str (PK) | 工作流唯一 ID |
| `tenant_id` | str | 租户隔离 |
| `status` | enum | PENDING / APPROVED / REJECTED |
| `content` | JSON | 待审批内容 |
| `feedback` | str \| null | 审批意见 |
| `created_at` | datetime | 创建时间 |
| `decided_at` | datetime \| null | 决策时间 |
| `expires_at` | datetime \| null | 超时时间 |

## 子任务

### 1. 新增 approval_requests 数据库 model

文件：`src/agentos/db/models.py`（或对应 models 文件）

- [ ] 新增 `ApprovalRequest` SQLAlchemy model，字段见上表
- [ ] `status` 使用 SQLAlchemy `Enum` 类型
- [ ] 设置 `tenant_id` + `created_at` 的联合索引

**验收：** model 定义无语法错误，Alembic 可识别。

### 2. 生成并应用 migration

```bash
alembic revision --autogenerate -m "add_approval_requests"
alembic upgrade head
```

- [ ] migration 文件生成成功
- [ ] `alembic upgrade head` 无报错

### 3. 实现 ApprovalRepository

文件：`src/agentos/db/repositories/approval_repository.py`（新建）

需实现方法：
```python
async def create(self, workflow_id: str, tenant_id: str, content: dict, expires_at: datetime | None) -> None
async def get(self, workflow_id: str) -> dict | None
async def decide(self, workflow_id: str, approved: bool, feedback: str) -> bool
async def list_pending(self, tenant_id: str) -> list[dict]
async def cleanup_expired(self) -> int  # 返回清理数量
```

- [ ] 所有方法使用 async SQLAlchemy session
- [ ] `decide()` 使用乐观锁（检查 status == PENDING 才更新）

**验收：** 方法实现完整，逻辑正确。

### 4. 修改 ApprovalWorkflow 接入持久化

文件：`src/agentos/workflows/approval.py`

- [ ] `ApprovalWorkflow.__init__` 接收可选 `repository: ApprovalRepository` 参数
- [ ] `run()` 方法中，提交审批时调用 `repository.create()`
- [ ] 等待审批时：轮询数据库（每 5 秒 `repository.get()`）而不是 `asyncio.Event.wait()`
  - 原因：`asyncio.Event` 重启后丢失，改为数据库轮询确保重启可恢复
- [ ] 收到审批结果后调用 `repository.decide()`
- [ ] 超时后将记录标记为 EXPIRED（不是删除）

**注意：** 保留原有 `asyncio.Event` 路径用于测试（当 `repository=None` 时）。

- [ ] 修改完成，逻辑符合上述要求

### 5. 新增 API 端点：列出和处理待审批

文件：`src/agentos/api/routes/` 下新建或追加

- [ ] `GET /workflows/approvals` — 列出当前租户所有 PENDING 记录
  - 需要权限：`Permission.WORKFLOW_RUN`（或新增 `WORKFLOW_APPROVE`）
- [ ] `POST /workflows/approvals/{workflow_id}/decide` — 提交审批决定
  - 请求体：`{"approved": true, "feedback": "LGTM"}`
  - 调用 `repository.decide()`，触发对应等待中的工作流继续执行

- [ ] 两个端点实现完整，有租户隔离检查

### 6. 编写单元测试

文件：`tests/unit/test_approval_workflow.py`（新建）

- [ ] 测试正常审批通过流程
- [ ] 测试审批拒绝流程
- [ ] 测试超时流程
- [ ] 测试重启恢复（模拟：create → 重启 → decide → 结果正确）

**验收：** `PYTHONPATH=src pytest tests/unit/test_approval_workflow.py` 全部通过。
