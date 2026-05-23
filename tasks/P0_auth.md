# P0: 安全默认值 — 认证、CORS、限流

## 背景

当前安全配置存在严重默认值问题：
- `auth_enabled: false` — 任何人无需认证即可调用 API
- CORS 允许通配符 `*` — 任意来源跨域请求均被接受
- 无认证端点限流 — 暴力破解无防护

## 相关文件

- `configs/agentos.yaml` — 安全配置
- `src/agentos/api/server.py` — CORS 中间件、应用入口
- `src/agentos/api/deps.py` — 认证依赖注入
- `src/agentos/security/auth.py` — OIDC/JWT 验证逻辑
- `src/agentos/config.py` — SecurityConfig 模型

## 子任务

### 1. 将 auth_enabled 默认值改为 true

文件：`src/agentos/config.py`

- [ ] 找到 `SecurityConfig` 中 `auth_enabled` 字段，将默认值从 `False` 改为 `True`
- [ ] 同步修改 `configs/agentos.yaml` 示例文件，将 `auth_enabled: false` 改为 `auth_enabled: true`，并添加注释说明开发环境可设为 false

**验收：** 新部署环境不设置任何覆盖时，默认要求认证。

### 2. 收敛 CORS 配置

文件：`src/agentos/api/server.py`

- [ ] 读取当前 CORS 配置代码
- [ ] 将 `allow_origins=["*"]` 改为从配置读取：`allow_origins=settings.server.cors_origins`
- [ ] 在 `configs/agentos.yaml` 的 `server` 节新增：
  ```yaml
  cors_origins:
    - "http://localhost:3000"   # 本地开发
  ```
- [ ] 在 `src/agentos/config.py` 的 `ServerConfig` 中新增 `cors_origins: list[str] = ["http://localhost:3000"]`

**验收：** 生产配置不包含 `*`，只有显式配置的域名被允许跨域。

### 3. 为认证端点添加限流

文件：`src/agentos/api/server.py` 或新建 `src/agentos/api/middleware/rate_limit.py`

- [ ] 为以下路径添加基于 IP 的滑动窗口限流（使用已有的 `RateLimiter`）：
  - `POST /auth/token`（或认证端点）
  - `POST /agents/{id}/run`
- [ ] 默认限制：每 IP 每分钟最多 60 次请求；认证端点每 IP 每分钟最多 10 次
- [ ] 超限时返回 `HTTP 429 Too Many Requests`，包含 `Retry-After` header

**验收：** 连续超过限制的请求收到 429 响应。

### 4. 修复 deps.py 中 auth 禁用时的行为

文件：`src/agentos/api/deps.py`

- [ ] 读取当前 `require_permission` 实现
- [ ] 确认当 `auth_enabled=False` 时返回的 dev_user 有明确的 `tenant_id`（当前可能为空）
- [ ] 添加警告日志：`logger.warning("Auth disabled — running in development mode")`，在每次应用启动时输出一次（不是每次请求）

**验收：** dev 模式日志中有明确警告；dev_user 的 tenant_id 为合法非空字符串。

### 5. 为敏感配置字段添加校验

文件：`src/agentos/config.py`

- [ ] `SecurityConfig` 中：若 `auth_enabled=True` 且未配置 `oidc_issuer`，启动时抛出明确错误（而非静默继续）
- [ ] `ServerConfig` 中：`port` 范围校验 1–65535

**验收：** `auth_enabled=True` 但无 OIDC 配置时，服务启动失败并输出可读错误信息。
