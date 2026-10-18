"""Bounded, capability-authenticated demonstration sessions; never review approvals."""
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import time
from threading import BoundedSemaphore
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile, Request
from fastapi.responses import Response
from .audio import AudioStore, AudioArtifact, AUDIO_MIME, transcribe_artifact
from .alignment import propose_alignment
from .engine import verify
from .providers import AMDTokenFactoryProvider, DisabledProvider
from .review import _root
from .schemas import VerificationRequest, ScriptPolicy
from .ui_contracts import DemoScenario, QuickReport, QuickConfig
from .public_amd import enabled, check_budget

router = APIRouter(prefix="/quick", tags=["demonstration"])
TTL = 1800
MAX_BYTES = 10_000_000
MAX_SECONDS = 60
_AMD_SLOT = BoundedSemaphore(1)  # A deleted session cannot release an in-flight HTTP call's slot.
_DEMO_SLOTS = BoundedSemaphore(2)


def scenarios() -> list[DemoScenario]:
    source = json.loads((Path(__file__).parent / "data" / "demo_scenarios.json").read_text())
    return [DemoScenario.model_validate(item) for item in source]


@contextmanager
def database():
    root = _root() / "quick"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(root / "sessions.sqlite3", timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, digest TEXT, expires REAL, created REAL, state TEXT, runs INTEGER, payload TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS admissions (created REAL)")
        db.execute("CREATE TABLE IF NOT EXISTS amd_attempts (created REAL, browser TEXT, network TEXT)")
        db.execute("CREATE INDEX IF NOT EXISTS amd_attempts_time ON amd_attempts(created)")
        db.execute("CREATE TABLE IF NOT EXISTS client_events (digest TEXT, kind TEXT, created REAL)")
        db.execute("CREATE INDEX IF NOT EXISTS client_events_lookup ON client_events(digest,kind,created)")
        db.execute("CREATE TABLE IF NOT EXISTS accounting_secret (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT)")
        db.execute("INSERT OR IGNORE INTO accounting_secret VALUES (1,?)", (secrets.token_hex(32),))
        if "amd_runs" not in {r["name"] for r in db.execute("PRAGMA table_info(sessions)")}:
            db.execute("ALTER TABLE sessions ADD COLUMN amd_runs INTEGER NOT NULL DEFAULT 0")
        columns = {r["name"] for r in db.execute("PRAGMA table_info(sessions)")}
        if "scope" not in columns:
            db.execute("ALTER TABLE sessions ADD COLUMN scope TEXT NOT NULL DEFAULT 'sample'")
        if "custom" not in columns:
            db.execute("ALTER TABLE sessions ADD COLUMN custom TEXT")
        db.commit()
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def cleanup():
    with database() as db:
        expired = db.execute("SELECT id FROM sessions WHERE expires<=?", (time.time(),)).fetchall()
        for row in expired:
            shutil.rmtree(_root() / "quick" / row["id"], ignore_errors=True)
        db.execute("DELETE FROM sessions WHERE expires<=?", (time.time(),))
        db.execute("DELETE FROM admissions WHERE created<?", (time.time()-3600,))
        db.execute("DELETE FROM client_events WHERE created<?", (time.time()-3600,))
        db.execute("DELETE FROM amd_attempts WHERE created<=?", (time.time()-86400,))


def resolve_session(authorization: str | None, scope: str = "sample") -> str:
    cleanup()
    supplied = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    with database() as db:
        row = db.execute("SELECT id FROM sessions WHERE digest=? AND expires>? AND scope=?", (sha256(supplied.encode()).hexdigest(), time.time(), scope)).fetchone()
    if not row:
        raise HTTPException(401, "Quick Test session is missing or expired")
    return row["id"]


def session(authorization: str | None = Header(default=None)) -> str:
    return resolve_session(authorization)


@router.get("/scenarios", response_model=list[DemoScenario])
def get_scenarios():
    return scenarios()


def amd_demo_available() -> bool:
    # Configuration inspection only. Never construct a transport or perform discovery.
    from .providers import _load_project_env
    from urllib.parse import urlsplit
    _load_project_env()
    try:
        endpoint = urlsplit(os.getenv("AMD_TOKEN_FACTORY_ENDPOINT", ""))
        return bool(enabled()
                    and os.getenv("AMD_TOKEN_FACTORY_API_KEY")
                    and os.getenv("AMD_TOKEN_FACTORY_MODEL") == "DeepSeek-V4-Flash"
                    and endpoint.scheme == "https" and endpoint.hostname
                    and not endpoint.username and not endpoint.password and not endpoint.query and not endpoint.fragment)
    except (ValueError, TypeError):
        return False


def authorize_amd(consent: bool):
    if not consent:
        raise HTTPException(422, "Explicit consent is required for each AMD analysis; only script, policy and transcript text are sent")
    if not amd_demo_available():
        raise HTTPException(503, "AMD Semantic Review is temporarily unavailable. Local Verification remains available.")


@router.get("/config", response_model=QuickConfig)
def demo_config():
    available = amd_demo_available()
    reason = None if available else "configuration"
    if available:
        try:
            with database() as db:
                check_budget(db)
        except HTTPException:
            available = False
            reason = "quota"
    return {"public_local": True, "amd_available": available, "amd_unavailable_reason": reason}


@router.post("/sessions")
def create_session():
    return new_session("sample")


def new_session(scope: str):
    cleanup()
    token, identity = secrets.token_urlsafe(32), uuid4().hex
    with database() as db:
        if db.execute("SELECT count(*) FROM sessions").fetchone()[0] >= 20 or db.execute("SELECT count(*) FROM admissions").fetchone()[0] >= 30:
            raise HTTPException(429, "Demo session quota reached; retry later")
        now = time.time()
        db.execute("INSERT INTO admissions VALUES (?)", (now,))
        db.execute("INSERT INTO sessions (id,digest,expires,created,state,runs,payload,scope) VALUES (?,?,?,?,?,?,?,?)", (identity, sha256(token.encode()).hexdigest(), now+TTL, now, "EMPTY", 0, "{}", scope))
    return {"token": token, "id": identity, "expires_at": now+TTL, "max_runs": 3, "max_seconds": MAX_SECONDS, "max_bytes": MAX_BYTES}


@router.get("/session", response_model=QuickReport)
def get_session(identity: str = Depends(session)):
    with database() as db:
        row = db.execute("SELECT * FROM sessions WHERE id=?", (identity,)).fetchone()
    if not row:
        raise HTTPException(401, "Session expired")
    return QuickReport(id=identity, state=row["state"], expires_at=row["expires"], runs=row["runs"], amd_runs=row["amd_runs"], **json.loads(row["payload"]))


def analyze_job(*args):
    try:
        _analyze_job(*args)
    finally:
        _DEMO_SLOTS.release()


def _analyze_job(identity: str, data: bytes, content_type: str, scenario_id: str | None, mode: str = "local", consented_at: float | None = None,
                 reference: ScriptPolicy | None = None, reference_revision: int | None = None):
    # Each job has an isolated directory. A deleted/expired session cannot be resurrected.
    root = _root() / "quick" / identity
    payload = {"scenario_id": scenario_id, "mode": mode, "consented_at": consented_at,
               "semantic_status": "pending_transcription" if mode == "amd" else "not_requested"}
    state = "FAILED"
    if reference is not None:
        payload.update(reference_policy=reference.model_dump(mode="json"), reference_revision=reference_revision)
    try:
        policy = reference or next(item.policy for item in scenarios() if item.id == scenario_id)
        audio = AudioStore(root)
        artifact = audio.ingest(data, content_type=content_type, max_bytes=MAX_BYTES, max_seconds=MAX_SECONDS)
        payload["artifact"] = artifact.model_dump(mode="json")
        result = transcribe_artifact(audio, artifact)
        payload["transcription"] = result.model_dump(mode="json")
        payload["alignment"] = propose_alignment(policy.script, result.transcript).model_dump(mode="json")
        request = VerificationRequest(**policy.model_dump(mode="json"), transcript=result.transcript)
        payload["verification"] = verify(request).model_dump(mode="json")
        if mode == "amd":
            authorize_amd(consented_at is not None)
            payload["semantic_status"] = "processing"
            # Publish local evidence before the bounded remote call. Re-check consent/session lifetime.
            with database() as db:
                row = db.execute("SELECT expires FROM sessions WHERE id=?", (identity,)).fetchone()
                if not row or row["expires"] <= time.time():
                    shutil.rmtree(root, ignore_errors=True)
                    return
                db.execute("UPDATE sessions SET payload=? WHERE id=?", (json.dumps(payload), identity))
            provider = AMDTokenFactoryProvider(max_retries=0, timeout_seconds=40, max_output_tokens=1024, max_input_tokens=32768)
            # Quick Test never substitutes another model or the optional audio provider.
            if provider.model != "DeepSeek-V4-Flash":
                provider.model = None  # visible unavailable result, zero HTTP attempts
            acquired = _AMD_SLOT.acquire(blocking=False)
            try:
                semantic = verify(request, hybrid=True, provider=provider if acquired else DisabledProvider())
            finally:
                if acquired:
                    _AMD_SLOT.release()
            payload["semantic_verification"] = semantic.model_dump(mode="json")
            assessment = semantic.semantic
            payload["semantic_status"] = ("invalid_citations" if assessment.issues else "completed") if assessment and assessment.status == "real" else "unavailable"
        state = "COMPLETE"
    except Exception:
        if mode == "amd":
            payload["semantic_status"] = "not_completed"
        if payload.get("verification"):
            state = "COMPLETE"
            payload["error"] = "AMD Semantic Review did not complete. Local Verification results remain available. No remote result is fabricated."
        else:
            payload["error"] = "Analysis failed: unsupported audio, exceeded duration, or unavailable local ASR. No result is fabricated. Check local dependencies and cached model."
    with database() as db:
        row = db.execute("SELECT expires FROM sessions WHERE id=?", (identity,)).fetchone()
        if row and row["expires"] > time.time():
            db.execute("UPDATE sessions SET state=?,payload=? WHERE id=?", (state, json.dumps(payload), identity))
        else:
            shutil.rmtree(root, ignore_errors=True)


@router.post("/analyze")
async def analyze(tasks: BackgroundTasks, request: Request, scenario_id: str, file: UploadFile = File(...),
                  mode: Literal["local", "amd"] = "local", consent: bool = False,
                  identity: str = Depends(session)):
    if scenario_id not in {item.id for item in scenarios()}:
        raise HTTPException(422, "Unknown demonstration scenario")
    if mode == "amd":
        authorize_amd(consent)
    data = await file.read(MAX_BYTES+1)
    await file.close()
    if not data or len(data)>MAX_BYTES:
        raise HTTPException(413, "Demo audio must be nonempty and at most 10 MB")
    return enqueue_analysis(tasks, identity, data, file.content_type or "", scenario_id, mode,
                            clients=getattr(request.state, "amd_clients", ()), consent=consent)


def enqueue_analysis(tasks, identity, data, content_type, scenario_id=None, mode="local", reference=None, reference_revision=None, expected_revision=None, clients=(), consent=False):
    if mode == "amd":
        authorize_amd(consent)
    if not _DEMO_SLOTS.acquire(blocking=False):
        raise HTTPException(429, "Two demo jobs are already running; wait for completion")
    try:
        with database() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (identity,)).fetchone()
            if not row or row["expires"] <= time.time():
                raise HTTPException(401, "Session expired")
            if reference is not None:
                document = json.loads(row["custom"])
                if (document["revision"] != expected_revision
                        or document["reference_version"] != reference_revision
                        or document["reference"] != reference.model_dump(mode="json")):
                    raise HTTPException(409, "Reference changed; reload before analyzing")
                document.update(evidence=None, reviewed=[], demo_decision=None)
                document["revision"] += 1
                db.execute("UPDATE sessions SET custom=? WHERE id=?", (json.dumps(document), identity))
            if row["state"] == "PROCESSING" or row["runs"] >= 3 or db.execute("SELECT count(*) FROM sessions WHERE state='PROCESSING'").fetchone()[0] >= 2:
                raise HTTPException(429, "At most three attempts per session and two concurrent demo jobs; wait or start a new session")
            if mode == "amd" and (row["amd_runs"] >= 2 or db.execute("SELECT count(*) FROM sessions WHERE state='PROCESSING' AND json_extract(payload,'$.mode')='amd'").fetchone()[0] >= 1):
                raise HTTPException(429, "At most two AMD runs per session and one concurrent AMD demo job; failed attempts also count")
            if mode == "amd":
                check_budget(db, clients, reserve=True)
            consented_at = time.time() if mode == "amd" else None
            shutil.rmtree(_root() / "quick" / identity, ignore_errors=True)
            db.execute("UPDATE sessions SET state='PROCESSING',runs=runs+1,amd_runs=amd_runs+?,payload=? WHERE id=?", (int(mode == "amd"), json.dumps({"scenario_id": scenario_id, "mode": mode, "consented_at": consented_at, "semantic_status": "pending_transcription" if mode == "amd" else "not_requested"}), identity))
        tasks.add_task(analyze_job, identity, data, content_type, scenario_id, mode, consented_at, reference, reference_revision)
    except BaseException:
        _DEMO_SLOTS.release()
        raise
    return {"state": "PROCESSING"}


