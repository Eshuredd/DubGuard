"""Temporary, isolated custom review. Never writes ReviewStore or approvals.

Uses Quick Test capabilities, accounting, expiry, audio storage and worker slots.
References are visitor declarations; evidence/decisions have no authenticated identity.
"""
from contextlib import contextmanager
from hashlib import sha256
import json
import os
import time
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile
from pydantic import Field, model_validator

from . import quick
from .engine import verify
from .schemas import Model, Constraint, ScriptPolicy, Transcript, ReviewResult, VerificationRequest, HumanTranscriptInput
from .ui_contracts import QuickReport
from .audio import AudioStore

router = APIRouter(prefix="/workspace", tags=["temporary custom review"])
NOTICE = "Temporary demo only. Visitor reference and evidence are not organizational approval, authenticated reviewer identity or release authorization. Data expires after 30 minutes."


def enabled():
    return os.getenv("DUBGUARD_PUBLIC_WORKSPACE", "false").lower() == "true"


def require_enabled():
    if not enabled():
        raise HTTPException(503, "Public custom reviews are currently disabled; no sign-in is required when enabled by the operator")


def session(authorization: str | None = Header(default=None)):
    return quick.resolve_session(authorization, "custom")


class ReferenceStep(Model):
    text: str = Field(min_length=1, max_length=2000)
    alternatives: list[str] = Field(default_factory=list, max_length=5)


class ReferenceInput(Model):
    expected_revision: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=100)
    instructions: list[ReferenceStep] = Field(min_length=1, max_length=12)
    requirements: list[Constraint] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def bounded_text(self):
        texts = [s.text for s in self.instructions] + [v for s in self.instructions for v in s.alternatives]
        if any(not t.strip() or len(t) > 2000 for t in texts) or sum(map(len, texts)) > 12000:
            raise ValueError("Reference text must be nonempty and at most 12,000 characters in total")
        return self

    def policy(self, version):
        return ScriptPolicy.model_validate({"script": {"id": "visitor-reference", "revision": str(version),
            "instructions": [{"id": f"step-{i+1}", "text": step.text,
                "approved_variants": [{"text": text, "approved_by": "visitor-demo-only", "reason": "Visitor-declared alternative; no organizational approval"} for text in step.alternatives]} for i, step in enumerate(self.instructions)]},
            "policy": {"id": "visitor-demo-policy", "revision": str(version), "approved_by": "visitor-demo-only; not an authenticated approval", "constraints": [r.model_dump() for r in self.requirements]}})


class DemoEvidence(Model):
    transcript: Transcript
    audio_sha256: str
    raw_run: int
    reason: str
    provenance: Literal["anonymous visitor attestation; not authenticated reviewer evidence"] = "anonymous visitor attestation; not authenticated reviewer evidence"
    result: ReviewResult


class WorkspaceState(Model):
    revision: int = 0
    reference_version: int = 0
    title: str = ""
    reference: ScriptPolicy | None = None
    evidence: DemoEvidence | None = None
    reviewed: list[int] = Field(default_factory=list)
    notes: str = ""
    demo_decision: Literal["NEEDS_REVIEW", "REVIEWED", "REQUEST_NEW_RECORDING"] | None = None
    changes: int = 0
    events: list[str] = Field(default_factory=list)


class WorkspaceView(Model):
    workspace: WorkspaceState
    analysis: QuickReport
    notice: str = NOTICE


class DemoReviewInput(Model):
    expected_revision: int = Field(ge=0)
    notes: str = Field(max_length=2000)
    reviewed: list[int] = Field(default_factory=list, max_length=200)
    demo_decision: Literal["NEEDS_REVIEW", "REVIEWED", "REQUEST_NEW_RECORDING"]


def read_state(row):
    return WorkspaceState.model_validate_json(row["custom"] or "{}")


@contextmanager
def edit(identity, expected):
    require_enabled()
    with quick.database() as db:
        row = db.execute("SELECT * FROM sessions WHERE id=? AND scope='custom' AND expires>?", (identity, time.time())).fetchone()
        if not row:
            raise HTTPException(401, "Workspace expired")
        document = read_state(row)
        if document.revision != expected or row["state"] == "PROCESSING":
            raise HTTPException(409, "Workspace changed or is processing; reload the current evidence")
        if document.changes >= 30:
            raise HTTPException(429, "Temporary workspace edit limit reached; export your evidence before expiry")
        yield document, row
        document.revision += 1
        document.changes += 1
        document.events = document.events[-20:]
        db.execute("UPDATE sessions SET custom=? WHERE id=?", (document.model_dump_json(), identity))


