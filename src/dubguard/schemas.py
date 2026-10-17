"""Public, strict contracts. Reviewer identities are recorded, not authenticated."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .text import contains_phrase, normalize, numeric_signatures, quantities, supported_numeric_syntax

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ApprovedVariant(Model):
    text: Text
    approved_by: Text
    reason: Text


class Instruction(Model):
    id: Identifier
    text: Text
    approved_variants: list[ApprovedVariant] = Field(default_factory=list, max_length=50)

    def wordings(self) -> list[str]:
        return [self.text] + [v.text for v in self.approved_variants]


class ApprovedScript(Model):
    id: Identifier
    revision: Identifier
    language: Literal["en"] = "en"
    speaker_count: Literal[1] = 1
    instructions: list[Instruction] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({i.id for i in self.instructions}) != len(self.instructions):
            raise ValueError("instruction IDs must be unique")
        return self


class NumericConstraint(Model):
    id: Identifier
    kind: Literal["numeric"]
    instruction_id: Identifier


class PolarityConstraint(Model):
    id: Identifier
    kind: Literal["polarity"]
    instruction_id: Identifier
    approved_phrase: Text
    reversed_phrase: Text


class WarningConstraint(Model):
    id: Identifier
    kind: Literal["warning"]
    instruction_id: Identifier
    # Reviewer-declared dangerous alternatives; unknown rewrites stay unresolved.
    forbidden_wordings: list[Text] = Field(default_factory=list, max_length=50)


class SequenceConstraint(Model):
    id: Identifier
    kind: Literal["sequence"]
    instruction_ids: list[Identifier] = Field(min_length=2, max_length=200)


Constraint = Annotated[NumericConstraint | PolarityConstraint | WarningConstraint | SequenceConstraint, Field(discriminator="kind")]


class ReviewPolicy(Model):
    id: Identifier
    revision: Identifier
    approved_by: Text
    min_asr_confidence: float = Field(default=0.9, ge=0, le=1)
    constraints: list[Constraint] = Field(default_factory=list, max_length=500)


class ScriptPolicy(Model):
    script: ApprovedScript
    policy: ReviewPolicy

    @model_validator(mode="after")
    def coherent_policy(self):
        instructions = {i.id: i for i in self.script.instructions}
        ids = [c.id for c in self.policy.constraints]
        if len(set(ids)) != len(ids):
            raise ValueError("constraint IDs must be unique")
        for c in self.policy.constraints:
            references = c.instruction_ids if c.kind == "sequence" else [c.instruction_id]
            if not set(references) <= instructions.keys():
                raise ValueError(f"unknown instruction reference in {c.id}")
            if c.kind == "sequence":
                positions = [list(instructions).index(i) for i in references]
                if positions != sorted(set(positions)):
                    raise ValueError("protected sequence must follow approved script order with unique steps")
                continue
            instruction = instructions[c.instruction_id]
            if c.kind == "numeric":
                expected = numeric_signatures(instruction.text)
                if not expected:
                    raise ValueError("numeric constraint requires an explicit supported numeric expression")
                for wording in instruction.wordings():
                    if not supported_numeric_syntax(wording) or numeric_signatures(wording) != expected:
                        raise ValueError("numeric wording is unsupported or changes protected quantities")
                    if any(q.upper is not None and q.lower > q.upper for q in quantities(wording)):
                        raise ValueError("numeric range lower bound exceeds upper bound")
            elif c.kind == "polarity":
                if normalize(c.approved_phrase) == normalize(c.reversed_phrase):
                    raise ValueError("polarity phrases must differ")
                if not contains_phrase(instruction.text, c.approved_phrase):
                    raise ValueError("approved polarity phrase must occur in the instruction")
                # 'do' inside 'do not' is legitimate; remove the approved phrase first.
                from .text import phrase_replace
                for wording in instruction.wordings():
                    remaining = phrase_replace(normalize(wording), normalize(c.approved_phrase), "")
                    if contains_phrase(remaining, c.reversed_phrase):
                        raise ValueError("approved wording contains the reversed polarity phrase")
            elif c.kind == "warning":
                if {normalize(w) for w in c.forbidden_wordings} & {normalize(w) for w in instruction.wordings()}:
                    raise ValueError("warning wording cannot be both approved and forbidden")
        return self


class TranscriptSegment(Model):
    id: Identifier
    text: str = Field(max_length=20000)
    instruction_id: Identifier | None = None
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    uncertain: bool = False
    uncertainty_reason: Text | None = None

    @model_validator(mode="after")
    def coherent_timing(self):
        if (self.start_seconds is None) != (self.end_seconds is None):
            raise ValueError("provide both segment timestamps or neither")
        if self.start_seconds is not None and self.end_seconds < self.start_seconds:
            raise ValueError("segment end precedes start")
        if self.uncertainty_reason and not self.uncertain:
            raise ValueError("uncertainty reason requires uncertain=true")
        return self


class Transcript(Model):
    source: Literal["manual", "asr"] = "manual"
    completeness: Literal["complete", "incomplete", "unknown"] = "unknown"
    segments: list[TranscriptSegment] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def unique_and_ordered(self):
        if len({s.id for s in self.segments}) != len(self.segments):
            raise ValueError("segment IDs must be unique")
        timed = [s for s in self.segments if s.start_seconds is not None]
        if any(b.start_seconds < a.end_seconds for a, b in zip(timed, timed[1:])):
            raise ValueError("single-speaker timestamps must follow array order without overlap")
        return self


class VerificationRequest(ScriptPolicy):
    transcript: Transcript


class FindingStatus(StrEnum):
    SATISFIED = "SATISFIED"
    VIOLATION = "VIOLATION"
    UNRESOLVED = "UNRESOLVED"


class Decision(StrEnum):
    PASS_CANDIDATE = "PASS_CANDIDATE"
    CRITICAL_DEVIATION = "CRITICAL_DEVIATION"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class EvidenceSpan(Model):
    source: Literal["approved", "observed"]
    instruction_id: str | None = None
    segment_id: str | None = None
    text: str
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)
    start_seconds: float | None = None
    end_seconds: float | None = None
    timing_scope: Literal["segment"] | None = None

    @model_validator(mode="after")
    def valid_span(self):
        if self.end_char - self.start_char != len(self.text):
            raise ValueError("evidence span length does not match text")
        return self


class Finding(Model):
    rule_id: str
    status: FindingStatus
    constraint_id: str | None = None
    instruction_ids: list[str] = Field(default_factory=list)
    approved: list[EvidenceSpan] = Field(default_factory=list)
    observed: list[EvidenceSpan] = Field(default_factory=list)
    explanation: str
    provider: str | None = None
    model_call_id: str | None = None


class SemanticFinding(Model):
    """Validated model advice. Its evidence is copied from the request, never trusted text."""

    requirement_id: Identifier
    kind: Literal["NUMERIC_LIMIT", "PROCEDURE_ORDER", "WARNING_POLICY", "POLARITY", "PARAPHRASE", "OTHER"]
    verdict: Literal["EQUIVALENT", "DEVIATION", "UNRESOLVED"]
    instruction_id: Identifier
    approved: list[EvidenceSpan] = Field(min_length=1, max_length=20)
    observed: list[EvidenceSpan] = Field(default_factory=list, max_length=20)
    explanation: Text


class SemanticIssue(Model):
    requirement_id: Identifier | None = None
    explanation: str = Field(min_length=1, max_length=300)


class SemanticAssessment(Model):
    provider: str
    status: Literal["unavailable", "mock", "real"]
    verdict: Literal["EQUIVALENT", "DEVIATION", "UNRESOLVED"] = "UNRESOLVED"
    explanation: str
    real_inference: bool = False
    call_id: str | None = None
    model: str | None = None
    findings: list[SemanticFinding] = Field(default_factory=list, max_length=500)
    issues: list[SemanticIssue] = Field(default_factory=list, max_length=500)
    response_valid: bool = False
    latency_ms: float | None = Field(default=None, ge=0)
    attempts: int | None = Field(default=None, ge=0)
    usage: dict[str, int] | None = None
    error_class: str | None = None

    @model_validator(mode="after")
    def provenance(self):
        if self.status == "real":
            if not self.real_inference or not self.call_id or not self.model or not self.response_valid:
                raise ValueError("real inference requires validated response, call ID, and model provenance")
        elif self.real_inference:
            raise ValueError("mock/unavailable assessments cannot claim real inference")
        return self


class ReviewResult(Model):
    decision: Decision
    findings: list[Finding]
    script_id: str
    script_revision: str
    policy_id: str
    policy_revision: str
    engine_version: str = "0.5.0"
    mode: Literal["deterministic", "hybrid"] = "deterministic"
    semantic: SemanticAssessment | None = None
    safety_notice: str = "Review aid only. PASS_CANDIDATE is not safety certification or release approval."


class EvaluationLabel(StrEnum):
    ACCEPTABLE = "ACCEPTABLE"
    CRITICAL = "CRITICAL"
    UNRESOLVED = "UNRESOLVED"


class EvaluationCase(Model):
    id: Identifier
    category: Identifier
    label: EvaluationLabel
    rationale: Text
    profile: Identifier
    transcript: Transcript


class HumanTranscriptInput(Model):
    expected_revision: int = Field(ge=0)
    transcript: Transcript
    listened_to_original: Literal[True]
    reason: Text


class VerifiedTranscriptEvidence(Model):
    transcript: Transcript
    audio_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_transcription_record_id: str
    previous_evidence_record_id: str | None = None
    reviewer_id: Text
    reason: Text
    listened_to_original: Literal[True]
    created_at: str

    @model_validator(mode="after")
    def human_source(self):
        if self.transcript.source != "manual":
            raise ValueError("human evidence must use manual source")
        return self
