"""SQLite MVP for authenticated, auditable human review decisions."""

from datetime import datetime, timezone
from contextlib import contextmanager
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import sqlite3
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from pydantic import Field

from .alignment import AlignmentRun, apply_confirmed_alignment, propose_alignment
from .audio import (AudioArtifact, AudioError, AudioStore, FasterWhisperProvider, AUDIO_MIME,
                    TranscriptionResult, transcribe_artifact)
from .acoustic import TargetedRecheckResult, targeted_recheck
from .engine import approved_evidence, observed_evidence, verify
from .providers import _load_project_env
from .schemas import (Decision, Finding, FindingStatus, Model, ReviewResult,
                      ScriptPolicy, VerificationRequest, HumanTranscriptInput, VerifiedTranscriptEvidence)

from .ui_contracts import WorkflowView, WorkflowSummary, PolicyRecord

router = APIRouter(prefix="/review", tags=["human-review"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root() -> Path:
    _load_project_env()
    return Path(os.getenv("DUBGUARD_DATA_DIR", ".dubguard-data")).resolve()


def _store():
    return ReviewStore(_root() / "review.sqlite3")


def reviewer(authorization: str | None = Header(default=None), request: Request = None) -> str:
    """MVP shared-secret authentication. Tokens and mappings live only in env."""
    _load_project_env()
    raw = os.getenv("DUBGUARD_REVIEW_TOKENS_JSON", "")
    if not raw:
        raise HTTPException(503, "Reviewer authentication is not configured")
    try:
        tokens = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(503, "Reviewer authentication configuration is invalid") from None
    if not isinstance(tokens, dict) or not tokens or not all(
            isinstance(name, str) and name and isinstance(secret, str) and len(secret) >= 24
            for name, secret in tokens.items()):
        raise HTTPException(503, "Reviewer authentication configuration is invalid")
    supplied = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    if not authorization and request is not None:
        from .operator_auth import cookie_identity
        return cookie_identity(request)
    matched = [name for name, secret in tokens.items() if hmac.compare_digest(secret.encode(), supplied.encode())]
    if len(matched) != 1:
        raise HTTPException(401, "Valid reviewer bearer token required")
    return matched[0]


class ReviewStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.parent.chmod(0o700)
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS records (
              id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
              created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS workflows (
              id TEXT PRIMARY KEY, policy_record_id TEXT NOT NULL, audio_record_id TEXT NOT NULL,
              transcription_record_id TEXT, alignment_record_id TEXT,
              confirmed_alignment_record_id TEXT,
              acoustic_record_id TEXT, verification_record_id TEXT,
              state TEXT NOT NULL, supersedes TEXT,
              created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS finding_decisions (
              id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, finding_index INTEGER NOT NULL,
              verification_record_id TEXT NOT NULL,
              decision TEXT NOT NULL, reason TEXT NOT NULL, reviewer_id TEXT NOT NULL,
              created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS approvals (
              id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, decision TEXT NOT NULL,
              reviewer_id TEXT NOT NULL, reason TEXT NOT NULL, script_id TEXT NOT NULL,
              script_revision TEXT NOT NULL, policy_id TEXT NOT NULL,
              policy_revision TEXT NOT NULL, audio_sha256 TEXT NOT NULL,
              status TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit_events (
              id TEXT PRIMARY KEY, workflow_id TEXT, event TEXT NOT NULL,
              reviewer_id TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
            """)
            db.execute("BEGIN IMMEDIATE")  # executescript commits its preceding transaction
            # Additive migration: preserve all legacy evidence and approval history.
            for table, column, definition in (
                ("workflows", "evidence_record_id", "TEXT"),
                ("workflows", "acoustic_resolution_record_id", "TEXT"),
                ("workflows", "revision", "INTEGER NOT NULL DEFAULT 0"),
                ("approvals", "evidence_record_id", "TEXT"),
                ("approvals", "verification_record_id", "TEXT"),
                ("approvals", "input_snapshot", "TEXT"),
            ):
                if column not in {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            db.execute("CREATE TABLE IF NOT EXISTS verification_inputs (id TEXT PRIMARY KEY, snapshot TEXT NOT NULL)")
            db.execute("UPDATE approvals SET status='LEGACY_UNVERIFIED' WHERE status='CURRENT' AND input_snapshot IS NULL")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def add_record(self, kind: str, payload: dict) -> str:
        identity = uuid4().hex
        with self._connect() as db:
            db.execute("INSERT INTO records VALUES (?,?,?,?)", (identity, kind,
                       json.dumps(payload, sort_keys=True), _now()))
        return identity

    def record(self, identity: str, kind: str) -> dict:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM records WHERE id=? AND kind=?", (identity, kind)).fetchone()
        if not row:
            raise KeyError(f"Unknown {kind} record")
        return json.loads(row["payload"])

    def event(self, workflow_id: str | None, event: str, reviewer_id: str, detail: dict) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (
                uuid4().hex, workflow_id, event, reviewer_id, json.dumps(detail, sort_keys=True), _now()))

    def workflow(self, identity: str) -> dict:
        with self._connect() as db:
            row = db.execute("SELECT * FROM workflows WHERE id=?", (identity,)).fetchone()
        if not row:
            raise KeyError("Unknown workflow")
        return dict(row)

    def create_workflow(self, policy_record_id: str, audio_record_id: str,
                        reviewer_id: str, supersedes: str | None = None) -> str:
        policy = self.record(policy_record_id, "approved_policy")
        artifact = self.record(audio_record_id, "audio_artifact")
        identity = uuid4().hex
        with self._connect() as db:
            if supersedes:
                if not db.execute("SELECT id FROM workflows WHERE id=?", (supersedes,)).fetchone():
                    raise KeyError("Unknown superseded workflow")
                db.execute("UPDATE approvals SET status='SUPERSEDED' WHERE workflow_id=? AND status='CURRENT'",
                           (supersedes,))
                db.execute("UPDATE workflows SET state='SUPERSEDED' WHERE id=?", (supersedes,))
            db.execute("INSERT INTO workflows (id,policy_record_id,audio_record_id,transcription_record_id,alignment_record_id,confirmed_alignment_record_id,acoustic_record_id,verification_record_id,state,supersedes,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                identity, policy_record_id, audio_record_id, None, None, None, None, None,
                "DRAFT", supersedes, _now()))
        self.event(identity, "WORKFLOW_CREATED", reviewer_id, {
            "script_revision": policy["script"]["revision"],
            "policy_revision": policy["policy"]["revision"],
            "audio_sha256": artifact["sha256"], "supersedes": supersedes})
        return identity

    @staticmethod
    def _snapshot(workflow: dict) -> dict:
        return {key: workflow[key] for key in (
            "policy_record_id", "audio_record_id", "transcription_record_id",
            "alignment_record_id", "confirmed_alignment_record_id",
            "acoustic_record_id", "evidence_record_id", "acoustic_resolution_record_id", "revision")}

    @staticmethod
    def _read(db, identity: str, kind: str) -> dict:
        row = db.execute("SELECT payload FROM records WHERE id=? AND kind=?", (identity, kind)).fetchone()
        if not row:
            raise ValueError(f"Missing {kind} record")
        return json.loads(row["payload"])

    @staticmethod
    def _active(db, identity: str) -> dict:
        row = db.execute("SELECT * FROM workflows WHERE id=?", (identity,)).fetchone()
        if not row or row["state"] in {"APPROVED", "REJECTED", "SUPERSEDED"}:
            raise ValueError("workflow is unavailable or finalized; create a superseding workflow")
        return dict(row)

    def set_record(self, workflow_id: str, field: str, record_id: str,
                   state: str, reviewer_id: str, expected_revision: int | None = None) -> None:
        kinds = {"transcription_record_id": "transcription", "alignment_record_id": "alignment",
                 "confirmed_alignment_record_id": "confirmed_alignment", "acoustic_record_id": "acoustic",
                 "verification_record_id": "verification", "evidence_record_id": "verified_evidence",
                 "acoustic_resolution_record_id": "acoustic_resolution"}
        if field not in kinds:
            raise ValueError("invalid workflow record field")
        with self._connect() as db:
            workflow = self._active(db, workflow_id)
            if expected_revision is not None and workflow["revision"] != expected_revision:
                raise ValueError("stale workflow revision; reload before retrying")
            pending = {"TRANSCRIBING": "transcription_record_id", "VERIFYING": "verification_record_id",
                       "ACOUSTIC_RECHECKING": "acoustic_record_id"}
            if workflow["state"] in pending and field != pending[workflow["state"]]:
                raise ValueError("processing job is pending; inputs cannot change until completion")
            self._read(db, record_id, kinds[field])
            if field == "verification_record_id":
                db.execute("INSERT INTO verification_inputs VALUES (?,?)", (
                    record_id, json.dumps(self._snapshot(workflow), sort_keys=True)))
                db.execute("UPDATE workflows SET verification_record_id=?,state=? WHERE id=?",
                           (record_id, state, workflow_id))
            else:
                # Every input mutation invalidates prior run decisions. Raw records remain immutable.
                clear = ",verification_record_id=NULL"
                if field != "acoustic_resolution_record_id":
                    clear += ",acoustic_resolution_record_id=NULL"
                if field == "transcription_record_id":
                    clear += ",alignment_record_id=NULL,confirmed_alignment_record_id=NULL,acoustic_record_id=NULL,evidence_record_id=NULL"
                if field == "confirmed_alignment_record_id":
                    clear += ",acoustic_record_id=NULL"
                db.execute(f"UPDATE workflows SET {field}=?,state=?,revision=revision+1{clear} WHERE id=?",
                           (record_id, state, workflow_id))
            db.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (
                uuid4().hex, workflow_id, field.upper(), reviewer_id,
                json.dumps({"record_id": record_id}), _now()))

    def mark_state(self, workflow_id: str, expected: set[str], state: str,
                   reviewer_id: str) -> None:
        with self._connect() as db:
            workflow = self._active(db, workflow_id)
            if workflow["state"] not in expected:
                raise ValueError("workflow is not in a state eligible for this operation")
            # Starting a job invalidates readiness immediately, including when it fails.
            db.execute("UPDATE workflows SET state=?,verification_record_id=NULL,revision=revision+1 WHERE id=?",
                       (state, workflow_id))
            db.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (
                uuid4().hex, workflow_id, "STATE_CHANGED", reviewer_id, json.dumps({"state": state}), _now()))

    def fail_job(self, workflow_id: str, expected_state: str, failed_state: str,
                 reviewer_id: str, expected_revision: int) -> None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
            if row and row["state"] == expected_state and row["revision"] == expected_revision:
                db.execute("UPDATE workflows SET state=?,verification_record_id=NULL,revision=revision+1 WHERE id=?",
                           (failed_state, workflow_id))
            db.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (
                uuid4().hex, workflow_id, failed_state, reviewer_id,
                json.dumps({"job_input_revision": expected_revision, "note": "Failure never restores readiness"}), _now()))

    def recover_interrupted(self) -> int:
        """Single-worker startup recovery; never invent a completed job or replay inference."""
        failed = {"TRANSCRIBING": "TRANSCRIPTION_FAILED", "VERIFYING": "VERIFICATION_FAILED",
                  "ACOUSTIC_RECHECKING": "ACOUSTIC_RECHECK_FAILED"}
        with self._connect() as db:
            rows = db.execute("SELECT id,state FROM workflows WHERE state IN ('TRANSCRIBING','VERIFYING','ACOUSTIC_RECHECKING')").fetchall()
            for row in rows:
                state = failed[row["state"]]
                db.execute("UPDATE workflows SET state=?,verification_record_id=NULL,revision=revision+1 WHERE id=?", (state, row["id"]))
                db.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (
                    uuid4().hex, row["id"], "INTERRUPTED_ON_RESTART", "system",
                    json.dumps({"previous_state": row["state"], "state": state,
                                "note": "No automatic retry; inspect evidence and create a superseding workflow if needed."}), _now()))
        return len(rows)

    def _checked_run(self, db, workflow: dict) -> ReviewResult:
        if workflow["state"] not in {"IN_REVIEW", "READY_FOR_SIGNOFF"}:
            raise ValueError("processing is incomplete or failed")
        run = workflow["verification_record_id"]
        row = db.execute("SELECT snapshot FROM verification_inputs WHERE id=?", (run,)).fetchone()
        if not row or json.loads(row["snapshot"]) != self._snapshot(workflow):
            raise ValueError("current verification of exact evidence is required")
        return ReviewResult.model_validate(self._read(db, run, "verification"))

    def decide_finding(self, workflow_id: str, index: int, decision: str,
                       reason: str, reviewer_id: str, expected_run: str | None = None) -> str:
        identity = uuid4().hex
        with self._connect() as db:
            workflow = self._active(db, workflow_id)
            result = self._checked_run(db, workflow)
            if expected_run is not None and workflow["verification_record_id"] != expected_run:
                raise ValueError("stale verification run")
            if not 0 <= index < len(result.findings):
                raise ValueError("unknown finding index")
            if decision == "ACCEPTED_AS_CORRECT" and result.findings[index].status != FindingStatus.SATISFIED:
                raise ValueError("unresolved or critical findings require corrected evidence or a new recording; ordinary acceptance cannot override them")
            db.execute("INSERT INTO finding_decisions VALUES (?,?,?,?,?,?,?,?)", (
                identity, workflow_id, index, workflow["verification_record_id"],
                decision, reason, reviewer_id, _now()))
            db.execute("UPDATE workflows SET state='IN_REVIEW' WHERE id=?", (workflow_id,))
            db.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (
                uuid4().hex, workflow_id, "FINDING_DECIDED", reviewer_id,
                json.dumps({"index": index, "decision": decision, "reason": reason}), _now()))
        return identity

    def signoff(self, workflow_id: str, decision: str, reason: str, reviewer_id: str, expected_run: str | None = None) -> str:
        # One write transaction spans eligibility, input snapshot, and finalization.
        # Repeated/concurrent signoffs serialize and observe the finalized state.
        with self._connect() as db:
            workflow = self._active(db, workflow_id)
            result = self._checked_run(db, workflow)
            if expected_run is not None and workflow["verification_record_id"] != expected_run:
                raise ValueError("stale verification run")
            if decision == "APPROVED":
                if result.decision != Decision.PASS_CANDIDATE or any(
                        f.status != FindingStatus.SATISFIED for f in result.findings):
                    raise ValueError("critical or unresolved checks block approval; use corrective workflow")
                evidence = VerifiedTranscriptEvidence.model_validate(self._read(
                    db, workflow["evidence_record_id"], "verified_evidence"))
                if evidence.raw_transcription_record_id != workflow["transcription_record_id"]:
                    raise ValueError("human evidence refers to stale transcription")
                if evidence.transcript.completeness != "complete" or not evidence.transcript.segments:
                    raise ValueError("human verification of complete spoken content is required")
                if any(s.uncertain or not s.text.strip() for s in evidence.transcript.segments):
                    raise ValueError("human evidence still contains uncertainty")
                transcription = TranscriptionResult.model_validate(self._read(
                    db, workflow["transcription_record_id"], "transcription"))
                if not transcription.coverage.complete_processing:
                    raise ValueError("audio processing coverage is incomplete (not an accuracy metric)")
                rows = db.execute("SELECT finding_index,decision FROM finding_decisions WHERE workflow_id=? AND verification_record_id=? ORDER BY created_at,id",
                                  (workflow_id, workflow["verification_record_id"])).fetchall()
                latest = {row["finding_index"]: row["decision"] for row in rows}
                if any(latest.get(i) != "ACCEPTED_AS_CORRECT" for i in range(len(result.findings))):
                    raise ValueError("all findings require explicit human review; zero findings may proceed directly to explicit signoff")
            policy = ScriptPolicy.model_validate(self._read(db, workflow["policy_record_id"], "approved_policy"))
            if decision == "APPROVED":
                independent_check = verify(VerificationRequest(**policy.model_dump(mode="json"), transcript=evidence.transcript))
                if independent_check.decision != Decision.PASS_CANDIDATE:
                    raise ValueError("required deterministic checks on human evidence are not satisfied")
            artifact = AudioArtifact.model_validate(self._read(db, workflow["audio_record_id"], "audio_artifact"))
            path = AudioStore(_root() / "artifacts").path_for(artifact.sha256, artifact.format)
            if not path.exists() or sha256(path.read_bytes()).hexdigest() != artifact.sha256:
                raise ValueError("original audio is missing or changed")
            if decision == "APPROVED" and (evidence.audio_sha256 != artifact.sha256 or transcription.artifact.sha256 != artifact.sha256):
                raise ValueError("evidence is bound to different audio")
            if (result.script_id, result.script_revision, result.policy_id, result.policy_revision) != (
                    policy.script.id, policy.script.revision, policy.policy.id, policy.policy.revision):
                raise ValueError("verification policy revisions differ")
            identity = uuid4().hex
            db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                identity, workflow_id, decision, reviewer_id, reason,
                policy.script.id, policy.script.revision, policy.policy.id,
                policy.policy.revision, artifact.sha256, "CURRENT", _now(),
                workflow["evidence_record_id"], workflow["verification_record_id"],
                json.dumps(self._snapshot(workflow), sort_keys=True)))
            db.execute("UPDATE workflows SET state=? WHERE id=?", (decision, workflow_id))
            db.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (
                uuid4().hex, workflow_id, "FINAL_SIGNOFF", reviewer_id,
                json.dumps({"approval_id": identity, "decision": decision}), _now()))
        return identity

    def details(self, identity: str) -> dict:
        workflow = self.workflow(identity)
        with self._connect() as db:
            decisions = [dict(row) for row in db.execute(
                "SELECT * FROM finding_decisions WHERE workflow_id=? ORDER BY created_at,id", (identity,))]
            approvals = [dict(row) for row in db.execute(
                "SELECT * FROM approvals WHERE workflow_id=? ORDER BY created_at,id", (identity,))]
            events = [dict(row) for row in db.execute(
                "SELECT * FROM audit_events WHERE workflow_id=? ORDER BY created_at,id", (identity,))]
            history = []
            for event in events:
                record_id = json.loads(event["detail"]).get("record_id")
                if record_id:
                    record = db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
                    if record:
                        history.append({"id": record["id"], "kind": record["kind"],
                                        "payload": json.loads(record["payload"]), "created_at": record["created_at"]})
        return {"workflow": workflow, "finding_decisions": decisions,
                "approvals": approvals, "audit_events": events, "record_history": history}

    def audit(self, *, workflow_id: str | None = None, limit: int = 100) -> list[dict]:
        with self._connect() as db:
            if workflow_id is None:
                rows = db.execute("SELECT * FROM audit_events ORDER BY created_at DESC,id DESC LIMIT ?",
                                  (limit,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM audit_events WHERE workflow_id=? ORDER BY created_at DESC,id DESC LIMIT ?",
                                  (workflow_id, limit)).fetchall()
        return [dict(row) for row in rows]


class WorkflowCreate(Model):
    policy_record_id: str
    audio_record_id: str
    supersedes: str | None = None


class FindingDecisionInput(Model):
    verification_record_id: str
    decision: str = Field(pattern="^(ACCEPTED_AS_CORRECT|CORRECTION_REQUIRED|RERECORD_REQUIRED|ESCALATED)$")
    reason: str = Field(min_length=1, max_length=2000)


class SignoffInput(Model):
    verification_record_id: str
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    reason: str = Field(min_length=1, max_length=2000)


class AlignmentConfirmationInput(Model):
    confirmations: dict[str, str]
    reason: str = Field(min_length=1, max_length=2000)


def _handle_key(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from None
    except (ValueError, AudioError) as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("/policy-drafts")
def policy_draft(payload: ScriptPolicy, origin: Literal["human", "ai"] = "human",
                 identity: str = Depends(reviewer)):
    store = _store()
    record_id = store.add_record("policy_draft", payload.model_dump(mode="json"))
    store.event(None, "POLICY_DRAFTED", identity, {"record_id": record_id, "origin": origin})
    return {"record_id": record_id, "status": "DRAFT", "origin": origin}


@router.post("/policy-drafts/{record_id}/revise")
def revise_policy(record_id: str, payload: ScriptPolicy, identity: str = Depends(reviewer)):
    store = _store()
    _handle_key(store.record, record_id, "policy_draft")
    revised = store.add_record("policy_draft", payload.model_dump(mode="json"))
    store.event(None, "POLICY_DRAFT_REVISED", identity, {"prior_record_id": record_id,
                "record_id": revised})
    return {"record_id": revised, "status": "DRAFT", "revises": record_id}


@router.post("/policy-drafts/{record_id}/approve")
def approve_policy(record_id: str, identity: str = Depends(reviewer)):
    store = _store()
    payload = ScriptPolicy.model_validate(_handle_key(store.record, record_id, "policy_draft"))
    payload.policy.approved_by = identity
    for instruction in payload.script.instructions:
        for variant in instruction.approved_variants:
            variant.approved_by = identity
    approved = store.add_record("approved_policy", payload.model_dump(mode="json"))
    store.event(None, "POLICY_APPROVED", identity, {"draft_id": record_id, "record_id": approved})
    return {"record_id": approved, "status": "HUMAN_APPROVED", "reviewer_id": identity}


@router.get("/policies/{record_id}")
def get_approved_policy(record_id: str, identity: str = Depends(reviewer)):
    return {"record_id": record_id, "policy": _handle_key(_store().record,
                                                            record_id, "approved_policy")}


@router.post("/artifacts")
async def upload_audio(file: UploadFile = File(...), identity: str = Depends(reviewer)):
    limit = int(os.getenv("DUBGUARD_MAX_UPLOAD_BYTES", "25000000"))
    data = await file.read(limit + 1)
    await file.close()
    try:
        artifact = await run_in_threadpool(AudioStore(_root() / "artifacts").ingest, data, content_type=file.content_type)
    except AudioError as exc:
        raise HTTPException(422, str(exc)) from None
    store = _store()
    record_id = store.add_record("audio_artifact", artifact.model_dump(mode="json"))
    store.event(None, "AUDIO_INGESTED", identity, {"record_id": record_id, "sha256": artifact.sha256})
    return {"record_id": record_id, "artifact": artifact}


@router.get("/artifacts/{record_id}/audio")
def get_audio(record_id: str, identity: str = Depends(reviewer)):
    artifact = AudioArtifact.model_validate(_handle_key(_store().record, record_id, "audio_artifact"))
    path = AudioStore(_root() / "artifacts").path_for(artifact.sha256, artifact.format)
    data = path.read_bytes() if path.exists() else b""
    if sha256(data).hexdigest() != artifact.sha256:
        raise HTTPException(404, "Original audio is missing or changed")
    return Response(content=data, media_type=AUDIO_MIME[artifact.format], headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/artifacts/{record_id}")
def get_artifact(record_id: str, identity: str = Depends(reviewer)):
    return {"record_id": record_id, "artifact": _handle_key(_store().record,
                                                               record_id, "audio_artifact")}


@router.post("/workflows")
def create_workflow(payload: WorkflowCreate, identity: str = Depends(reviewer)):
    store = _store()
    workflow_id = _handle_key(store.create_workflow, payload.policy_record_id,
                              payload.audio_record_id, identity, payload.supersedes)
    return {"workflow_id": workflow_id, "state": "DRAFT"}


def _transcribe_job(workflow_id: str, identity: str):
    store = _store()
    workflow = store.workflow(workflow_id)
    artifact = AudioArtifact.model_validate(store.record(workflow["audio_record_id"], "audio_artifact"))
    try:
        result = transcribe_artifact(AudioStore(_root() / "artifacts"), artifact)
        record_id = store.add_record("transcription", result.model_dump(mode="json"))
        _handle_key(store.set_record, workflow_id, "transcription_record_id", record_id, "ANALYZED", identity, expected_revision=workflow["revision"])
    except Exception:
        store.event(workflow_id, "TRANSCRIPTION_FAILED", identity, {"reason": "Processing failed; inspect server logs privately"})
        store.fail_job(workflow_id, "TRANSCRIBING", "TRANSCRIPTION_FAILED", identity, workflow["revision"])


@router.post("/workflows/{workflow_id}/transcribe")
def start_transcription(workflow_id: str, tasks: BackgroundTasks, identity: str = Depends(reviewer)):
    workflow = _handle_key(_store().workflow, workflow_id)
    if workflow["state"] != "DRAFT":
        raise HTTPException(409, "transcription can start only from DRAFT")
    _handle_key(_store().mark_state, workflow_id, {"DRAFT"}, "TRANSCRIBING", identity)
    tasks.add_task(_transcribe_job, workflow_id, identity)
    _store().event(workflow_id, "TRANSCRIPTION_QUEUED", identity, {})
    return {"state": "QUEUED", "note": "In-process background task; use an external queue for durable deployment."}


@router.get("/workflows/{workflow_id}", response_model=WorkflowView)
def workflow_details(workflow_id: str, identity: str = Depends(reviewer)):
    store = _store()
    details = _handle_key(store.details, workflow_id)
    workflow = details["workflow"]
    details["approved_policy"] = store.record(workflow["policy_record_id"], "approved_policy")
    details["audio_artifact"] = store.record(workflow["audio_record_id"], "audio_artifact")
    for field, kind in (("transcription_record_id", "transcription"),
                        ("alignment_record_id", "alignment"),
                        ("evidence_record_id", "verified_evidence"),
                        ("confirmed_alignment_record_id", "confirmed_alignment"),
                        ("acoustic_record_id", "acoustic"),
                        ("acoustic_resolution_record_id", "acoustic_resolution"),
                        ("verification_record_id", "verification")):
        if workflow[field]:
            details[kind] = store.record(workflow[field], kind)
    return details


@router.get("/audit-events")
def audit_events(workflow_id: str | None = None, limit: int = 100,
                 identity: str = Depends(reviewer)):
    if not 1 <= limit <= 500:
        raise HTTPException(422, "limit must be between 1 and 500")
    return {"events": _store().audit(workflow_id=workflow_id, limit=limit),
            "note": "SQLite audit history is not tamper-proof."}


@router.post("/workflows/{workflow_id}/alignments/propose")
def propose_workflow_alignment(workflow_id: str, identity: str = Depends(reviewer)):
    store = _store()
    workflow = _handle_key(store.workflow, workflow_id)
    if not workflow["transcription_record_id"]:
        raise HTTPException(409, "transcription is required")
    policy = ScriptPolicy.model_validate(store.record(workflow["policy_record_id"], "approved_policy"))
    transcription = TranscriptionResult.model_validate(store.record(workflow["transcription_record_id"], "transcription"))
    run = propose_alignment(policy.script, transcription.transcript)
    record_id = store.add_record("alignment", run.model_dump(mode="json"))
    _handle_key(store.set_record, workflow_id, "alignment_record_id", record_id, "IN_REVIEW", identity, expected_revision=workflow["revision"])
    return {"record_id": record_id, "alignment": run}


@router.post("/workflows/{workflow_id}/alignments/confirm")
def confirm_alignment(workflow_id: str, payload: AlignmentConfirmationInput,
                      identity: str = Depends(reviewer)):
    store = _store()
    workflow = _handle_key(store.workflow, workflow_id)
    if not workflow["transcription_record_id"]:
        raise HTTPException(409, "transcription is required")
    policy = ScriptPolicy.model_validate(store.record(workflow["policy_record_id"], "approved_policy"))
    transcription = TranscriptionResult.model_validate(store.record(workflow["transcription_record_id"], "transcription"))
    try:
        apply_confirmed_alignment(transcription.transcript, payload.confirmations, policy.script)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    record_id = store.add_record("confirmed_alignment", {"confirmations": payload.confirmations,
                                                           "reviewer_id": identity, "reason": payload.reason,
                                                           "transcription_record_id": workflow["transcription_record_id"]})
    _handle_key(store.set_record, workflow_id, "confirmed_alignment_record_id", record_id, "IN_REVIEW", identity, expected_revision=workflow["revision"])
    store.event(workflow_id, "ALIGNMENT_CONFIRMED", identity, {"record_id": record_id,
                "segment_ids": list(payload.confirmations), "reason": payload.reason})
    return {"record_id": record_id, "status": "CONFIRMED"}


def _acoustic_job(workflow_id: str, identity: str, model_id: str):
    store = _store()
    workflow = store.workflow(workflow_id)
    try:
        transcription = TranscriptionResult.model_validate(store.record(
            workflow["transcription_record_id"], "transcription"))
        policy = ScriptPolicy.model_validate(store.record(workflow["policy_record_id"], "approved_policy"))
        confirmation = store.record(workflow["confirmed_alignment_record_id"], "confirmed_alignment")
        result = targeted_recheck(AudioStore(_root() / "artifacts"), transcription.artifact,
                                  policy.policy, transcription.transcript, confirmation["confirmations"],
                                  FasterWhisperProvider(model_id, local_files_only=True),
                                  primary_provider=transcription.provider, primary_model=transcription.model)
        record_id = store.add_record("acoustic", result.model_dump(mode="json"))
        _handle_key(store.set_record, workflow_id, "acoustic_record_id", record_id, "IN_REVIEW", identity, expected_revision=workflow["revision"])
        _run_verification(workflow_id, identity, False)
    except Exception:
        store.event(workflow_id, "ACOUSTIC_RECHECK_FAILED", identity, {"reason": "Processing failed; inspect server logs privately"})
        store.fail_job(workflow_id, "ACOUSTIC_RECHECKING", "ACOUSTIC_RECHECK_FAILED", identity, workflow["revision"])


@router.post("/workflows/{workflow_id}/acoustic-recheck")
def start_acoustic_recheck(workflow_id: str, tasks: BackgroundTasks,
                           identity: str = Depends(reviewer)):
    model_id = os.getenv("DUBGUARD_SECONDARY_WHISPER_MODEL", "")
    if not model_id:
        raise HTTPException(503, "Configure a locally available independent secondary Whisper model")
    workflow = _handle_key(_store().workflow, workflow_id)
    if not workflow["transcription_record_id"] or not workflow["confirmed_alignment_record_id"]:
        raise HTTPException(409, "transcription and confirmed alignment are required")
    _handle_key(_store().mark_state, workflow_id, {"IN_REVIEW", "READY_FOR_SIGNOFF", "ANALYZED"},
                "ACOUSTIC_RECHECKING", identity)
    tasks.add_task(_acoustic_job, workflow_id, identity, model_id)
    return {"state": "QUEUED", "note": "Independent recognizer receives audio only, not expected words."}


def _run_verification(workflow_id: str, identity: str, hybrid: bool) -> tuple[str, ReviewResult]:
    store = _store()
    workflow = _handle_key(store.workflow, workflow_id)
    if not workflow["transcription_record_id"]:
        raise HTTPException(409, "transcription is required")
    policy = ScriptPolicy.model_validate(store.record(workflow["policy_record_id"], "approved_policy"))
    transcription = TranscriptionResult.model_validate(store.record(workflow["transcription_record_id"], "transcription"))
    transcript = transcription.transcript
    if workflow["confirmed_alignment_record_id"]:
        confirmation = store.record(workflow["confirmed_alignment_record_id"], "confirmed_alignment")
        if confirmation["transcription_record_id"] != workflow["transcription_record_id"]:
            raise HTTPException(409, "alignment refers to an outdated transcription")
        transcript = apply_confirmed_alignment(transcript, confirmation["confirmations"], policy.script)
    if workflow["evidence_record_id"]:
        evidence = VerifiedTranscriptEvidence.model_validate(store.record(workflow["evidence_record_id"], "verified_evidence"))
        if evidence.raw_transcription_record_id != workflow["transcription_record_id"]:
            raise HTTPException(409, "human evidence refers to stale transcription")
        transcript = evidence.transcript
    request = VerificationRequest(**policy.model_dump(mode="json"), transcript=transcript)
    result = verify(request, hybrid=hybrid)
    if workflow["acoustic_record_id"]:
        acoustic = TargetedRecheckResult.model_validate(store.record(workflow["acoustic_record_id"], "acoustic"))
        instructions = {i.id: i for i in policy.script.instructions}
        primary_segments = {s.id: s for s in transcription.transcript.segments}
        secondary_segments = {s.id: s for s in acoustic.secondary_transcript.segments}
        resolved = set()
        if workflow["acoustic_resolution_record_id"]:
            resolution = store.record(workflow["acoustic_resolution_record_id"], "acoustic_resolution")
            if (resolution["evidence_record_id"] == workflow["evidence_record_id"] and
                    resolution["acoustic_record_id"] == workflow["acoustic_record_id"]):
                resolved = set(resolution["requirement_ids"])
        for requirement_id in resolved:
            result.findings.append(Finding(rule_id="ACOUSTIC.HUMAN_RESOLVED", status=FindingStatus.SATISFIED,
                constraint_id=requirement_id, explanation="Authenticated listener resolved acoustic evidence against the linked human transcript revision. Original hypotheses remain in history."))
        for disagreement in acoustic.assessment.disagreements:
            if disagreement.requirement_id in resolved:
                continue
            spans = [observed_evidence(primary_segments[disagreement.primary_segment_id], disagreement.instruction_id)]
            if disagreement.secondary_segment_id:
                spans.append(observed_evidence(secondary_segments[disagreement.secondary_segment_id],
                                               disagreement.instruction_id))
            result.findings.append(Finding(rule_id="ACOUSTIC.DISAGREEMENT", status=FindingStatus.UNRESOLVED,
                constraint_id=disagreement.requirement_id,
                instruction_ids=[disagreement.instruction_id],
                approved=[approved_evidence(instructions[disagreement.instruction_id])], observed=spans,
                explanation=disagreement.explanation, provider=acoustic.secondary_provider))
        for requirement_id in acoustic.assessment.unresolved_requirement_ids:
            if requirement_id in resolved:
                continue
            constraint = next(c for c in policy.policy.constraints if c.id == requirement_id)
            if constraint.kind == "sequence":
                continue
            result.findings.append(Finding(rule_id="ACOUSTIC.UNRESOLVED", status=FindingStatus.UNRESOLVED,
                constraint_id=requirement_id, instruction_ids=[constraint.instruction_id],
                approved=[approved_evidence(instructions[constraint.instruction_id])],
                explanation="Independent audio recheck lacks a reliable mapped hypothesis; listen to the original audio.",
                provider=acoustic.secondary_provider))
        if result.decision != Decision.CRITICAL_DEVIATION and any(
                f.rule_id.startswith("ACOUSTIC.") and f.status == FindingStatus.UNRESOLVED for f in result.findings):
            result.decision = Decision.REVIEW_REQUIRED
    record_id = store.add_record("verification", result.model_dump(mode="json"))
    _handle_key(store.set_record, workflow_id, "verification_record_id", record_id, "IN_REVIEW", identity, expected_revision=workflow["revision"])
    return record_id, result


def _verification_job(workflow_id: str, identity: str):
    workflow = _store().workflow(workflow_id)
    try:
        _run_verification(workflow_id, identity, True)
    except Exception:
        store = _store()
        store.event(workflow_id, "VERIFICATION_FAILED", identity, {"reason": "Processing failed; inspect server logs privately"})
        store.fail_job(workflow_id, "VERIFYING", "VERIFICATION_FAILED", identity, workflow["revision"])


@router.post("/workflows/{workflow_id}/verify")
def verify_workflow(workflow_id: str, tasks: BackgroundTasks,
                    mode: Literal["deterministic", "hybrid"] = "deterministic",
                    identity: str = Depends(reviewer)):
    if mode == "hybrid":
        _handle_key(_store().mark_state, workflow_id, {"ANALYZED", "IN_REVIEW", "READY_FOR_SIGNOFF"},
                    "VERIFYING", identity)
        tasks.add_task(_verification_job, workflow_id, identity)
        return {"state": "QUEUED", "mode": "hybrid"}
    record_id, result = _run_verification(workflow_id, identity, False)
    return {"record_id": record_id, "result": result}


@router.post("/workflows/{workflow_id}/findings/{index}/decision")
def decide_finding(workflow_id: str, index: int, payload: FindingDecisionInput,
                   identity: str = Depends(reviewer)):
    record_id = _handle_key(_store().decide_finding, workflow_id, index,
                            payload.decision, payload.reason, identity, expected_run=payload.verification_record_id)
    return {"decision_id": record_id, "status": payload.decision}


@router.post("/workflows/{workflow_id}/signoff")
def signoff(workflow_id: str, payload: SignoffInput, identity: str = Depends(reviewer)):
    approval_id = _handle_key(_store().signoff, workflow_id, payload.decision,
                              payload.reason, identity, expected_run=payload.verification_record_id)
    return {"approval_id": approval_id, "decision": payload.decision}


@router.post("/workflows/{workflow_id}/transcript-evidence")
def verify_spoken_transcript(workflow_id: str, payload: HumanTranscriptInput,
                             identity: str = Depends(reviewer)):
    """Attest actual spoken words, never edit them to resemble the approved script."""
    store = _store()
    workflow = _handle_key(store.workflow, workflow_id)
    if not workflow["transcription_record_id"]:
        raise HTTPException(409, "raw transcription is required")
    if payload.transcript.source != "manual":
        raise HTTPException(422, "human-reviewed transcript must use manual source")
    artifact = AudioArtifact.model_validate(store.record(workflow["audio_record_id"], "audio_artifact"))
    policy = ScriptPolicy.model_validate(store.record(workflow["policy_record_id"], "approved_policy"))
    known = {i.id for i in policy.script.instructions}
    for segment in payload.transcript.segments:
        if segment.instruction_id is not None and segment.instruction_id not in known:
            raise HTTPException(422, "unknown instruction reference")
        if segment.end_seconds is not None and segment.end_seconds > artifact.duration_seconds:
            raise HTTPException(422, "human timestamp exceeds original audio duration")
    path = AudioStore(_root() / "artifacts").path_for(artifact.sha256, artifact.format)
    if not path.exists() or sha256(path.read_bytes()).hexdigest() != artifact.sha256:
        raise HTTPException(409, "original audio is missing or changed")
    evidence = VerifiedTranscriptEvidence(transcript=payload.transcript,
        audio_sha256=artifact.sha256, raw_transcription_record_id=workflow["transcription_record_id"],
        previous_evidence_record_id=workflow["evidence_record_id"], reviewer_id=identity,
        reason=payload.reason, listened_to_original=True, created_at=_now())
    record_id = store.add_record("verified_evidence", evidence.model_dump(mode="json"))
    _handle_key(store.set_record, workflow_id, "evidence_record_id", record_id, "IN_REVIEW", identity,
                expected_revision=payload.expected_revision)
    return {"record_id": record_id, "evidence": evidence, "verification_required": True}


@router.get("/workflows", response_model=list[WorkflowSummary])
def list_workflows(limit: int = 50, offset: int = 0, identity: str = Depends(reviewer)):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(422, "Invalid pagination")
    store = _store()
    with store._connect() as db:
        rows = db.execute("SELECT * FROM workflows ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [{"workflow": dict(row), "policy": store._read(db, row["policy_record_id"], "approved_policy"),
                 "audio": store._read(db, row["audio_record_id"], "audio_artifact")} for row in rows]


@router.get("/policy-records", response_model=list[PolicyRecord])
def list_policy_records(limit: int = 100, identity: str = Depends(reviewer)):
    if not 1 <= limit <= 100:
        raise HTTPException(422, "Invalid limit")
    with _store()._connect() as db:
        rows = db.execute("SELECT * FROM records WHERE kind IN ('policy_draft','approved_policy') ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]


@router.get("/workflows/{workflow_id}/export", response_model=WorkflowView)
def export_workflow(workflow_id: str, identity: str = Depends(reviewer)):
    return workflow_details(workflow_id, identity)


class AcousticResolutionInput(Model):
    expected_revision: int = Field(ge=0)
    evidence_record_id: str
    acoustic_record_id: str
    requirement_ids: list[str] = Field(min_length=1)
    listened_to_original: Literal[True]
    reason: str = Field(min_length=1, max_length=2000)


@router.post("/workflows/{workflow_id}/acoustic-resolution")
def resolve_acoustic(workflow_id: str, payload: AcousticResolutionInput, identity: str = Depends(reviewer)):
    store = _store()
    workflow = _handle_key(store.workflow, workflow_id)
    if (workflow["evidence_record_id"] != payload.evidence_record_id or
            workflow["acoustic_record_id"] != payload.acoustic_record_id):
        raise HTTPException(409, "Resolution must reference current human and acoustic evidence")
    evidence = VerifiedTranscriptEvidence.model_validate(_handle_key(store.record, payload.evidence_record_id, "verified_evidence"))
    acoustic = TargetedRecheckResult.model_validate(_handle_key(store.record, payload.acoustic_record_id, "acoustic"))
    policy = ScriptPolicy.model_validate(store.record(workflow["policy_record_id"], "approved_policy"))
    affected = {d.requirement_id for d in acoustic.assessment.disagreements} | set(acoustic.assessment.unresolved_requirement_ids)
    if not set(payload.requirement_ids) <= affected or len(set(payload.requirement_ids)) != len(payload.requirement_ids):
        raise HTTPException(422, "Resolve only existing unique acoustic requirement IDs")
    from .engine import uncertainty
    request = VerificationRequest(**policy.model_dump(mode="json"), transcript=evidence.transcript)
    for requirement_id in payload.requirement_ids:
        constraint = next(c for c in policy.policy.constraints if c.id == requirement_id)
        ids = constraint.instruction_ids if constraint.kind == "sequence" else [constraint.instruction_id]
        for instruction_id in ids:
            segments = [s for s in evidence.transcript.segments if s.instruction_id == instruction_id]
            if len(segments) != 1 or uncertainty(segments[0], request) or evidence.transcript.completeness != "complete":
                raise HTTPException(409, "Each acoustic requirement needs complete, unambiguous, mapped human evidence")
    record_id = store.add_record("acoustic_resolution", {**payload.model_dump(mode="json"), "reviewer_id": identity, "created_at": _now()})
    _handle_key(store.set_record, workflow_id, "acoustic_resolution_record_id", record_id,
                "IN_REVIEW", identity, expected_revision=payload.expected_revision)
    return {"record_id": record_id, "verification_required": True}
