"""WebSocket endpoint for real-time event streaming."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from agentos.kernel.events import Event

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and topic subscriptions."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._subscriptions: dict[str, set[str]] = {}  # conn_id -> set of topic patterns

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        await websocket.accept()
        self._connections[client_id] = websocket
        self._subscriptions[client_id] = {"*"}  # Subscribe to all by default
        logger.info("WebSocket connected: %s", client_id[:8])

    def disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)
        self._subscriptions.pop(client_id, None)
        logger.info("WebSocket disconnected: %s", client_id[:8])

    def subscribe(self, client_id: str, patterns: list[str]) -> None:
        if client_id in self._subscriptions:
            self._subscriptions[client_id] = set(patterns)

    async def broadcast_event(self, event: Event) -> None:
        """Send an event to all connected clients with matching subscriptions."""
        import fnmatch

        data = json.dumps({
            "event_id": event.event_id,
            "topic": event.topic,
            "data": event.data if isinstance(event.data, (dict, list, str, int, float, bool)) else str(event.data),
            "timestamp": event.timestamp,
            "source": event.source,
        })

        disconnected = []
        for client_id, ws in self._connections.items():
            patterns = self._subscriptions.get(client_id, set())
            if any(fnmatch.fnmatch(event.topic, p) for p in patterns):
                try:
                    await ws.send_text(data)
                except Exception:
                    disconnected.append(client_id)

        for client_id in disconnected:
            self.disconnect(client_id)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


_manager = ConnectionManager()


def get_ws_manager() -> ConnectionManager:
    return _manager


def register_websocket(app: FastAPI) -> None:
    """Register the WebSocket endpoint and hook into the event bus."""

    @app.websocket("/ws/events")
    async def websocket_events(websocket: WebSocket):
        from uuid import uuid4
        client_id = str(uuid4())
        await _manager.connect(websocket, client_id)

        try:
            while True:
                # Receive subscription commands from client
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "subscribe":
                        _manager.subscribe(client_id, msg.get("patterns", ["*"]))
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            _manager.disconnect(client_id)

    @app.on_event("startup")
    async def _hook_event_bus():
        """Hook the WebSocket manager into the event bus."""
        try:
            from agentos.api.server import get_runtime
            runtime = get_runtime()
            await runtime.event_bus.subscribe("*", _manager.broadcast_event)
        except RuntimeError:
            pass  # Runtime may not be started in test mode
