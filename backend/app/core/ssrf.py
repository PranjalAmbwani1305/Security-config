"""Outbound-request guard for tenant-supplied URLs (webhooks).

Without this, any tenant could make the server call cloud metadata endpoints
(169.254.169.254), internal services or localhost. We resolve the host and refuse
any non-public address; callers must also disable redirects.

Residual risk: DNS can change between this check and the request (rebinding).
In AWS, also restrict egress at the network layer (security group / egress proxy).
"""
import ipaddress
import socket
from urllib.parse import urlsplit

from app.config import get_settings
from app.core.errors import ApiError


def _is_public(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
        or ip.is_reserved or ip.is_unspecified
    )


def assert_safe_url(url: str) -> None:
    s = get_settings()
    parts = urlsplit(url)
    allowed = ("https", "http") if not s.is_production else ("https",)
    if parts.scheme not in allowed:
        raise ApiError(422, "invalid_webhook_url", f"Webhook URL must use {' or '.join(allowed)}")
    if parts.username or parts.password:
        raise ApiError(422, "invalid_webhook_url", "Webhook URL must not contain credentials")
    host = parts.hostname
    if not host:
        raise ApiError(422, "invalid_webhook_url", "Webhook URL has no host")
    if s.webhook_allow_private:
        return
    try:
        infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80),
                                   type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ApiError(422, "invalid_webhook_url", "Webhook host could not be resolved") from None
    for info in infos:
        if not _is_public(ipaddress.ip_address(info[4][0])):
            raise ApiError(422, "invalid_webhook_url",
                           "Webhook URL must point to a public internet address")
