"""Early, bounded admission for demo uploads. One API process is required.

Authenticate before multipart spooling; persistent hourly HMAC accounting survives
session deletion/restart. No raw address is stored. Proxy trust is opt-in.
"""
import asyncio
from hashlib import sha256
import hmac
from ipaddress import ip_address, ip_network
import os
from threading import BoundedSemaphore, Lock
import time
from urllib.parse import parse_qs

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from .quick import MAX_BYTES, authorize_amd, database, resolve_session

_UPLOAD_SLOTS = BoundedSemaphore(2)
_ACTIVE_CLIENTS: set[str] = set()
_LOCK = Lock()
MAX_BODY = MAX_BYTES + 65_536  # Multipart overhead is bounded too.
BODY_SECONDS = 30


def client_address(scope, headers):
    peer = (scope.get("client") or ("unknown", 0))[0]
    try:
        address = ip_address(peer)
        networks = [ip_network(n.strip(), strict=False) for n in os.getenv("DUBGUARD_TRUSTED_PROXIES", "").split(",") if n.strip()]
        def trusted(addr):
            return any(addr in network for network in networks)
        if trusted(address):
            # Peel only known proxy hops from the right. Attacker-supplied left
            # entries never override the first untrusted source in the chain.
            forwarded = headers.get("x-forwarded-for", "")
            if len(forwarded) > 1024:
                return str(address)
            for hop in reversed(forwarded.split(",")):
                if not trusted(address):
                    break
                address = ip_address(hop.strip())
        return str(address)
    except ValueError:
        return peer if peer == "testclient" else "unknown"


def bounded_limit(name, default, maximum):
    try:
        return min(maximum, max(1, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


def charge(address, kind):
    now = time.time()
    limit = (bounded_limit("DUBGUARD_CLIENT_SESSIONS_PER_HOUR", 4, 30) if kind == "session" else
             bounded_limit("DUBGUARD_OPERATOR_LOGINS_PER_HOUR", 8, 30) if kind == "operator_login" else
             bounded_limit("DUBGUARD_CLIENT_EDITS_PER_HOUR", 60, 120) if kind == "edit" else
             bounded_limit("DUBGUARD_CLIENT_UPLOADS_PER_HOUR", 6, 90))
    with database() as db:
        db.execute("DELETE FROM client_events WHERE created<?", (now - 3600,))
        secret = db.execute("SELECT value FROM accounting_secret").fetchone()[0]
        digest = hmac.new(secret.encode(), address.encode(), sha256).hexdigest()
        count = db.execute("SELECT count(*) FROM client_events WHERE digest=? AND kind=?", (digest, kind)).fetchone()[0]
        total = db.execute("SELECT count(*) FROM client_events").fetchone()[0]
        if count >= limit or total >= 600:
            raise HTTPException(429, "Demo request limit reached; wait before trying again")
        db.execute("INSERT INTO client_events VALUES (?,?,?)", (digest, kind, now))
    return digest


def preflight(headers, query, address, scope="sample"):
    identity = resolve_session(headers.get("authorization"), scope)
    if scope == "custom":
        from .workspace import require_enabled
        require_enabled()
    # Authenticated upload attempts consume client budget even when AMD code,
    # consent or subsequent quotas reject them. No credential guessing loop.
    digest = charge(address, "upload")
    mode = query.get("mode", ["local"])
    if len(mode) != 1 or mode[0] not in {"local", "amd"}:
        raise HTTPException(422, "Choose a supported verification mode")
    if mode[0] == "amd":
        if scope == "custom":
            raise HTTPException(403, "Custom workspace supports local verification only; AMD remains separately protected in Quick Test")
        consent = query.get("consent", [])
        authorize_amd(headers.get("x-amd-demo-code", ""), len(consent) == 1 and consent[0].lower() in {"true", "1", "yes", "on"})
    with database() as db:
        row = db.execute("SELECT * FROM sessions WHERE id=?", (identity,)).fetchone()
        if not row or row["expires"] <= time.time():
            raise HTTPException(401, "Quick Test session is missing or expired")
        if row["state"] == "PROCESSING" or row["runs"] >= 3 or db.execute("SELECT count(*) FROM sessions WHERE state='PROCESSING'").fetchone()[0] >= 2:
            raise HTTPException(429, "Demo analysis limit reached; wait for running analyses to finish")
        if mode[0] == "amd" and (row["amd_runs"] >= 2 or db.execute("SELECT count(*) FROM sessions WHERE state='PROCESSING' AND json_extract(payload,'$.mode')='amd'").fetchone()[0]):
            raise HTTPException(429, "AMD demo limit reached; local verification may still be available")
    return digest


class QuickAdmissionMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        paths = {"/operator/session", "/quick/analyze", "/quick/sessions", "/workspace/analyze", "/workspace/sessions", "/workspace/reference", "/workspace/evidence", "/workspace/review"}
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT"} or scope["path"] not in paths:
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        acquired = False
        digest = None
        try:
            address = client_address(scope, headers)
            upload = scope["path"].endswith("/analyze")
            custom = scope["path"].startswith("/workspace/")
            metadata = scope["method"] == "PUT"
            maximum = MAX_BODY if upload else 32768 if metadata else 4096
            try:
                length = int(headers.get("content-length", "0"))
            except ValueError:
                raise HTTPException(400, "Invalid request length")
            if length < 0 or length > maximum:
                raise HTTPException(413, "Demo request is too large; audio limit is 10 MB")
            if upload:
                query = parse_qs(scope.get("query_string", b"").decode("ascii", errors="replace"))
                # Reject repeated security parameters; framework parsers otherwise
                # may select a different value than an early authorization check.
                if any(len(values) != 1 for values in query.values()):
                    raise HTTPException(422, "Repeated parameters are not supported")
                digest = await run_in_threadpool(preflight, headers, query, address, "custom" if custom else "sample")
            elif metadata:
                await run_in_threadpool(resolve_session, headers.get("authorization"), "custom")
                from .workspace import require_enabled
                require_enabled()
                digest = await run_in_threadpool(charge, address, "edit")
            else:
                digest = await run_in_threadpool(charge, address, "operator_login" if scope["path"] == "/operator/session" else "session")
            if upload:
                with _LOCK:
                    if digest in _ACTIVE_CLIENTS or not _UPLOAD_SLOTS.acquire(blocking=False):
                        raise HTTPException(429, "Demo upload busy; wait for the current upload to finish")
                    _ACTIVE_CLIENTS.add(digest)
                    acquired = True
            # Small fixed global upload concurrency bounds memory/spooling. A hard
            # body deadline bounds stalled/chunked uploads before multipart parsing.
            body = bytearray()
            async with asyncio.timeout(BODY_SECONDS):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > maximum:
                        raise HTTPException(413, "Demo request is too large; audio limit is 10 MB")
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
            delivered = False
            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()
            await self.app(scope, replay, send)
        except (HTTPException, TimeoutError) as exc:
            status = exc.status_code if isinstance(exc, HTTPException) else 408
            detail = exc.detail if isinstance(exc, HTTPException) else "Upload timed out; choose a smaller recording or try later"
            response = JSONResponse({"detail": detail}, status_code=status, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", **({"Retry-After": "3600"} if status == 429 else {})})
            await response(scope, receive, send)
        finally:
            if acquired:
                with _LOCK:
                    _ACTIVE_CLIENTS.discard(digest)
                    _UPLOAD_SLOTS.release()
