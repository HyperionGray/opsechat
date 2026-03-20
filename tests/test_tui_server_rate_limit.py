"""
Unit tests for per-user rate limiting in src/tui/server.py.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tui.server import ChatServer


def _make_server(max_messages=2, window_seconds=60):
    return ChatServer(
        host='127.0.0.1',
        port=0,
        max_messages_per_window=max_messages,
        rate_limit_window_seconds=window_seconds,
        start_cleanup_thread=False,
    )


def test_rate_limit_allows_messages_under_threshold():
    server = _make_server(max_messages=3, window_seconds=30)

    allowed_1, retry_1 = server._check_rate_limit("Alice")
    allowed_2, retry_2 = server._check_rate_limit("Alice")
    allowed_3, retry_3 = server._check_rate_limit("Alice")

    assert allowed_1 and retry_1 == 0
    assert allowed_2 and retry_2 == 0
    assert allowed_3 and retry_3 == 0


def test_rate_limit_blocks_when_threshold_exceeded():
    server = _make_server(max_messages=2, window_seconds=60)

    assert server._check_rate_limit("Alice")[0]
    assert server._check_rate_limit("Alice")[0]

    allowed, retry_after = server._check_rate_limit("Alice")
    assert not allowed
    assert 1 <= retry_after <= 60


def test_rate_limit_allows_again_after_window_expires():
    server = _make_server(max_messages=1, window_seconds=10)

    assert server._check_rate_limit("Alice")[0]

    with server.lock:
        server.client_message_times["Alice"] = [
            datetime.datetime.now() - datetime.timedelta(seconds=15)
        ]

    allowed, retry_after = server._check_rate_limit("Alice")
    assert allowed
    assert retry_after == 0


def test_cleanup_prunes_stale_rate_limit_entries():
    server = _make_server(max_messages=2, window_seconds=10)
    now = datetime.datetime.now()

    with server.lock:
        server.client_message_times["stale"] = [
            now - datetime.timedelta(seconds=30)
        ]
        server.client_message_times["fresh"] = [
            now - datetime.timedelta(seconds=2)
        ]

    server._cleanup_old_messages()

    with server.lock:
        assert "stale" not in server.client_message_times
        assert "fresh" in server.client_message_times


def test_stop_clears_rate_limit_state():
    server = _make_server(max_messages=2, window_seconds=30)

    with server.lock:
        server.client_message_times["Alice"] = [datetime.datetime.now()]

    server.stop()

    with server.lock:
        assert server.client_message_times == {}
