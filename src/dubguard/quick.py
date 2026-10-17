"""Bounded, capability-authenticated demonstration sessions; never review approvals."""
from contextlib import contextmanager
from hashlib import sha256
import hmac
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

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import Response
from .audio import AudioStore, AudioArtifact, AUDIO_MIME, transcribe_artifact
from .alignment import propose_alignment
from .engine import verify
from .providers import AMDTokenFactoryProvider, DisabledProvider
from .review import _root
from .schemas import VerificationRequest, ScriptPolicy
from .ui_contracts import DemoScenario, QuickReport

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
        if "amd_runs" not in {r["name"] for r in db.execute("PRAGMA table_info(sessions)")}:
            db.execute("ALTER TABLE sessions ADD COLUMN amd_runs INTEGER NOT NULL DEFAULT 0")
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


def session(authorization: str | None = Header(default=None)) -> str:
    cleanup()
    supplied = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    with database() as db:
        row = db.execute("SELECT id FROM sessions WHERE digest=? AND expires>?", (sha256(supplied.encode()).hexdigest(), time.time())).fetchone()
    if not row:
        raise HTTPException(401, "Quick Test session is missing or expired")
    return row["id"]


@router.get("/scenarios", response_model=list[DemoScenario])
def get_scenarios():
    return scenarios()


@router.post("/sessions")
def create_session(x_demo_code: str = Header(default="")):
    expected = os.getenv("DUBGUARD_DEMO_ACCESS_CODE", "")
    if len(expected) < 24:
        raise HTTPException(503, "Quick Test is disabled; operator must configure a demo access code")
    if not hmac.compare_digest(expected, x_demo_code):
        raise HTTPException(401, "Valid demo access code required")
    cleanup()
    token, identity = secrets.token_urlsafe(32), uuid4().hex
    with database() as db:
        if db.execute("SELECT count(*) FROM sessions").fetchone()[0] >= 20 or db.execute("SELECT count(*) FROM admissions").fetchone()[0] >= 30:
            raise HTTPException(429, "Demo session quota reached; retry later")
        now = time.time()
        db.execute("INSERT INTO admissions VALUES (?)", (now,))
        db.execute("INSERT INTO sessions (id,digest,expires,created,state,runs,payload) VALUES (?,?,?,?,?,?,?)", (identity, sha256(token.encode()).hexdigest(), now+TTL, now, "EMPTY", 0, "{}"))
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


def _analyze_job(identity: str, data: bytes, content_type: str, scenario_id: str, mode: str = "local", consented_at: float | None = None):
    # Each job has an isolated directory. A deleted/expired session cannot be resurrected.
    root = _root() / "quick" / identity
    payload = {"scenario_id": scenario_id, "mode": mode, "consented_at": consented_at,
               "semantic_status": "pending_transcription" if mode == "amd" else "not_requested"}
    state = "FAILED"
    try:
        policy = next(item.policy for item in scenarios() if item.id == scenario_id)
        audio = AudioStore(root)
        artifact = audio.ingest(data, content_type=content_type, max_bytes=MAX_BYTES, max_seconds=MAX_SECONDS)
        payload["artifact"] = artifact.model_dump(mode="json")
        result = transcribe_artifact(audio, artifact)
        payload["transcription"] = result.model_dump(mode="json")
        payload["alignment"] = propose_alignment(policy.script, result.transcript).model_dump(mode="json")
        request = VerificationRequest(**policy.model_dump(mode="json"), transcript=result.transcript)
        payload["verification"] = verify(request).model_dump(mode="json")
        if mode == "amd":
            payload["semantic_status"] = "processing"
            # Publish local evidence before the bounded remote call. Re-check consent/session lifetime.
            with database() as db:
                row = db.execute("SELECT expires FROM sessions WHERE id=?", (identity,)).fetchone()
                if not row or row["expires"] <= time.time():
                    shutil.rmtree(root, ignore_errors=True)
                    return
                db.execute("UPDATE sessions SET payload=? WHERE id=?", (json.dumps(payload), identity))
            provider = AMDTokenFactoryProvider(max_retries=0, timeout_seconds=40, max_output_tokens=1024)
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
        payload["error"] = "Analysis failed: unsupported audio, exceeded duration, or unavailable local ASR. No result is fabricated. Check local dependencies and cached model."
    with database() as db:
        row = db.execute("SELECT expires FROM sessions WHERE id=?", (identity,)).fetchone()
        if row and row["expires"] > time.time():
            db.execute("UPDATE sessions SET state=?,payload=? WHERE id=?", (state, json.dumps(payload), identity))
        else:
            shutil.rmtree(root, ignore_errors=True)


@router.post("/analyze")
async def analyze(tasks: BackgroundTasks, scenario_id: str, file: UploadFile = File(...),
                  mode: Literal["local", "amd"] = "local", consent: bool = False,
                  identity: str = Depends(session)):
    if scenario_id not in {item.id for item in scenarios()}:
        raise HTTPException(422, "Unknown demonstration scenario")
    if mode == "amd" and not consent:
        raise HTTPException(422, "Explicit consent is required to send script, policy and provisional transcript text to AMD. Original audio is never sent to DeepSeek.")
    data = await file.read(MAX_BYTES+1)
    await file.close()
    if not data or len(data)>MAX_BYTES:
        raise HTTPException(413, "Demo audio must be nonempty and at most 10 MB")
    if not _DEMO_SLOTS.acquire(blocking=False):
        raise HTTPException(429, "Two demo jobs are already running; wait for completion")
    try:
        with database() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (identity,)).fetchone()
            if not row or row["expires"] <= time.time():
                raise HTTPException(401, "Session expired")
            if row["state"] == "PROCESSING" or row["runs"] >= 3 or db.execute("SELECT count(*) FROM sessions WHERE state='PROCESSING'").fetchone()[0] >= 2:
                raise HTTPException(429, "At most three attempts per session and two concurrent demo jobs; wait or start a new session")
            if mode == "amd" and (row["amd_runs"] >= 2 or db.execute("SELECT count(*) FROM sessions WHERE state='PROCESSING' AND json_extract(payload,'$.mode')='amd'").fetchone()[0] >= 1):
                raise HTTPException(429, "At most two AMD runs per session and one concurrent AMD demo job; failed attempts also count")
            consented_at = time.time() if mode == "amd" else None
            shutil.rmtree(_root() / "quick" / identity, ignore_errors=True)
            db.execute("UPDATE sessions SET state='PROCESSING',runs=runs+1,amd_runs=amd_runs+?,payload=? WHERE id=?", (int(mode == "amd"), json.dumps({"scenario_id": scenario_id, "mode": mode, "consented_at": consented_at, "semantic_status": "pending_transcription" if mode == "amd" else "not_requested"}), identity))
        tasks.add_task(analyze_job, identity, data, file.content_type or "", scenario_id, mode, consented_at)
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
    if not path.exists() or sha256(path.read_bytes()).hexdigest() != artifact.sha256:
        raise HTTPException(404, "Original audio missing or changed")
    return Response(path.read_bytes(), media_type=AUDIO_MIME[artifact.format], headers={"Cache-Control": "no-store"})


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
