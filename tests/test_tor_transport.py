"""
Tests for Tor ingress/egress transport helpers.
"""

from unittest.mock import patch

import requests
import socks

from tor_transport import (
    configure_requests_session,
    create_tor_connection,
    get_tor_control_endpoint,
    get_tor_socks_endpoint,
    resolve_tor_control_endpoint,
    tor_ingress_required,
    tor_socks_proxy_url,
)


def test_tor_endpoints_use_environment(monkeypatch):
    monkeypatch.setenv("TOR_CONTROL_HOST", "tor-control")
    monkeypatch.setenv("TOR_CONTROL_PORT", "19051")
    monkeypatch.setenv("TOR_SOCKS_HOST", "tor-socks")
    monkeypatch.setenv("TOR_SOCKS_PORT", "19050")
    monkeypatch.setenv("OPSECHAT_REQUIRE_TOR", "1")

    assert get_tor_control_endpoint() == ("tor-control", 19051)
    assert get_tor_socks_endpoint() == ("tor-socks", 19050)
    assert tor_socks_proxy_url() == "socks5h://tor-socks:19050"
    assert tor_ingress_required() is True


def test_configure_requests_session_sets_tor_proxies(monkeypatch):
    monkeypatch.setenv("OPSECHAT_FORCE_TOR_EGRESS", "1")
    monkeypatch.setenv("TOR_SOCKS_HOST", "tor")
    monkeypatch.setenv("TOR_SOCKS_PORT", "9050")

    session = requests.Session()
    configure_requests_session(session)

    assert session.trust_env is False
    assert session.proxies["http"] == "socks5h://tor:9050"
    assert session.proxies["https"] == "socks5h://tor:9050"


@patch("tor_transport.socket.gethostbyname", return_value="172.18.0.2")
def test_resolve_tor_control_endpoint_resolves_hostnames(mock_gethostbyname, monkeypatch):
    monkeypatch.setenv("TOR_CONTROL_HOST", "tor")
    monkeypatch.setenv("TOR_CONTROL_PORT", "9051")

    assert resolve_tor_control_endpoint() == ("172.18.0.2", 9051)
    mock_gethostbyname.assert_called_once_with("tor")


@patch("tor_transport.socks.create_connection")
def test_create_tor_connection_uses_socks_proxy(mock_create_connection, monkeypatch):
    monkeypatch.setenv("TOR_SOCKS_HOST", "tor")
    monkeypatch.setenv("TOR_SOCKS_PORT", "9050")

    create_tor_connection("example.com", 443, timeout=5)

    mock_create_connection.assert_called_once_with(
        ("example.com", 443),
        timeout=5,
        source_address=None,
        proxy_type=socks.SOCKS5,
        proxy_addr="tor",
        proxy_port=9050,
        proxy_rdns=True,
    )


from tor_transport import get_hidden_service_target


def test_hidden_service_target_default_is_int(monkeypatch):
    """No env override -> int port; Tor interprets as 127.0.0.1 in its own
    namespace, which is correct for ad-hoc / native runs.
    """
    monkeypatch.delenv("OPSECHAT_HS_TARGET", raising=False)
    monkeypatch.delenv("OPSECHAT_HS_TARGET_HOST", raising=False)
    monkeypatch.delenv("OPSECHAT_HS_TARGET_PORT", raising=False)
    assert get_hidden_service_target() == 5000
    assert get_hidden_service_target(default_port=8000) == 8000


def test_hidden_service_target_host_env_returns_host_port_string(monkeypatch):
    """Compose / quadlet path: HOST env makes us return the string Tor needs."""
    monkeypatch.delenv("OPSECHAT_HS_TARGET", raising=False)
    monkeypatch.setenv("OPSECHAT_HS_TARGET_HOST", "opsechat")
    monkeypatch.delenv("OPSECHAT_HS_TARGET_PORT", raising=False)
    assert get_hidden_service_target() == "opsechat:5000"


def test_hidden_service_target_host_and_port_env(monkeypatch):
    monkeypatch.delenv("OPSECHAT_HS_TARGET", raising=False)
    monkeypatch.setenv("OPSECHAT_HS_TARGET_HOST", "opsechat-app")
    monkeypatch.setenv("OPSECHAT_HS_TARGET_PORT", "5050")
    assert get_hidden_service_target() == "opsechat-app:5050"


def test_hidden_service_target_raw_env_takes_priority(monkeypatch):
    monkeypatch.setenv("OPSECHAT_HS_TARGET", "explicit-target:9999")
    monkeypatch.setenv("OPSECHAT_HS_TARGET_HOST", "ignored")
    monkeypatch.setenv("OPSECHAT_HS_TARGET_PORT", "1234")
    assert get_hidden_service_target() == "explicit-target:9999"


def test_hidden_service_target_raw_env_must_be_host_port(monkeypatch):
    monkeypatch.setenv("OPSECHAT_HS_TARGET", "no-port-here")
    try:
        get_hidden_service_target()
    except RuntimeError as exc:
        assert "host:port" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for malformed OPSECHAT_HS_TARGET")
