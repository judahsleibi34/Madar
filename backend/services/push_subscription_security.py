from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

import requests


class UnsafePushEndpoint(ValueError):
    pass


def create_no_redirect_session() -> requests.Session:
    session = requests.Session()
    session.max_redirects = 0
    return session


def validate_push_endpoint(endpoint: str) -> str:
    value = str(endpoint or "").strip()
    try:
        parsed = urlsplit(value)
        port = parsed.port or 443
    except ValueError as error:
        raise UnsafePushEndpoint("push_endpoint_invalid") from error

    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or parsed.query and not parsed.path
    ):
        raise UnsafePushEndpoint("push_endpoint_invalid")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise UnsafePushEndpoint("push_endpoint_unsafe")

    try:
        addresses = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except OSError as error:
        raise UnsafePushEndpoint("push_endpoint_unresolved") from error

    resolved = set()
    for address in addresses:
        try:
            resolved.add(ipaddress.ip_address(address[4][0]))
        except (IndexError, ValueError, TypeError) as error:
            raise UnsafePushEndpoint("push_endpoint_unresolved") from error

    if not resolved or any(
        not address.is_global
        or address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
        for address in resolved
    ):
        raise UnsafePushEndpoint("push_endpoint_unsafe")

    return value
