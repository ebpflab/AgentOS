"""FastAPI application for AgentOS REST API.

Provides HTTP endpoints for managing agents, workflows, sessions, and metrics.
Uses lifespan to boot/shutdown the AgentOS runtime.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from agentos.config import load_config
from agentos.kernel.runtime import AgentOSRuntime

logger = logging.getLogger(__name__)

_runtime: AgentOSRuntime | None = None


def get_runtime() -> AgentOSRuntime:
    """Get the current runtime instance."""
    if _runtime is None:
        raise RuntimeError("AgentOS runtime not initialized")
    return _runtime


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan: start and stop the AgentOS runtime."""
    global _runtime

    config = load_config()
    _runtime = AgentOSRuntime(config)
    await _runtime.start()

    logger.info("AgentOS API server started")
    yield

    await _runtime.shutdown()
    _runtime = None
    logger.info("AgentOS API server stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AgentOS API",
        description="Enterprise Agent Operating System — REST API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure per environment in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register route modules
    from agentos.api.routes import agents, auth, workflows, sessions, metrics, admin
    app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
    app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
    app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

    # WebSocket for real-time events
    from agentos.api.websocket import register_websocket
    register_websocket(app)

    @app.get("/health")
    async def health():
        runtime = get_runtime()
        return {
            "status": "healthy" if runtime.is_running else "unhealthy",
            "agents": runtime.registry.count,
            "providers": runtime.providers.list_providers(),
        }

    # Serve React web UI (if built) — SPA fallback to index.html
    web_dist = Path(__file__).parent.parent.parent.parent / "web" / "dist"
    if web_dist.is_dir():
        class SPAStaticFiles(StaticFiles):
            """StaticFiles subclass that falls back to index.html for SPA routing."""
            async def get_response(self, path: str, scope):
                try:
                    return await super().get_response(path, scope)
                except (StarletteHTTPException,):
                    return await super().get_response("index.html", scope)

        app.mount("/", SPAStaticFiles(directory=str(web_dist), html=True), name="web-ui")
        logger.info("Serving web UI from %s", web_dist)

    return app
