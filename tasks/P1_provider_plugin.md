# P1: Provider 插件化

## 背景

`src/agentos/providers/manager.py` 中 Provider 创建是硬编码 if-elif 链：
```python
if provider == "openai": ...
elif provider == "anthropic": ...
elif provider == "ollama": ...
```
新增 Provider（如 Azure、Vertex、Bedrock）需要修改核心代码，违反开闭原则。

## 实现目标

使用 Python `entry_points` 或显式注册机制让 Provider 可插件化。

## 相关文件

- `src/agentos/providers/manager.py` — 主要修改目标
- `pyproject.toml` — entry_points 声明
- `src/agentos/exceptions.py` — ProviderError

## 子任务

### 1. 定义 ProviderFactory Protocol

文件：`src/agentos/providers/base.py`（新建）

```python
from typing import Protocol, Any

class ProviderFactory(Protocol):
    """每个 Provider 实现的工厂接口"""

    name: str  # provider 名称，如 "openai"

    def create_client(self, model: str, config: dict[str, Any]) -> Any:
        """创建 MAF ChatClient 实例"""
        ...

    def list_models(self) -> list[str]:
        """返回该 Provider 支持的模型列表"""
        ...
```

- [ ] Protocol 定义完成

### 2. 内置 Providers 重构为 Factory 类

文件：`src/agentos/providers/factories/`（新建目录）

- [ ] `factories/openai_factory.py` — `class OpenAIFactory` 实现 ProviderFactory
- [ ] `factories/anthropic_factory.py` — `class AnthropicFactory`
- [ ] `factories/ollama_factory.py` — `class OllamaFactory`
- [ ] 每个 factory 封装原 if-elif 中对应分支的逻辑
- [ ] `create_client()` 处理 API key 和 endpoint 配置
- [ ] `list_models()` 至少返回硬编码的常见模型列表（后续可扩展为 API 查询）

**验收：** 三个 factory 实现完成，行为与原代码一致。

### 3. 实现注册表机制

文件：`src/agentos/providers/manager.py`

修改 `ProviderManager`：

```python
class ProviderManager:
    def __init__(self, config):
        self._factories: dict[str, ProviderFactory] = {}
        self._clients: dict[str, Any] = {}
        self._register_builtin_factories()
        self._load_entry_point_factories()

    def register_factory(self, factory: ProviderFactory) -> None:
        """显式注册"""
        self._factories[factory.name] = factory

    def _register_builtin_factories(self) -> None:
        from .factories.openai_factory import OpenAIFactory
        from .factories.anthropic_factory import AnthropicFactory
        from .factories.ollama_factory import OllamaFactory
        for factory_cls in [OpenAIFactory, AnthropicFactory, OllamaFactory]:
            self.register_factory(factory_cls())

    def _load_entry_point_factories(self) -> None:
        """从 entry_points 加载第三方 Provider"""
        from importlib.metadata import entry_points
        for ep in entry_points(group="agentos.providers"):
            factory_cls = ep.load()
            self.register_factory(factory_cls())
```

- [ ] `get_client(provider, model)` 改为查 `_factories[provider].create_client(model, config)`
- [ ] 删除原 if-elif 链
- [ ] 未知 provider 时抛出 `ProviderError` 并列出已注册的 provider
- [ ] `list_models(provider)` 委托给对应 factory

**验收：** 行为与原代码一致，新增 Provider 只需注册 factory 即可。

### 4. 在 pyproject.toml 声明内置 entry_points（可选）

文件：`pyproject.toml`

可以保留内置 factory 硬编码注册，无需声明 entry_points；
但要在文档中说明第三方如何注册：

- [ ] 在 `pyproject.toml` 中添加示例注释：
  ```toml
  # 第三方 Provider 通过以下方式注册：
  # [project.entry-points."agentos.providers"]
  # azure = "my_pkg.azure_factory:AzureFactory"
  ```

### 5. 编写单元测试

文件：`tests/unit/test_provider_manager.py`（新建）

- [ ] 测试内置 factories 正常注册
- [ ] 测试 `get_client("openai", "gpt-4")` 返回 cached client
- [ ] 测试 `get_client("unknown", "x")` 抛出 `ProviderError` 包含可用 provider 列表
- [ ] 测试 `register_factory()` 自定义 factory 后可用
- [ ] 测试 `list_models()` 委托给 factory

**验收：** `PYTHONPATH=src pytest tests/unit/test_provider_manager.py` 全部通过。

### 6. CLI 支持显示注册的 Provider

文件：`src/agentos/cli.py`

- [ ] `agentos providers list` 命令显示所有已注册 factory 的 name 和 model 列表
- [ ] 输出格式：表格或简单文本，每行 `provider: model1, model2, ...`

**验收：** `PYTHONPATH=src python -m agentos providers list` 列出三个内置 provider 及其模型。
