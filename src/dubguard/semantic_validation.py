"""Turn untrusted model JSON into source-backed, advisory semantic findings."""

import json
import re
from typing import Any, Literal

from pydantic import Field, ValidationError, model_validator

from .schemas import (EvidenceSpan, Identifier, Model, SemanticFinding,
                      SemanticIssue, TranscriptSegment, VerificationRequest)
from .text import normalize


class ApprovedReference(Model):
    instruction_id: Identifier
    quote: str = Field(min_length=1, max_length=20000)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)


class ObservedReference(Model):
    instruction_id: Identifier
    segment_id: Identifier
    quote: str = Field(min_length=1, max_length=20000)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)


class DraftFinding(Model):
    requirement_id: Identifier
    kind: Literal["NUMERIC_LIMIT", "PROCEDURE_ORDER", "WARNING_POLICY", "POLARITY", "PARAPHRASE", "OTHER"]
    verdict: Literal["EQUIVALENT", "DEVIATION", "UNRESOLVED"]
    instruction_id: Identifier
    approved_evidence: list[ApprovedReference] = Field(min_length=1, max_length=20)
    observed_evidence: list[ObservedReference] = Field(default_factory=list, max_length=20)
    explanation: str = Field(min_length=1, max_length=2000)


class DraftResponse(Model):
    verdict: Literal["EQUIVALENT", "DEVIATION", "UNRESOLVED"]
    explanation: str = Field(min_length=1, max_length=2000)
    findings: list[dict[str, Any]] = Field(default_factory=list, max_length=500)


class BaselineResponse(Model):
    verdict: Literal["EQUIVALENT", "DEVIATION", "UNRESOLVED"]
    explanation: str = Field(min_length=1, max_length=2000)


KIND_FOR_CONSTRAINT = {
    "numeric": "NUMERIC_LIMIT", "polarity": "POLARITY",
    "warning": "WARNING_POLICY", "sequence": "PROCEDURE_ORDER",
}


def _matching_segment(segment: TranscriptSegment, instruction_id: str,
                      request: VerificationRequest) -> bool:
    if segment.instruction_id is not None:
        return segment.instruction_id == instruction_id
    # Only exact/explicitly approved text provides automatic alignment.
    candidates = [i.id for i in request.script.instructions
                  if normalize(segment.text) in {normalize(w) for w in i.wordings()}]
    return candidates == [instruction_id] or segment.uncertain


