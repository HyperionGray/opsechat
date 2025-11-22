from __future__ import annotations
"""Shim entrypoint for ff3sync-mini-tcp script.

Delegates to the full TCP ingest server defined in tcp_receiver.py.
"""
from .tcp_receiver import main

if __name__ == "__main__":
    main()
