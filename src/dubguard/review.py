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

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import Field

from .alignment import AlignmentRun, apply_confirmed_alignment, propose_alignment
from .audio import (AudioArtifact, AudioError, AudioStore, FasterWhisperProvider,
                    TranscriptionResult, transcribe_artifact)
from .acoustic import TargetedRecheckResult, targeted_recheck
from .engine import approved_evidence, observed_evidence, verify
from .providers import _load_project_env
from .schemas import (Decision, Finding, FindingStatus, Model, ReviewResult,
                      ScriptPolicy, VerificationRequest)

router = APIRouter(prefix="/review", tags=["human-review"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root() -> Path:
    _load_project_env()
    return Path(os.getenv("DUBGUARD_DATA_DIR", ".dubguard-data")).resolve()


def _store():
    return ReviewStore(_root() / "review.sqlite3")


def reviewer(authorization: str | None = Header(default=None)) -> str:
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
    matched = [name for name, secret in tokens.items() if hmac.compare_digest(secret, supplied)]
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

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
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
            db.execute("INSERT INTO workflows VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                identity, policy_record_id, audio_record_id, None, None, None, None, None,
                "DRAFT", supersedes, _now()))
        self.event(identity, "WORKFLOW_CREATED", reviewer_id, {
            "script_revision": policy["script"]["revision"],
            "policy_revision": policy["policy"]["revision"],
            "audio_sha256": artifact["sha256"], "supersedes": supersedes})
        return identity

    def set_record(self, workflow_id: str, field: str, record_id: str,
                   state: str, reviewer_id: str) -> None:
        if field not in {"transcription_record_id", "alignment_record_id",
                         "confirmed_alignment_record_id", "acoustic_record_id",
                         "verification_record_id"}:
            raise ValueError("invalid workflow record field")
        with self._connect() as db:
            row = db.execute("SELECT state FROM workflows WHERE id=?", (workflow_id,)).fetchone()
            if not row or row["state"] in {"APPROVED", "SUPERSEDED", "REJECTED"}:
                raise ValueError("workflow is unavailable or finalized")
            db.execute(f"UPDATE workflows SET {field}=?,state=? WHERE id=?", (record_id, state, workflow_id))
        self.event(workflow_id, field.upper(), reviewer_id, {"record_id": record_id})

    def mark_state(self, workflow_id: str, expected: set[str], state: str,
                   reviewer_id: str) -> None:
        with self._connect() as db:
            row = db.execute("SELECT state FROM workflows WHERE id=?", (workflow_id,)).fetchone()
            if not row or row["state"] not in expected:
                raise ValueError("workflow is not in a state eligible for this operation")
            db.execute("UPDATE workflows SET state=? WHERE id=?", (state, workflow_id))
        self.event(workflow_id, "STATE_CHANGED", reviewer_id, {"state": state})

    def decide_finding(self, workflow_id: str, index: int, decision: str,
                       reason: str, reviewer_id: str) -> str:
        workflow = self.workflow(workflow_id)
        if workflow["state"] in {"APPROVED", "SUPERSEDED", "REJECTED"}:
            raise ValueError("workflow is finalized")
        if not workflow["verification_record_id"]:
            raise ValueError("verification is required first")
        result = ReviewResult.model_validate(self.record(workflow["verification_record_id"], "verification"))
        if not 0 <= index < len(result.findings):
            raise ValueError("unknown finding index")
        identity = uuid4().hex
        with self._connect() as db:
            db.execute("INSERT INTO finding_decisions VALUES (?,?,?,?,?,?,?,?)", (
                identity, workflow_id, index, workflow["verification_record_id"],
                decision, reason, reviewer_id, _now()))
            rows = db.execute("SELECT finding_index, decision FROM finding_decisions WHERE workflow_id=? AND verification_record_id=? ORDER BY created_at,id",
                              (workflow_id, workflow["verification_record_id"])).fetchall()
            latest = {row["finding_index"]: row["decision"] for row in rows}
            ready = all(latest.get(position) == "ACCEPTED_AS_CORRECT" for position in range(len(result.findings)))
            db.execute("UPDATE workflows SET state=? WHERE id=?", (
                "READY_FOR_SIGNOFF" if ready else "IN_REVIEW", workflow_id))
        self.event(workflow_id, "FINDING_DECIDED", reviewer_id, {
            "finding_index": index, "decision": decision, "reason": reason})
        return identity

    def signoff(self, workflow_id: str, decision: str, reason: str, reviewer_id: str) -> str:
        workflow = self.workflow(workflow_id)
        if workflow["state"] in {"APPROVED", "SUPERSEDED", "REJECTED"}:
            raise ValueError("workflow is finalized")
        if not workflow["verification_record_id"]:
            raise ValueError("verification is required first")
        result = ReviewResult.model_validate(self.record(workflow["verification_record_id"], "verification"))
        if decision == "APPROVED":
            if workflow["state"] != "READY_FOR_SIGNOFF":
                raise ValueError("required findings are not ready for signoff")
            with self._connect() as db:
                rows = db.execute("SELECT finding_index, decision FROM finding_decisions WHERE workflow_id=? AND verification_record_id=? ORDER BY created_at,id",
                                  (workflow_id, workflow["verification_record_id"])).fetchall()
            latest = {row["finding_index"]: row["decision"] for row in rows}
            if any(latest.get(index) != "ACCEPTED_AS_CORRECT" for index in range(len(result.findings))):
                raise ValueError("all findings require an explicit accepting human decision before approval")
            if not workflow["transcription_record_id"]:
                raise ValueError("audio transcription record is required before approval")
            transcription = TranscriptionResult.model_validate(self.record(
                workflow["transcription_record_id"], "transcription"))
            if not transcription.coverage.complete_processing:
                raise ValueError("audio processing coverage is incomplete")
        policy = ScriptPolicy.model_validate(self.record(workflow["policy_record_id"], "approved_policy"))
        artifact = AudioArtifact.model_validate(self.record(workflow["audio_record_id"], "audio_artifact"))
        path = AudioStore(_root() / "artifacts").path_for(artifact.sha256, artifact.format)
        if not path.exists() or sha256(path.read_bytes()).hexdigest() != artifact.sha256:
            raise ValueError("original audio is missing or changed")
        identity = uuid4().hex
        with self._connect() as db:
            db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                identity, workflow_id, decision, reviewer_id, reason,
                policy.script.id, policy.script.revision, policy.policy.id,
                policy.policy.revision, artifact.sha256, "CURRENT", _now()))
            db.execute("UPDATE workflows SET state=? WHERE id=?", (decision, workflow_id))
        self.event(workflow_id, "FINAL_SIGNOFF", reviewer_id, {"decision": decision, "approval_id": identity,
                    "audio_sha256": artifact.sha256, "script_revision": policy.script.revision,
                    "policy_revision": policy.policy.revision})
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
        return {"workflow": workflow, "finding_decisions": decisions,
                "approvals": approvals, "audit_events": events}

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
    decision: str = Field(pattern="^(ACCEPTED_AS_CORRECT|CORRECTION_REQUIRED|RERECORD_REQUIRED|ESCALATED)$")
    reason: str = Field(min_length=1, max_length=2000)


