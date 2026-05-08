"""SSRF protection for HTTP endpoint adapters.

The default policy refuses any URL that resolves to localhost, link-local, or
RFC1918 private space. Operators self-hosting an agent on their own infra can
opt out by setting `AGENT_ENDPOINT_ALLOW_PRIVATE=true`.

This is intentionally conservative — once we accept arbitrary URLs from
authenticated users, the same code path can be coerced into pinging internal
metadata services (e.g. AWS IMDS at 169.254.169.254) unless we block private
ranges up front.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from ..config import get_settings


class UnsafeEndpointError(ValueError):
    """Raised when a user-provided URL targets a denied address."""


_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local — covers AWS IMDS
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),   # IPv6 unique local
]


def _is_private(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return any(ip in net for net in _PRIVATE_NETWORKS)


def assert_endpoint_safe(url: str) -> None:
    """Raise UnsafeEndpointError if the URL targets a denied destination.

    No-op when `AGENT_ENDPOINT_ALLOW_PRIVATE=true` is set in the environment.
    """
    settings = get_settings()
    if getattr(settings, "agent_endpoint_allow_private", False):
        return

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeEndpointError(f"Only http(s) endpoints are allowed; got '{parsed.scheme}'.")
    host = parsed.hostname
    if not host:
        raise UnsafeEndpointError("Endpoint URL is missing a hostname.")

    lowered = host.lower()
    if lowered == "localhost":
        raise UnsafeEndpointError("localhost endpoints are not allowed.")

    # Direct IP literal — check it.
    if _is_private(host):
        raise UnsafeEndpointError(f"Endpoint host {host} is in a private/loopback range.")

    # DNS hostname — resolve and check every A/AAAA result.
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeEndpointError(f"Endpoint host {host} could not be resolved.") from exc

    for info in infos:
        addr = info[4][0]
        if _is_private(addr):
            raise UnsafeEndpointError(
                f"Endpoint host {host} resolves to private address {addr}; refusing."
            )