def _validate_finding(raw: dict[str, Any], request: VerificationRequest) -> SemanticFinding:
    draft = DraftFinding.model_validate(raw)
    constraints = {c.id: c for c in request.policy.constraints}
    instructions = {i.id: i for i in request.script.instructions}
    segments = {s.id: s for s in request.transcript.segments}
    constraint = constraints.get(draft.requirement_id)
    if constraint is None:
        raise ValueError("unknown requirement ID")
    allowed_ids = set(constraint.instruction_ids if constraint.kind == "sequence" else [constraint.instruction_id])
    if draft.instruction_id not in allowed_ids:
        raise ValueError("requirement and instruction references conflict")
    if draft.kind not in {KIND_FOR_CONSTRAINT[constraint.kind], "PARAPHRASE", "OTHER"}:
        raise ValueError("finding kind conflicts with requirement type")
    approved: list[EvidenceSpan] = []
    observed: list[EvidenceSpan] = []
    for reference in draft.approved_evidence:
        if reference.instruction_id not in allowed_ids:
            raise ValueError("approved evidence points outside requirement")
        instruction = instructions[reference.instruction_id]
        if instruction.text[reference.start_char:reference.end_char] != reference.quote:
            raise ValueError("approved quote or offsets do not match source")
        approved.append(EvidenceSpan(source="approved", instruction_id=reference.instruction_id,
                                     text=reference.quote, start_char=reference.start_char,
                                     end_char=reference.end_char))
    if draft.instruction_id not in {span.instruction_id for span in approved}:
        raise ValueError("finding lacks approved evidence for its instruction")
    for reference in draft.observed_evidence:
        if reference.instruction_id not in allowed_ids:
            raise ValueError("observed evidence points outside requirement")
        segment = segments.get(reference.segment_id)
        if segment is None:
            raise ValueError("unknown transcript segment ID")
        if not _matching_segment(segment, reference.instruction_id, request):
            raise ValueError("segment does not correspond to cited instruction")
        if segment.text[reference.start_char:reference.end_char] != reference.quote:
            raise ValueError("observed quote or offsets do not match source")
        observed.append(EvidenceSpan(source="observed", instruction_id=reference.instruction_id,
                                     segment_id=reference.segment_id, text=reference.quote,
                                     start_char=reference.start_char, end_char=reference.end_char,
                                     start_seconds=segment.start_seconds, end_seconds=segment.end_seconds,
                                     timing_scope="segment" if segment.start_seconds is not None else None))
    if draft.verdict == "EQUIVALENT" and not observed:
        raise ValueError("equivalence requires observed evidence")
    if not observed and (draft.kind not in {"WARNING_POLICY", "PROCEDURE_ORDER"}
                         or request.transcript.completeness != "complete"):
        raise ValueError("missing observed evidence is unsupported for this finding")
    if observed and draft.instruction_id not in {span.instruction_id for span in observed}:
        raise ValueError("finding lacks observed evidence for its instruction")
    verdict = draft.verdict
    if any(segments[span.segment_id].uncertain for span in observed):
        verdict = "UNRESOLVED"
    return SemanticFinding(requirement_id=draft.requirement_id, kind=draft.kind,
                           verdict=verdict, instruction_id=draft.instruction_id,
                           approved=approved, observed=observed,
                           explanation=draft.explanation)


def parse_semantic_json(content: str, request: VerificationRequest) -> tuple[str, str, list[SemanticFinding], list[SemanticIssue]]:
    """Parse one response; reject bad citations without losing independent valid ones."""
    # Some compatible endpoints wrap JSON in one Markdown code fence.
    cleaned = content.strip()
    fence = re.fullmatch(r"```(?:json)?\s*\n([\s\S]*?)\n```", cleaned, re.I)
    if fence:
        cleaned = fence.group(1)
    draft = DraftResponse.model_validate(json.loads(cleaned))
    valid: list[SemanticFinding] = []
    issues: list[SemanticIssue] = []
    known = {c.id for c in request.policy.constraints}
    for item in draft.findings:
        requirement_id = item.get("requirement_id")
        linked = requirement_id if isinstance(requirement_id, str) and requirement_id in known else None
        try:
            valid.append(_validate_finding(item, request))
        except (ValidationError, ValueError, KeyError, TypeError):
            issues.append(SemanticIssue(requirement_id=linked,
                                        explanation="A model finding had an invalid requirement, source reference, quote, or offset."))
    if draft.verdict == "DEVIATION" and not any(f.verdict == "DEVIATION" for f in valid):
        issues.append(SemanticIssue(explanation="The model reported a deviation without a validated supporting finding."))
    if draft.verdict == "EQUIVALENT" and any(f.verdict != "EQUIVALENT" for f in valid):
        issues.append(SemanticIssue(explanation="The model's overall verdict conflicts with a finding."))
    if draft.verdict == "EQUIVALENT" and issues:
        issues.append(SemanticIssue(explanation="Equivalence cannot be accepted with invalid model evidence."))
    verdict = "UNRESOLVED" if issues or any(f.verdict == "UNRESOLVED" for f in valid) else draft.verdict
    return verdict, draft.explanation, valid, issues


def parse_basic_json(content: str) -> BaselineResponse:
    cleaned = content.strip()
    fence = re.fullmatch(r"```(?:json)?\s*\n([\s\S]*?)\n```", cleaned, re.I)
    if fence:
        cleaned = fence.group(1)
    return BaselineResponse.model_validate(json.loads(cleaned))
