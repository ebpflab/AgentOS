"""Server-side internationalization (i18n).

Resolves messages based on the ``Accept-Language`` header (or query string
``?lang=zh``). Falls back to English when a key is missing in the target
locale.

Usage in route handlers::

    from fastapi import Depends
    from agentos.i18n import get_locale, tr

    @router.get("/foo")
    async def foo(locale: str = Depends(get_locale)):
        return {"message": tr("agent.not_found", locale)}
"""

from __future__ import annotations

from typing import Literal

from fastapi import Request

Locale = Literal["en", "zh"]


MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "agent.not_found": "Agent not found",
        "agent.no_instance": "Agent has no active instance",
        "agent.create_failed": "Failed to create agent: {0}",
        "workflow.not_found": "Workflow run not found",
        "workflow.requires_instances": "Workflow execution requires agent instances — use CLI for now",
        "auth.use_oidc": "Use OIDC SSO for authentication",
        "auth.refresh_not_impl": "Token refresh not implemented",
        "auth.callback_received": "callback_received",
        "auth.dev_token": "dev-token",
        "common.internal_error": "Internal server error: {0}",
    },
    "zh": {
        "agent.not_found": "未找到指定的 Agent",
        "agent.no_instance": "Agent 没有可用的活动实例",
        "agent.create_failed": "Agent 创建失败：{0}",
        "workflow.not_found": "未找到工作流运行记录",
        "workflow.requires_instances": "工作流执行需要 Agent 实例 — 请暂时使用 CLI",
        "auth.use_oidc": "请使用 OIDC SSO 进行身份认证",
        "auth.refresh_not_impl": "尚未实现令牌刷新功能",
        "auth.callback_received": "回调已接收",
        "auth.dev_token": "开发模式令牌",
        "common.internal_error": "服务器内部错误：{0}",
    },
}


def parse_accept_language(header: str | None) -> Locale:
    """Parse an Accept-Language header and return a supported locale.

    Returns "zh" if any zh* variant is the most preferred; otherwise "en".
    """
    if not header:
        return "en"
    # Trivial parsing — we only care about the first language tag
    primary = header.split(",")[0].strip().lower()
    if primary.startswith("zh"):
        return "zh"
    return "en"


def get_locale(request: Request) -> Locale:
    """FastAPI dependency that extracts the request locale.

    Priority: ``?lang=`` query param → ``Accept-Language`` header → "en".
    """
    explicit = request.query_params.get("lang")
    if explicit:
        explicit = explicit.lower()
        if explicit.startswith("zh"):
            return "zh"
        if explicit.startswith("en"):
            return "en"
    return parse_accept_language(request.headers.get("Accept-Language"))


def tr(key: str, locale: str = "en", *args: object) -> str:
    """Translate ``key`` into ``locale``.

    Falls back to the English message if the key is missing from the requested
    locale, and to ``key`` itself if it does not exist at all. Positional
    ``{0}``, ``{1}`` … placeholders are formatted with ``args``.
    """
    dictionary = MESSAGES.get(locale) or MESSAGES["en"]
    template = dictionary.get(key) or MESSAGES["en"].get(key) or key
    if not args:
        return template
    formatted = template
    for idx, val in enumerate(args):
        formatted = formatted.replace("{" + str(idx) + "}", str(val))
    return formatted
