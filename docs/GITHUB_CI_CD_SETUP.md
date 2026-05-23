# GitHub & CI/CD 自动化配置

## 1️⃣ 安装 GitHub MCP

```bash
claude mcp add github npx @modelcontextprotocol/server-github
```

验证安装：
```bash
claude mcp list
```

## 2️⃣ 在 Claude Code 中配置 GitHub

创建或编辑 `.claude/settings.json`：

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "your_personal_access_token"
      }
    }
  }
}
```

### 获取 GitHub Token
1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 选择权限：`repo`, `workflow`, `read:org`
4. 复制 token 到上面的配置

## 3️⃣ Workflow 说明

### 🔄 CI/CD Pipeline (`.github/workflows/ci.yml`)

**触发条件：**
- 推送到 `main` 或 `develop` 分支
- 提交 PR

**运行步骤：**
1. **Lint & Format** — Python 3.11/3.12 ruff 检查
2. **Unit Tests** — pytest 单元测试 + 覆盖率（PostgreSQL + Redis）
3. **Integration Tests** — 集成测试
4. **Docker Build** — 验证 Docker 镜像构建
5. **Frontend Build** — Node.js 前端编译和 lint

**检查失败时的自动反馈：**
- 在 PR 中评论修复建议
- Codecov 覆盖率报告

---

### 📋 PR 自动审查 (`.github/workflows/pr-review.yml`)

**功能：**
- 自动标记 PR（`backend`, `frontend`, `tests`, `ci-cd` 等）
- 检测超大 PR（>500 行变更），提醒拆分
- 跳过草稿 PR 的 CI

---

### 🏥 定时健康检查 (`.github/workflows/health-check.yml`)

**触发条件：**
- 每 30 分钟运行一次
- 或手动触发 `workflow_dispatch`

**功能：**
- 检查 main 分支最新的 CI 运行状态
- 如果失败，自动创建 Issue（标记为 `ci-failure` 和 `urgent`）
- 避免重复创建

---

## 4️⃣ Claude Code 中的自动化命令

### 实时监控 CI 状态（使用 `/loop` skill）

```bash
/loop 10m gh run list -R ebpflab/AgentOS -w ci.yml --limit 1 --json status,conclusion,name
```

这会每 10 分钟检查一次最新的 CI 运行状态。

### 管理 PR

```bash
# 查看所有开放的 PR
gh pr list -R ebpflab/AgentOS

# 查看特定 PR 的详情
gh pr view 123 -R ebpflab/AgentOS

# 在 PR 中添加评论
gh pr comment 123 -R ebpflab/AgentOS -b "Great work! 🎉"

# 合并 PR
gh pr merge 123 -R ebpflab/AgentOS --squash
```

### 查看 Workflow 运行

```bash
# 最新运行
gh run list -R ebpflab/AgentOS -w ci.yml --limit 5

# 查看运行详情
gh run view RUN_ID -R ebpflab/AgentOS --log

# 重新运行失败的 workflow
gh run rerun RUN_ID -R ebpflab/AgentOS
```

---

## 5️⃣ 下一步配置

### 可选：添加自动部署

编辑 `.github/workflows/ci.yml`，在 `all-checks-passed` 后添加：

```yaml
  deploy:
    name: Deploy to Staging
    needs: [all-checks-passed]
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy
        run: echo "Deploying to staging..."
```

### 可选：Slack/邮件通知

```yaml
  notify:
    name: Send Notification
    needs: [all-checks-passed]
    if: always()
    runs-on: ubuntu-latest
    steps:
      - name: Send Slack message
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {
              "text": "CI Pipeline: ${{ needs.all-checks-passed.result }}"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

---

## 6️⃣ 提交 Workflow 到 GitHub

```bash
git add .github/workflows/
git commit -m "feat: add complete CI/CD pipeline with health checks"
git push origin main
```

完成！🎉 GitHub Actions 会自动开始运行 workflow。
