# AgentOS 任务清单

基于 code review 结果生成的修复任务，按优先级和模块拆分。

## 使用指南

- **P0** = 生产上线前必须完成
- **P1** = 重要，影响可用性和可观测性
- **P2** = 优化项，可延后

## 工作流程

1. 按优先级顺序选择任务文件（P0 → P1 → P2）
2. 每个任务文件内按列出顺序执行子任务
3. 完成一项后在文件内勾选 `[x]`
4. 每个子任务都要满足 **验收标准** 才算完成
5. 改动后运行 `PYTHONPATH=src pytest tests/` 确认未破坏现有测试

## 任务清单

### P0 — 阻塞上线
- [P0_persistence.md](./P0_persistence.md) — Registry、AuditLog、Workflow 状态持久化
- [P0_auth.md](./P0_auth.md) — 默认开启认证、CORS 收敛、限流
- [P0_a2a_bridge.md](./P0_a2a_bridge.md) — 实现 A2A 跨 Agent 通信
- [P0_approval_workflow.md](./P0_approval_workflow.md) — 审批工作流状态持久化
- [P0_memory_backend.md](./P0_memory_backend.md) — Memory 后端实现（PostgreSQL）

### P1 — 重要
- [P1_budget_quota.md](./P1_budget_quota.md) — Budget 与 Quota 联动
- [P1_observability.md](./P1_observability.md) — Prometheus / OpenTelemetry 接入
- [P1_testing.md](./P1_testing.md) — 集成测试与覆盖率
- [P1_provider_plugin.md](./P1_provider_plugin.md) — Provider 插件化

### P2 — 优化
- [P2_optimization.md](./P2_optimization.md) — 性能、缓存、API 版本化

## 通用约定

- **不要**做任务之外的"顺手优化"。改动范围最小化。
- 新增依赖必须在 `pyproject.toml` 显式声明。
- 数据库 schema 变更必须通过 Alembic migration。
- 对外行为变更（API、配置）必须更新 `configs/agentos.yaml` 示例。
- 提交前运行 `ruff check src/ tests/ && ruff format src/ tests/`。
