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
