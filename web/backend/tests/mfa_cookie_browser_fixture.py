"""Loopback-only server for actual-cookie Playwright login acceptance."""
import socket
import ipaddress
import uvicorn
from fastapi import Request
from mfa_cookie_fixture import ADMIN, cookie_fixture

_original_connect = socket.socket.connect
_original_getaddrinfo = socket.getaddrinfo

def connect(sock, address):
    if sock.family in {socket.AF_INET, socket.AF_INET6} and not ipaddress.ip_address(address[0]).is_loopback:
        raise OSError("External networking disabled in MFA browser fixture")
    return _original_connect(sock, address)

def getaddrinfo(host, *args, **kwargs):
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise OSError("External networking disabled in MFA browser fixture")
    return _original_getaddrinfo(host, *args, **kwargs)

socket.socket.connect = connect
socket.getaddrinfo = getaddrinfo
app, provider, store, patches = cookie_fixture()
# Only bootstrap/status use synthetic responses; login/challenge/verify run the
# actual application routes and cookie helpers. Remove duplicate route matches.
app.router.routes = [route for route in app.router.routes
                     if getattr(route, "path", "") not in {"/auth/user_status", "/auth/mfa/status"}]

@app.get("/fixture-health")
def health(): return {"fixture": True}

@app.get("/auth/user_status")
def status(request: Request):
    valid = request.cookies.get("madar_access_token") == "synthetic-aal2-access"
    return {"logged_in": valid, "user": ADMIN if valid else None}

@app.get("/auth/mfa/status")
def mfa_status(request: Request):
    return {"aal": {"current_level": "aal2" if request.cookies.get("madar_access_token") == "synthetic-aal2-access" else "aal1"}, "factors": provider.list_factors()["all"]}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=18091, log_level="warning", access_log=False)
