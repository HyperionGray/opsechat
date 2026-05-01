"""
Tor transport helpers for ingress and egress policy.

Ingress:
- creation of the onion service still happens in the server entrypoints
- this module provides shared environment parsing for Tor control access

Egress:
- HTTP requests can be forced through Tor SOCKS
- SMTP/IMAP sockets can be forced through Tor SOCKS
"""

import imaplib
import os
import socket
import smtplib
from typing import Dict, Tuple

import socks


_TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def tor_ingress_required() -> bool:
    """Whether the app should refuse to start without an onion service."""
    return _env_flag("OPSECHAT_REQUIRE_TOR", False)


def tor_egress_enabled() -> bool:
    """Whether outbound network traffic should use the Tor SOCKS proxy."""
    return _env_flag("OPSECHAT_FORCE_TOR_EGRESS", False)


def get_tor_control_endpoint() -> Tuple[str, int]:
    """Return the Tor control endpoint from the environment."""
    host = os.environ.get("TOR_CONTROL_HOST", "127.0.0.1")
    port = int(os.environ.get("TOR_CONTROL_PORT", "9051"))
    return host, port


def resolve_tor_control_endpoint() -> Tuple[str, int]:
    """
    Return the Tor control endpoint with the host resolved to an IPv4 address.

    `stem.Controller.from_port()` rejects Docker-style service names such as
    `tor`, so the server entrypoints must resolve them before connecting.
    """
    host, port = get_tor_control_endpoint()
    return socket.gethostbyname(host), port


def get_tor_socks_endpoint() -> Tuple[str, int]:
    """Return the Tor SOCKS endpoint from the environment."""
    host = os.environ.get("TOR_SOCKS_HOST", os.environ.get("TOR_CONTROL_HOST", "127.0.0.1"))
    port = int(os.environ.get("TOR_SOCKS_PORT", "9050"))
    return host, port


def tor_socks_proxy_url() -> str:
    """Return a requests-compatible SOCKS proxy URL with remote DNS."""
    host, port = get_tor_socks_endpoint()
    return f"socks5h://{host}:{port}"


def tor_requests_proxies() -> Dict[str, str]:
    """Return requests proxy settings for Tor-routed HTTP(S)."""
    proxy = tor_socks_proxy_url()
    return {
        "http": proxy,
        "https": proxy,
    }


def configure_requests_session(session):
    """
    Apply safe defaults to a requests session and, when enabled, route it
    through Tor with remote DNS resolution.
    """
    session.trust_env = False
    if not tor_egress_enabled():
        return session

    proxies = tor_requests_proxies()
    existing = getattr(session, "proxies", None)
    if isinstance(existing, dict):
        merged = dict(existing)
        merged.update(proxies)
        session.proxies = merged
    else:
        session.proxies = proxies.copy()
    return session


def create_tor_connection(host: str, port: int, timeout=None, source_address=None):
    """Create a socket connection to the target through Tor SOCKS5."""
    tor_host, tor_port = get_tor_socks_endpoint()
    return socks.create_connection(
        (host, port),
        timeout=timeout,
        source_address=source_address,
        proxy_type=socks.SOCKS5,
        proxy_addr=tor_host,
        proxy_port=tor_port,
        proxy_rdns=True,
    )


class TorSMTP(smtplib.SMTP):
    """SMTP client that opens sockets through the Tor SOCKS proxy."""

    def _get_socket(self, host, port, timeout):
        if timeout is not None and not timeout:
            raise ValueError("Non-blocking socket (timeout=0) is not supported")
        if self.debuglevel > 0:
            self._print_debug("connect: to", (host, port), self.source_address)
        return create_tor_connection(host, port, timeout=timeout, source_address=self.source_address)


class TorIMAP4(imaplib.IMAP4):
    """IMAP client that opens sockets through the Tor SOCKS proxy."""

    def _create_socket(self, timeout):
        if timeout is not None and not timeout:
            raise ValueError("Non-blocking socket (timeout=0) is not supported")
        return create_tor_connection(self.host, self.port, timeout=timeout)


class TorIMAP4_SSL(imaplib.IMAP4_SSL):
    """IMAPS client that opens sockets through the Tor SOCKS proxy."""

    def _create_socket(self, timeout):
        sock = create_tor_connection(self.host, self.port, timeout=timeout)
        return self.ssl_context.wrap_socket(sock, server_hostname=self.host)
