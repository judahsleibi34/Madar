#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import socket
import sys
import unittest
from typing import Any

EXTERNAL_ATTEMPTS: list[str] = []
_original_connect = socket.socket.connect
_original_getaddrinfo = socket.getaddrinfo


def _loopback_host(host: Any) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="ignore")
    value = str(host or "").strip().lower().rstrip(".")
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _guarded_connect(sock: socket.socket, address: Any):
    if sock.family in {socket.AF_INET, socket.AF_INET6}:
        host = address[0] if isinstance(address, tuple) and address else ""
        if not _loopback_host(host):
            EXTERNAL_ATTEMPTS.append(str(host)[:200])
            raise OSError("external network disabled by Madar test guard")
    return _original_connect(sock, address)


def _guarded_getaddrinfo(host: Any, *args, **kwargs):
    if not _loopback_host(host):
        EXTERNAL_ATTEMPTS.append(str(host)[:200])
        raise socket.gaierror("external DNS disabled by Madar test guard")
    return _original_getaddrinfo(host, *args, **kwargs)


def main() -> int:
    socket.socket.connect = _guarded_connect
    socket.getaddrinfo = _guarded_getaddrinfo
    suite = unittest.defaultTestLoader.discover("tests")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"EXTERNAL_ATTEMPTS {sorted(set(EXTERNAL_ATTEMPTS))}")
    return 0 if result.wasSuccessful() and not EXTERNAL_ATTEMPTS else 1


if __name__ == "__main__":
    raise SystemExit(main())