def active_analysis(document, row):
    analysis = QuickReport(id=row["id"], state=row["state"], expires_at=row["expires"], runs=row["runs"], amd_runs=row["amd_runs"], **json.loads(row["payload"]))
    if analysis.state != "COMPLETE" or not analysis.artifact or analysis.reference_revision != document.reference_version:
        raise HTTPException(409, "Analyze the current reference and recording before reviewing evidence")
    path = AudioStore(quick._root() / "quick" / row["id"]).path_for(analysis.artifact.sha256, analysis.artifact.format)
    try:
        original = path.read_bytes()
    except OSError:
        raise HTTPException(409, "Original recording is missing or changed") from None
    if sha256(original).hexdigest() != analysis.artifact.sha256:
        raise HTTPException(409, "Original recording is missing or changed")
    return analysis


@router.get("/config")
def config():
    return {"enabled": enabled(), "amd_available": False, "notice": NOTICE}


@router.post("/sessions")
def create():
    require_enabled()
    created = quick.new_session("custom")
    with quick.database() as db:
        db.execute("UPDATE sessions SET custom=? WHERE id=?", (WorkspaceState().model_dump_json(), created["id"]))
    return created


@router.get("/session", response_model=WorkspaceView)
@router.get("/export", response_model=WorkspaceView)
def view(identity: str = Depends(session)):
    with quick.database() as db:
        row = db.execute("SELECT * FROM sessions WHERE id=? AND expires>?", (identity, time.time())).fetchone()
    if not row:
        raise HTTPException(401, "Workspace expired")
    return WorkspaceView(workspace=read_state(row), analysis=quick.get_session(identity))


@router.put("/reference")
def save_reference(payload: ReferenceInput, identity: str = Depends(session)):
    from pydantic import ValidationError
    with edit(identity, payload.expected_revision) as (document, row):
        try:
            policy = payload.policy(document.reference_version + 1)
        except ValidationError:
            raise HTTPException(422, "Check your protected requirements: use a supported number, phrases present in the reference, and the declared instruction order")
        document.reference_version += 1
        document.title = payload.title
        document.reference = policy
        document.evidence = None
        document.reviewed = []
        document.demo_decision = None
        document.events.append("Visitor saved reference; previous review acknowledgements invalidated")
    return {"saved": True}


@router.post("/analyze")
async def analyze(tasks: BackgroundTasks, expected_revision: int, file: UploadFile = File(...),
                  mode: Literal["local"] = "local", identity: str = Depends(session)):
    require_enabled()
    current = view(identity).workspace
    if not current.reference:
        raise HTTPException(409, "Save your reference script first")
    data = await file.read(quick.MAX_BYTES + 1)
    await file.close()
    if not data or len(data) > quick.MAX_BYTES:
        raise HTTPException(413, "Audio must be nonempty and at most 10 MB")
    return quick.enqueue_analysis(tasks, identity, data, file.content_type or "", reference=current.reference,
                                  reference_revision=current.reference_version, expected_revision=expected_revision)


@router.put("/evidence")
def correct(payload: HumanTranscriptInput, identity: str = Depends(session)):
    if payload.transcript.source != "manual" or len(payload.transcript.segments) > 50 or sum(len(s.text) for s in payload.transcript.segments) > 12000:
        raise HTTPException(422, "Use at most 50 visitor-corrected segments and 12,000 characters")
    with edit(identity, payload.expected_revision) as (document, row):
        analysis = active_analysis(document, row)
        known = {s.id for s in document.reference.script.instructions}
        if any(s.instruction_id not in known and s.instruction_id is not None or s.end_seconds is not None and s.end_seconds > analysis.artifact.duration_seconds for s in payload.transcript.segments):
            raise HTTPException(422, "Evidence must refer to this reference and original recording duration")
        result = verify(VerificationRequest(**document.reference.model_dump(), transcript=payload.transcript))
        document.evidence = DemoEvidence(transcript=payload.transcript, audio_sha256=analysis.artifact.sha256,
                                         raw_run=row["runs"], reason=payload.reason, result=result)
        document.reviewed = []
        document.demo_decision = None
        document.events.append("Visitor attested spoken text; local rules rerun, raw ASR retained")
    return {"saved": True, "organizational_approval": False}


@router.put("/review")
def review(payload: DemoReviewInput, identity: str = Depends(session)):
    with edit(identity, payload.expected_revision) as (document, row):
        analysis = active_analysis(document, row)
        result = document.evidence.result if document.evidence else analysis.verification
        if any(index < 0 or index >= len(result.findings) for index in payload.reviewed):
            raise HTTPException(422, "Finding does not belong to the current verification")
        document.reviewed = sorted(set(payload.reviewed))
        document.notes = payload.notes
        document.demo_decision = payload.demo_decision
        document.events.append("Demo decision saved; no organizational approval or authenticated sign-off")
    return {"saved": True, "organizational_approval": False}


@router.get("/audio")
def audio(identity: str = Depends(session)):
    return quick.audio(identity)


@router.delete("/session")
def delete(identity: str = Depends(session)):
    return quick.delete_session(identity)
