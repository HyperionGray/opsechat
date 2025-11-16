"""Deprecated: WebSocket bridge app removed.

This module no longer provides a WebSocket bridge. Use the main FastAPI app's
HTTP upload endpoints and the TCP/QUIC/UDP receivers instead.
"""

from __future__ import annotations

from pathlib import Path
import os
import json
from typing import Dict, Any

from typing import Any, Dict

def build_app(*_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover
    raise RuntimeError("websocket_bridge removed; use HTTP upload endpoints or TCP/QUIC/UDP receivers")
