"""
Focused tests for TUI server command and anti-spam behavior.
"""

import os
import sys

import pytest


# Ensure project src/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tui.server import ChatServer


@pytest.fixture(scope="module")
def server():
    """Create one TUI server instance for this module."""
    srv = ChatServer()
    yield srv
    with srv.lock:
        srv.messages.clear()
        srv.clients.clear()
        srv.client_message_times.clear()


@pytest.fixture(autouse=True)
def reset_server_state(server):
    """Reset mutable server state between tests."""
    with server.lock:
        server.messages.clear()
        server.clients.clear()
        server.client_message_times.clear()
    yield
    with server.lock:
        server.messages.clear()
        server.clients.clear()
        server.client_message_times.clear()


def test_tui_message_lifetime_is_four_minutes(server):
    assert server.MESSAGE_LIFETIME == 240


def test_tui_server_help_command(server):
    response = server.handle_command("/help")
    assert response["type"] == "command_response"
    assert response["command"] == "help"
    assert response["ok"] is True
    assert "/status" in response["message"]
    assert "/users" in response["message"]


def test_tui_server_status_and_users_commands(server):
    with server.lock:
        server.clients[object()] = "UserA"
        server.clients[object()] = "UserB"
        server.messages.append({"username": "UserA", "message": "hello", "timestamp": None})

    status_response = server.handle_command("status")
    assert status_response["ok"] is True
    assert "users=2" in status_response["message"]
    assert "messages=1" in status_response["message"]
    assert "rate_limit=" in status_response["message"]

    users_response = server.handle_command("/users")
    assert users_response["ok"] is True
    assert users_response["message"] == "Connected users: 2"


def test_tui_server_unknown_command(server):
    response = server.handle_command("/nope")
    assert response["type"] == "command_response"
    assert response["ok"] is False
    assert "Unknown command" in response["message"]


def test_tui_server_rate_limit_blocks_spam(server):
    username = "RateLimitedUser"
    for idx in range(server.RATE_LIMIT_MAX_MESSAGES):
        allowed, error_message = server.add_message(username, f"msg-{idx}")
        assert allowed is True
        assert error_message == ""

    allowed, error_message = server.add_message(username, "msg-blocked")
    assert allowed is False
    assert "Rate limit exceeded" in error_message


def test_tui_server_rate_limit_is_per_user(server):
    first_user = "UserA"
    second_user = "UserB"
    for idx in range(server.RATE_LIMIT_MAX_MESSAGES):
        allowed, _ = server.add_message(first_user, f"a-{idx}")
        assert allowed is True

    blocked, _ = server.add_message(first_user, "a-over")
    assert blocked is False

    allowed_other_user, other_error = server.add_message(second_user, "b-1")
    assert allowed_other_user is True
    assert other_error == ""