@router.get("/audio")
def audio(identity: str = Depends(session)):
    report = get_session(identity)
    if not report.artifact:
        raise HTTPException(404, "No audio available")
    artifact = report.artifact
    path = AudioStore(_root() / "quick" / identity).path_for(artifact.sha256, artifact.format)
    try:
        original = path.read_bytes()
    except OSError:
        raise HTTPException(404, "Original audio missing or changed") from None
    if sha256(original).hexdigest() != artifact.sha256:
        raise HTTPException(404, "Original audio missing or changed")
    return Response(original, media_type=AUDIO_MIME[artifact.format], headers={"Cache-Control": "no-store"})


@router.delete("/session")
def delete_session(identity: str = Depends(session)):
    with database() as db:
        db.execute("DELETE FROM sessions WHERE id=?", (identity,))
        shutil.rmtree(_root() / "quick" / identity, ignore_errors=True)
    return {"deleted": True}


def recover_interrupted():
    # Supported deployment is one API process. In-process jobs cannot survive restart.
    with database() as db:
        for row in db.execute("SELECT id,payload FROM sessions WHERE state='PROCESSING'").fetchall():
            payload = json.loads(row["payload"])
            payload["error"] = "Server restarted during analysis. This run did not complete; retry within your remaining quota. A sent AMD request may still have been billed."
            if payload.get("mode") == "amd":
                payload["semantic_status"] = "interrupted"
            db.execute("UPDATE sessions SET state='FAILED',payload=? WHERE id=?", (json.dumps(payload), row["id"]))


if __name__ == "__main__":
    cleanup()
