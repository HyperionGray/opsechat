"""Deprecated: WebSocket mini server removed.

This module is retained only to avoid import errors in legacy scripts. Do not
use it; prefer TCP arithmetic (`transfer_sdk.receiver_daemon`) or QUIC/UDP NDJSON.
"""

from __future__ import annotations

def main() -> None:  # pragma: no cover
    raise SystemExit("transfer_sdk.mini_ws_server has been removed; use receiver_daemon or ff3sync-mini-tcp instead")
