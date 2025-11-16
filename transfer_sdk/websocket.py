"""Deprecated WebSocket bridge helpers.

All WebSocket transport code has been removed. This stub remains only to avoid
hard failures in any lingering imports. Prefer TCP arithmetic or QUIC/UDP transports.
"""

from __future__ import annotations

def _deprecated(*_args, **_kwargs):  # pragma: no cover
    raise RuntimeError("WebSocket transport removed; use TCP/QUIC/UDP alternatives")

TransferHub = _deprecated  # type: ignore
receive_text = _deprecated  # type: ignore
dispatch_job = _deprecated  # type: ignore
ACK_MESSAGE = "ACK"
__all__ = ["TransferHub", "receive_text", "dispatch_job", "ACK_MESSAGE"]
