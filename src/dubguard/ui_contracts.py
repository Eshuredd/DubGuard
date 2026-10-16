"""Public application response contracts used to generate TypeScript types."""
from typing import Any
from pydantic import Field
from .schemas import Model, ScriptPolicy, ReviewResult, VerifiedTranscriptEvidence
from .audio import AudioArtifact, TranscriptionResult
from .alignment import AlignmentRun
from .acoustic import TargetedRecheckResult

class WorkflowState(Model):
    id: str
    policy_record_id: str
    audio_record_id: str
    transcription_record_id: str | None = None
    alignment_record_id: str | None = None
    confirmed_alignment_record_id: str | None = None
    acoustic_record_id: str | None = None
    evidence_record_id: str | None = None
    acoustic_resolution_record_id: str | None = None
    verification_record_id: str | None = None
    state: str
    supersedes: str | None = None
    created_at: str
    revision: int

class WorkflowView(Model):
    workflow: WorkflowState
    approved_policy: ScriptPolicy
    audio_artifact: AudioArtifact
    transcription: TranscriptionResult | None = None
    alignment: AlignmentRun | None = None
    confirmed_alignment: dict[str, Any] | None = None
    verified_evidence: VerifiedTranscriptEvidence | None = None
    acoustic: TargetedRecheckResult | None = None
    acoustic_resolution: dict[str, Any] | None = None
    verification: ReviewResult | None = None
    finding_decisions: list[dict[str, Any]] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    audit_events: list[dict[str, Any]] = Field(default_factory=list)
    record_history: list[dict[str, Any]] = Field(default_factory=list)

class WorkflowSummary(Model):
    workflow: WorkflowState
    policy: ScriptPolicy
    audio: AudioArtifact

class PolicyRecord(Model):
    id: str
    kind: str
    payload: ScriptPolicy
    created_at: str

class DemoScenario(Model):
    id: str
    title: str
    description: str
    fixture: bool = True
    policy: ScriptPolicy

class QuickReport(Model):
    id: str
    state: str
    expires_at: float
    runs: int
    scenario_id: str | None = None
    artifact: AudioArtifact | None = None
    transcription: TranscriptionResult | None = None
    alignment: AlignmentRun | None = None
    verification: ReviewResult | None = None
    error: str | None = None
    notice: str = "Demonstration fixture only. Never a human release approval. Local ASR is provisional."
