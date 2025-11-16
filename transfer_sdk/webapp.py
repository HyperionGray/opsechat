"""ASGI app exposing the Transfer SDK WebSocket bridge."""

from __future__ import annotations

from .websocket_bridge import build_app


app = build_app()

__all__ = ["app", "build_app"]