class SignoffInput(Model):
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
        artifact = AudioStore(_root() / "artifacts").ingest(data)
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
    return Response(content=data, media_type="audio/wav" if artifact.format == "wav" else "audio/mpeg")


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
        store.set_record(workflow_id, "transcription_record_id", record_id, "ANALYZED", identity)
    except Exception:
        store.event(workflow_id, "TRANSCRIPTION_FAILED", identity, {"reason": "Processing failed; inspect server logs privately"})
        store.mark_state(workflow_id, {"TRANSCRIBING"}, "TRANSCRIPTION_FAILED", identity)


@router.post("/workflows/{workflow_id}/transcribe")
def start_transcription(workflow_id: str, tasks: BackgroundTasks, identity: str = Depends(reviewer)):
    workflow = _handle_key(_store().workflow, workflow_id)
    if workflow["state"] != "DRAFT":
        raise HTTPException(409, "transcription can start only from DRAFT")
    _handle_key(_store().mark_state, workflow_id, {"DRAFT"}, "TRANSCRIBING", identity)
    tasks.add_task(_transcribe_job, workflow_id, identity)
    _store().event(workflow_id, "TRANSCRIPTION_QUEUED", identity, {})
    return {"state": "QUEUED", "note": "In-process background task; use an external queue for durable deployment."}


