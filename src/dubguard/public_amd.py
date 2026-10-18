"""Single-instance public inference admission. No raw client addresses persist."""
from hashlib import sha256
import hmac
import os
import secrets
import time

from fastapi import HTTPException

COOKIE = "dubguard-client"


def limit(name, default, maximum):
    try:
        return min(maximum, max(0, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


def enabled():
    # Fail closed for misspelled switches. Budgets may also be set to zero.
    return os.getenv("DUBGUARD_PUBLIC_AMD_ENABLED", "false").lower() == "true"


def client_identity(cookie, address):
    from .quick import database
    now = int(time.time())
    with database() as db:
        secret = db.execute("SELECT value FROM accounting_secret").fetchone()[0].encode()
    def sign(value):
        return hmac.new(secret, value.encode(), sha256).hexdigest()
    try:
        value, signature = cookie.rsplit(".", 1)
        nonce, expiry = value.split(".")
        valid = len(nonce) == 32 and now < int(expiry) <= now + 86400 and hmac.compare_digest(sign(value), signature)
    except (ValueError, AttributeError):
        valid = False
    if not valid:
        value = f"{secrets.token_hex(16)}.{now + 86400}"
        cookie = value + "." + sign(value)
    # Both buckets must pass: clearing cookies cannot reset the network bucket;
    # moving networks cannot reset an existing browser bucket. No fingerprinting.
    return (sign("browser:" + value), sign("network:" + address)), cookie


def check_budget(db, clients=(), *, reserve=False):
    now = time.time()
    db.execute("DELETE FROM amd_attempts WHERE created<=?", (now - 86400,))
    hourly = limit("DUBGUARD_AMD_REQUESTS_PER_HOUR", 10, 100)
    daily = limit("DUBGUARD_AMD_REQUESTS_PER_DAY", 40, 1000)
    per_client = limit("DUBGUARD_AMD_CLIENT_REQUESTS_PER_DAY", 4, 20)
    hour = db.execute("SELECT count(*) FROM amd_attempts WHERE created>?", (now - 3600,)).fetchone()[0]
    day = db.execute("SELECT count(*) FROM amd_attempts").fetchone()[0]
    exhausted = hour >= hourly or day >= daily or per_client == 0
    for digest in clients:
        count = db.execute("SELECT count(*) FROM amd_attempts WHERE browser=? OR network=?", (digest, digest)).fetchone()[0]
        exhausted |= count >= per_client
    if exhausted:
        raise HTTPException(429, "Public AMD quota exhausted. Local Verification remains available. Try again after the budget recovers.", headers={"Retry-After": "3600"})
    if reserve:
        if len(clients) != 2:
            raise HTTPException(429, "Public AMD client accounting unavailable")
        # Called inside the same BEGIN IMMEDIATE transaction as session charging.
        # Never refunded on decode errors, provider failures, deletion or restart.
        db.execute("INSERT INTO amd_attempts VALUES (?,?,?)", (now, *clients))
