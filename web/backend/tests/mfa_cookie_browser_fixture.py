"""Loopback-only server for actual-cookie Playwright login acceptance."""
import socket
import ipaddress
import uvicorn
from fastapi import Request, Response
from mfa_sdk_lifecycle_fixture import sdk_cookie_fixture
from services import auth_service

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
app, provider, store, shared, patches = sdk_cookie_fixture(secure=False)
commercial = {"attempts": 0, "successes": 0, "held": False, "revision": 17}

@app.get("/fixture-health")
def health(): return {"fixture": True}

@app.get("/fixture/stats")
def stats():
    return {"verify_count": provider.verify_count, "refresh_count": provider.refresh_count, **commercial}

@app.post("/fixture/advance")
def advance(payload: dict, request: Request, response: Response):
    auth_service.require_system_admin(request, response, require_aal2=True)
    provider.now += min(2000, max(0, int(payload.get("seconds", 0))))
    provider.downgrade = bool(payload.get("downgrade", False))
    return {"advanced": True}

@app.api_route("/admin/billing/{path:path}", methods=["GET", "POST"])
def commercial_fixture(path: str, request: Request, response: Response):
    if request.method == "POST": commercial["attempts"] += 1
    # Only the data/command seam is synthetic. Actual authorization reconstructs
    # cookie sessions, rotates provider tokens and enforces current AAL2.
    auth_service.require_system_admin(request, response, require_aal2=True)
    if path.endswith("price-books"): return {"price_books": []}
    if path.endswith("access-history"): return {"events": [], "payments": [], "periods": []}
    if request.method == "POST":
        commercial["successes"] += 1
        commercial["held"] = path.endswith("suspend")
        commercial["revision"] += 1
        return {"success": True}
    return {"tenant": {"brand_name": "Synthetic lifecycle tenant", "owner_name": "Synthetic owner"},
            "hold": {"commercial_suspended_at": "2026-10-01T00:00:00Z", "commercial_suspension_reason": "Synthetic reason"} if commercial["held"] else {},
            "commercial_access": {"revision": commercial["revision"], "access_state": "suspended" if commercial["held"] else "active", "review_state": "reviewed"},
            "entitlements": {"assigned_modules": ["website"], "effective_modules": [] if commercial["held"] else ["website"], "capabilities": [], "pricing": {"recurring_minor": 2000, "currency": "USD", "billing_interval": "month"}}}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=18091, log_level="warning", access_log=False)