@router.get("/workflows/{workflow_id}")
def workflow_details(workflow_id: str, identity: str = Depends(reviewer)):
    store = _store()
    details = _handle_key(store.details, workflow_id)
    workflow = details["workflow"]
    details["approved_policy"] = store.record(workflow["policy_record_id"], "approved_policy")
    details["audio_artifact"] = store.record(workflow["audio_record_id"], "audio_artifact")
    for field, kind in (("transcription_record_id", "transcription"),
                        ("alignment_record_id", "alignment"),
                        ("confirmed_alignment_record_id", "confirmed_alignment"),
                        ("acoustic_record_id", "acoustic"),
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
    store.set_record(workflow_id, "alignment_record_id", record_id, "IN_REVIEW", identity)
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
    store.set_record(workflow_id, "confirmed_alignment_record_id", record_id, "IN_REVIEW", identity)
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
        store.set_record(workflow_id, "acoustic_record_id", record_id, "IN_REVIEW", identity)
        _run_verification(workflow_id, identity, False)
    except Exception:
        store.event(workflow_id, "ACOUSTIC_RECHECK_FAILED", identity, {"reason": "Processing failed; inspect server logs privately"})
        store.mark_state(workflow_id, {"ACOUSTIC_RECHECKING"}, "ACOUSTIC_RECHECK_FAILED", identity)


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
    request = VerificationRequest(**policy.model_dump(mode="json"), transcript=transcript)
    result = verify(request, hybrid=hybrid)
    if workflow["acoustic_record_id"]:
        acoustic = TargetedRecheckResult.model_validate(store.record(workflow["acoustic_record_id"], "acoustic"))
        instructions = {i.id: i for i in policy.script.instructions}
        primary_segments = {s.id: s for s in transcription.transcript.segments}
        secondary_segments = {s.id: s for s in acoustic.secondary_transcript.segments}
        for disagreement in acoustic.assessment.disagreements:
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
            constraint = next(c for c in policy.policy.constraints if c.id == requirement_id)
            if constraint.kind == "sequence":
                continue
            result.findings.append(Finding(rule_id="ACOUSTIC.UNRESOLVED", status=FindingStatus.UNRESOLVED,
                constraint_id=requirement_id, instruction_ids=[constraint.instruction_id],
                approved=[approved_evidence(instructions[constraint.instruction_id])],
                explanation="Independent audio recheck lacks a reliable mapped hypothesis; listen to the original audio.",
                provider=acoustic.secondary_provider))
        if result.decision != Decision.CRITICAL_DEVIATION and any(
                f.rule_id.startswith("ACOUSTIC.") for f in result.findings):
            result.decision = Decision.REVIEW_REQUIRED
    record_id = store.add_record("verification", result.model_dump(mode="json"))
    store.set_record(workflow_id, "verification_record_id", record_id, "IN_REVIEW", identity)
    return record_id, result


def _verification_job(workflow_id: str, identity: str):
    try:
        _run_verification(workflow_id, identity, True)
    except Exception:
        store = _store()
        store.event(workflow_id, "VERIFICATION_FAILED", identity, {"reason": "Processing failed; inspect server logs privately"})
        store.mark_state(workflow_id, {"VERIFYING"}, "VERIFICATION_FAILED", identity)


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
                            payload.decision, payload.reason, identity)
    return {"decision_id": record_id, "status": payload.decision}


@router.post("/workflows/{workflow_id}/signoff")
def signoff(workflow_id: str, payload: SignoffInput, identity: str = Depends(reviewer)):
    approval_id = _handle_key(_store().signoff, workflow_id, payload.decision,
                              payload.reason, identity)
    return {"approval_id": approval_id, "decision": payload.decision}
