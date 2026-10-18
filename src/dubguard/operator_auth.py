"""Private UI authentication: opaque HttpOnly cookie, never a browser-stored reviewer key."""
from hashlib import sha256
import os
import secrets
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field
from .schemas import Model
from . import quick

router = APIRouter(prefix="/operator", tags=["private operator authentication"])
COOKIE = "dubguard_operator"


def same_origin(request):
    origin = request.headers.get("origin")
    if request.headers.get("sec-fetch-site") == "cross-site" or origin and urlsplit(origin).netloc != request.headers.get("host"):
        raise HTTPException(403, "Same-origin operator action required")


def table(db):
    db.execute("CREATE TABLE IF NOT EXISTS operator_sessions (digest TEXT PRIMARY KEY, identity TEXT, config TEXT, expires REAL)")
    db.execute("DELETE FROM operator_sessions WHERE expires<=?", (time.time(),))


def cookie_identity(request):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        same_origin(request)
    token = request.cookies.get(COOKIE, "")
    if not token:
        raise HTTPException(401, "Operator sign-in required")
    with quick.database() as db:
        table(db)
        row = db.execute("SELECT identity FROM operator_sessions WHERE digest=? AND config=? AND expires>?", (sha256(token.encode()).hexdigest(), sha256(os.getenv('DUBGUARD_REVIEW_TOKENS_JSON', '').encode()).hexdigest(), time.time())).fetchone()
    if not row:
        raise HTTPException(401, "Operator session expired; sign in again")
    return row['identity']


class OperatorLogin(Model):
    token: str = Field(min_length=1, max_length=512)


@router.post("/session")
def login(payload: OperatorLogin, request: Request, response: Response):
    from .review import reviewer
    same_origin(request)
    identity = reviewer("Bearer " + payload.token)
    token = secrets.token_urlsafe(32)
    with quick.database() as db:
        table(db)
        if db.execute('SELECT count(*) FROM operator_sessions').fetchone()[0] >= 100:
            raise HTTPException(429, 'Operator session limit reached')
        db.execute('INSERT INTO operator_sessions VALUES (?,?,?,?)', (sha256(token.encode()).hexdigest(), identity, sha256(os.getenv('DUBGUARD_REVIEW_TOKENS_JSON','').encode()).hexdigest(), time.time()+1800))
    response.set_cookie(COOKIE, token, httponly=True, secure=request.url.hostname not in {'localhost','127.0.0.1','testserver'}, samesite='strict', max_age=1800, path='/')
    return {"authenticated": True}


@router.get("/session")
def status(request: Request):
    cookie_identity(request)
    return {"authenticated": True}


@router.delete("/session")
def logout(request: Request, response: Response):
    same_origin(request)
    with quick.database() as db:
        table(db)
        db.execute('DELETE FROM operator_sessions WHERE digest=?', (sha256(request.cookies.get(COOKIE,'').encode()).hexdigest(),))
    response.delete_cookie(COOKIE, path='/')
    return {"signed_out": True}
