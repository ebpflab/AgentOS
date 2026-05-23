# AgentOS CI/CD 自动化配置完成 ✅

## 📦 已创建的文件

### Workflow 文件 (`.github/workflows/`)

1. **`ci.yml`** — 完整的 CI/CD Pipeline
   - Python 3.11/3.12 Lint & Format 检查
   - 单元测试 + 覆盖率报告
   - 集成测试（PostgreSQL + Redis）
   - Docker 镜像构建验证
   - 前端编译和 lint
   - 自动 PR 反馈

2. **`pr-review.yml`** — PR 自动审查
   - 自动标记 PR（标签：backend, frontend, tests, ci-cd）
   - 检测超大 PR（>500 行），提醒拆分
   - 跳过草稿 PR

3. **`health-check.yml`** — 定时健康检查
   - 每 30 分钟检查一次 main 分支 CI 状态
   - 如果失败自动创建 Issue（标记：ci-failure, urgent）

### 脚本文件 (`scripts/`)

1. **`monitor-ci.sh`** — CI 状态监控脚本
   - 定时检查 CI 运行状态
   - 支持 Slack 通知
   - 可配置检查间隔

2. **`ci-helpers.sh`** — CI/CD 快捷命令库
   - PR 操作：list, view, comment, merge
   - Workflow 操作：status, logs, rerun
   - Issue 操作：list, create, ci-failures
   - 监控和分析：pr_stats, ci_success_rate

### 文档

1. **`docs/GITHUB_CI_CD_SETUP.md`** — 完整配置指南

---

## 🚀 快速开始

### Step 1: 提交到 GitHub

```bash
git add .github/ scripts/ docs/GITHUB_CI_CD_SETUP.md
git commit -m "feat: add complete CI/CD pipeline with health checks

- Add comprehensive CI/CD workflow (lint, tests, docker)
- Add PR auto-review and health check workflows
- Add CI monitoring and helper scripts
- Add setup documentation"

git push origin main
```

### Step 2: 验证 Workflows

访问你的 GitHub 仓库：
```
https://github.com/ebpflab/AgentOS/actions
```

你应该看到 3 个 workflow：
- ✅ `CI/CD Pipeline`
- ✅ `PR Auto-Review`
- ✅ `Scheduled Health Check`

### Step 3: 配置 GitHub MCP（可选）

在 Claude Code 中使用 GitHub API：

```bash
claude mcp add github npx @modelcontextprotocol/server-github
```

在 `~/.claude/settings.json` 中配置：

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "your_github_token"
      }
    }
  }
}
```

获取 token：https://github.com/settings/tokens

---

## 📋 常用命令

### 在本地测试 Lint 和测试

```bash
# 安装依赖
pip install -e ".[dev]"

# Lint 检查
ruff check src/ tests/

# 自动格式化
ruff format src/ tests/

# 运行单元测试
PYTHONPATH=src pytest tests/unit/ -v --cov=src/agentos

# 运行集成测试
PYTHONPATH=src pytest tests/integration/ -v
```

### 使用 CI Helper 脚本

```bash
# Source 脚本
source scripts/ci-helpers.sh

# 查看可用命令
ci_help

# 列出开放的 PR
pr_list

# 查看 CI 状态
ci_status

# 监控 CI（每 5 分钟检查一次）
monitor_ci 300

# 创建 Issue
issue_create "Bug: something is broken" "Steps to reproduce..."
```

---

## 🔄 Workflow 流程图

```
用户 Push 到 main/develop 或提交 PR
        ↓
✅ PR Auto-Review (自动标记、检查大小)
        ↓
🔄 CI/CD Pipeline (并行运行):
   ├─ Lint & Format (Python 3.11/3.12)
   ├─ Unit Tests + Coverage
   ├─ Integration Tests
   ├─ Docker Build
   └─ Frontend Build
        ↓
✅ All Checks Passed → PR 可合并
❌ 失败 → PR 中自动添加修复建议
        ↓
定时任务 (每 30 分钟):
   └─ Health Check → 检查 main 分支状态
      └─ 失败时自动创建 Issue
```

---

## 📊 监控和通知

### 自动化监控

```bash
# 在后台启动 CI 监控（30 分钟检查间隔）
source scripts/ci-helpers.sh
monitor_ci 1800 &

# 在后台启动，带 Slack 通知
SLACK_WEBHOOK="https://hooks.slack.com/..." bash scripts/monitor-ci.sh --interval 600 &
```

### 手动检查

```bash
# 查看最新的 CI 运行
gh run list -R ebpflab/AgentOS -w ci.yml --limit 5 \
  --json status,conclusion,name,createdAt

# 查看运行日志
gh run view RUN_ID -R ebpflab/AgentOS --log

# 重新运行失败的 workflow
gh run rerun RUN_ID -R ebpflab/AgentOS
```

---

## 🔐 Secrets 配置（可选）

如果你想添加 Slack 通知或其他服务，在 GitHub 设置中添加：

```
Settings → Secrets and variables → Actions → New repository secret
```

常用 Secrets：
- `SLACK_WEBHOOK_URL` — Slack 通知
- `CODECOV_TOKEN` — Codecov 覆盖率
- `DOCKER_USERNAME` — Docker Hub 用户名
- `DOCKER_PASSWORD` — Docker Hub 密码

---

## 📚 其他资源

- GitHub Actions 文档：https://docs.github.com/en/actions
- Workflow 语法：https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions
- Python 工具链（ruff）：https://docs.astral.sh/ruff/
- Pytest 文档：https://docs.pytest.org/

---

## ✅ 检查清单

- [ ] 已提交 `.github/workflows/` 文件到 GitHub
- [ ] 已提交 `scripts/` 文件到 GitHub
- [ ] 已验证 GitHub Actions 正在运行（查看 Actions tab）
- [ ] 已配置 GitHub MCP（可选）
- [ ] 已测试本地 lint 和测试命令
- [ ] 已使用 `monitor-ci.sh` 验证监控脚本（可选）
- [ ] 已配置 Slack 通知（可选）

---

有任何问题或需要调整 workflow，请参考 `docs/GITHUB_CI_CD_SETUP.md` 或编辑对应的 YAML 文件。
