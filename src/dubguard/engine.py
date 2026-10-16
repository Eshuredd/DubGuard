"""Policy-aware checks with limited, explicit matching; no similarity clearance."""

import re

from .providers import SemanticProvider, provider_from_env
from .schemas import (Decision, EvidenceSpan, Finding, FindingStatus as Status,
                      Instruction, ReviewResult, SemanticAssessment,
                      TranscriptSegment, VerificationRequest)
from .text import (normalize, numeric_frame, numeric_signatures,
                   supported_numeric_syntax)


def approved_evidence(instruction: Instruction) -> EvidenceSpan:
    return EvidenceSpan(source="approved", instruction_id=instruction.id,
                        text=instruction.text, start_char=0, end_char=len(instruction.text))


def observed_evidence(segment: TranscriptSegment, instruction_id: str | None = None) -> EvidenceSpan:
    return EvidenceSpan(source="observed", instruction_id=instruction_id or segment.instruction_id,
                        segment_id=segment.id, text=segment.text, start_char=0, end_char=len(segment.text),
                        start_seconds=segment.start_seconds, end_seconds=segment.end_seconds,
                        timing_scope="segment" if segment.start_seconds is not None else None)


def uncertainty(segment: TranscriptSegment, request: VerificationRequest) -> str | None:
    if not segment.text.strip():
        return "The segment contains no text."
    if segment.uncertain:
        return "The supplied segment is marked uncertain."
    if re.search(r"\[(?:inaudible|unclear|unknown)\]|<unk>|\?\?\?", segment.text, re.I):
        return "The transcript contains an explicit unknown/inaudible marker."
    if request.transcript.source == "asr" and segment.confidence is None:
        return "ASR confidence is absent; reliable evidence has not been established."
    if segment.confidence is not None and segment.confidence < request.policy.min_asr_confidence:
        return "The segment confidence is below the reviewer policy threshold."
    return None


def _verify_rules(request: VerificationRequest, *, hybrid: bool = False,
           provider: SemanticProvider | None = None) -> ReviewResult:
    instructions = {i.id: i for i in request.script.instructions}
    findings: list[Finding] = []
    mapped: dict[str, list[tuple[int, TranscriptSegment]]] = {i: [] for i in instructions}
    recognized: set[str] = set()
    alignment_uncertain = False

    def add(rule: str, status: Status, explanation: str, ids=(), segments=(), constraint=None):
        findings.append(Finding(rule_id=rule, status=status, explanation=explanation,
                                constraint_id=constraint, instruction_ids=list(ids),
                                approved=[approved_evidence(instructions[i]) for i in ids],
                                observed=[observed_evidence(s, list(ids)[0] if len(ids) == 1 else None) for s in segments]))

    if request.transcript.completeness != "complete":
        add("EVIDENCE.COMPLETENESS", Status.UNRESOLVED,
            "Transcript completeness has not been confirmed; omission checks cannot clear the narration.")

    for index, segment in enumerate(request.transcript.segments):
        target = segment.instruction_id
        if target is None:
            candidates = [i.id for i in instructions.values() if normalize(segment.text) in {normalize(w) for w in i.wordings()}]
            target = candidates[0] if len(candidates) == 1 else None
        if target not in instructions:
            alignment_uncertain = True
            add("EVIDENCE.ALIGNMENT", Status.UNRESOLVED,
                "No unique exact/approved instruction match. Supply a reviewed instruction ID; similarity is not evidence of equivalence.",
                segments=[segment])
        else:
            mapped[target].append((index, segment))

    for instruction_id, matches in mapped.items():
        if not matches:
            continue
        instruction = instructions[instruction_id]
        segments = [s for _, s in matches]
        if len(matches) != 1:
            alignment_uncertain = True
            add("EVIDENCE.DUPLICATE", Status.UNRESOLVED,
                "Multiple segments map to this instruction. Review segmentation or repetitions before comparison.",
                [instruction_id], segments)
            continue
        segment = segments[0]
        reason = uncertainty(segment, request)
        if reason:
            alignment_uncertain = True
            add("EVIDENCE.UNCERTAIN", Status.UNRESOLVED, reason, [instruction_id], segments)
            continue
        wordings = instruction.wordings()
        observed = normalize(segment.text)
        exact = observed in {normalize(w) for w in wordings}
        violated = False
        constraints = [c for c in request.policy.constraints if getattr(c, "instruction_id", None) == instruction_id]
        safe_numeric_transform = (
            any(c.kind == "numeric" for c in constraints)
            and supported_numeric_syntax(segment.text)
            and any(numeric_frame(w) == numeric_frame(segment.text) for w in wordings)
            and numeric_signatures(instruction.text) == numeric_signatures(segment.text)
        )
        for c in constraints:
            if c.kind == "numeric":
                same_frame = any(numeric_frame(w) == numeric_frame(segment.text) for w in wordings)
                if exact:
                    add("NUMERIC.MATCH", Status.SATISFIED, "Protected quantities match an approved wording.", [instruction_id], segments, c.id)
                elif same_frame and supported_numeric_syntax(segment.text):
                    if numeric_signatures(instruction.text) == numeric_signatures(segment.text):
                        safe_numeric_transform = True
                        add("NUMERIC.EQUIVALENT", Status.SATISFIED,
                            "All protected values, units, bounds, and ranges are exactly equal after unit conversion; surrounding text matches an approved template.",
                            [instruction_id], segments, c.id)
                    else:
                        violated = True
                        add("NUMERIC.CHANGED", Status.VIOLATION,
                            "A protected quantity, unit dimension, range, or bound changed within the same instruction template.",
                            [instruction_id], segments, c.id)
                else:
                    add("NUMERIC.UNRESOLVED", Status.UNRESOLVED,
                        "Numeric evidence is missing or its wording is outside the supported template grammar.",
                        [instruction_id], segments, c.id)
            elif c.kind == "polarity":
                raw_reversals = [re.sub(r"(?<!\w)" + re.escape(c.approved_phrase) + r"(?!\w)",
                                        lambda _: c.reversed_phrase, w, flags=re.I) for w in wordings]
                # Only replacements that actually changed the approved text count.
                raw_reversals = [r for r, w in zip(raw_reversals, wordings) if normalize(r) != normalize(w)]
                reversal = observed in {normalize(r) for r in raw_reversals}
                if not reversal and any(k.kind == "numeric" for k in constraints):
                    reversal = any(numeric_frame(r) == numeric_frame(segment.text) for r in raw_reversals)
                if reversal:
                    violated = True
                    add("POLARITY.REVERSED", Status.VIOLATION,
                        "The reviewer-protected polarity phrase was replaced by its declared reversal in the same instruction template.",
                        [instruction_id], segments, c.id)
                elif exact:
                    add("POLARITY.MATCH", Status.SATISFIED, "The wording is explicitly approved for this polarity constraint.", [instruction_id], segments, c.id)
            elif c.kind == "warning":
                if observed in {normalize(w) for w in c.forbidden_wordings}:
                    violated = True
                    add("WARNING.CHANGED", Status.VIOLATION,
                        "The warning matches a reviewer-declared dangerous alternative.", [instruction_id], segments, c.id)
                elif exact:
                    add("WARNING.MATCH", Status.SATISFIED, "The protected warning matches approved wording.", [instruction_id], segments, c.id)
                elif not safe_numeric_transform and not violated:
                    add("WARNING.UNRESOLVED", Status.UNRESOLVED,
                        "The protected warning changed, but the available rules cannot determine its meaning safely.", [instruction_id], segments, c.id)
        if exact or safe_numeric_transform:
            recognized.add(instruction_id)
            add("WORDING.APPROVED" if exact else "WORDING.NUMERIC_TRANSFORM", Status.SATISFIED,
                "Exact/explicitly approved wording matched." if exact else "Only a verified numeric representation changed.", [instruction_id], segments)
        elif not violated:
            alignment_uncertain = True
            add("WORDING.UNRESOLVED", Status.UNRESOLVED,
                "This wording is not explicitly approved. Lexical similarity cannot establish semantic equivalence.", [instruction_id], segments)

    reliable_coverage = request.transcript.completeness == "complete" and not alignment_uncertain
    for instruction_id, matches in mapped.items():
        if matches:
            continue
        warnings = [c for c in request.policy.constraints if c.kind == "warning" and c.instruction_id == instruction_id]
        sequences = [c for c in request.policy.constraints if c.kind == "sequence" and instruction_id in c.instruction_ids]
        protected = warnings + sequences
        if protected and reliable_coverage:
            for c in protected:
                add("WARNING.MISSING" if c.kind == "warning" else "SEQUENCE.MISSING", Status.VIOLATION,
                    "An explicitly protected warning/step is absent from the transcript declared complete. No observed span or timestamp exists for an omission.",
                    [instruction_id], constraint=c.id)
        else:
            add("EVIDENCE.MISSING", Status.UNRESOLVED,
                "Instruction evidence is absent; a protected omission cannot be established from uncertain coverage." if protected else "Instruction evidence is absent and no explicit omission-critical constraint applies.",
                [instruction_id])

    for c in request.policy.constraints:
        if c.kind != "sequence":
            continue
        present = [i for i in c.instruction_ids if i in recognized]
        positions = [mapped[i][0][0] for i in present]
        segments = [mapped[i][0][1] for i in present]
        if positions != sorted(positions):
            add("SEQUENCE.REVERSED", Status.VIOLATION,
                "Recognized protected steps occur in the reverse of the explicitly required relative order. Array order is narration order.", c.instruction_ids, segments, c.id)
        elif len(present) == len(c.instruction_ids):
            add("SEQUENCE.MATCH", Status.SATISFIED, "All protected steps occur in their required relative order.", c.instruction_ids, segments, c.id)
        else:
            add("SEQUENCE.UNRESOLVED", Status.UNRESOLVED,
                "Not all protected steps have recognized evidence; their complete order cannot be established.", c.instruction_ids, segments, c.id)

    semantic = None
    if hybrid:
        try:
            semantic = SemanticAssessment.model_validate((provider or provider_from_env()).verify(request))
        except Exception:
            # Never expose exceptions that could contain keys, URLs, or prompts.
            semantic = SemanticAssessment(provider="unavailable", status="unavailable",
                                          explanation="Semantic provider failed; deterministic evidence is retained.")
        if semantic.status != "real":
            add("SEMANTIC.UNAVAILABLE", Status.UNRESOLVED,
                "Requested real semantic verification did not run. Mock or unavailable inference cannot clear this request.")
        else:
            constraints_by_id = {c.id: c for c in request.policy.constraints}
            for issue in semantic.issues:
                constraint = constraints_by_id.get(issue.requirement_id)
                related = (constraint.instruction_ids if constraint.kind == "sequence" else
                           [constraint.instruction_id]) if constraint else []
                findings.append(Finding(rule_id="SEMANTIC.INVALID_EVIDENCE", status=Status.UNRESOLVED,
                                        constraint_id=issue.requirement_id, instruction_ids=related,
                                        approved=[approved_evidence(instructions[i]) for i in related],
                                        explanation=issue.explanation + " Human review is required.",
                                        provider=semantic.provider, model_call_id=semantic.call_id))
            for advice in semantic.findings:
                rule = ("SEMANTIC.SUSPECTED_DEVIATION" if advice.verdict == "DEVIATION" else
                        "SEMANTIC.UNCERTAIN" if advice.verdict == "UNRESOLVED" else "SEMANTIC.EQUIVALENT_ADVICE")
                findings.append(Finding(rule_id=rule,
                                        status=Status.SATISFIED if advice.verdict == "EQUIVALENT" else Status.UNRESOLVED,
                                        constraint_id=advice.requirement_id,
                                        instruction_ids=[advice.instruction_id],
                                        approved=advice.approved, observed=advice.observed,
                                        explanation="AMD advisory: " + advice.explanation,
                                        provider=semantic.provider, model_call_id=semantic.call_id))
            if semantic.verdict != "EQUIVALENT" and not semantic.issues and not any(
                    f.verdict != "EQUIVALENT" for f in semantic.findings):
                add("SEMANTIC.REVIEW", Status.UNRESOLVED,
                    "The semantic provider reported deviation or uncertainty without a validated finding; human review is required.")
        # Even a real EQUIVALENT opinion cannot remove deterministic uncertainty.

    statuses = {f.status for f in findings}
    decision = Decision.CRITICAL_DEVIATION if Status.VIOLATION in statuses else Decision.REVIEW_REQUIRED if Status.UNRESOLVED in statuses else Decision.PASS_CANDIDATE
    return ReviewResult(decision=decision, findings=findings, script_id=request.script.id,
                        script_revision=request.script.revision, policy_id=request.policy.id,
                        policy_revision=request.policy.revision, mode="hybrid" if hybrid else "deterministic", semantic=semantic)


def verify(request: VerificationRequest, *, hybrid: bool = False,
           provider: SemanticProvider | None = None) -> ReviewResult:
    """Raw ASR can alert, but only reviewed text can establish a violation."""
    if request.transcript.source != "asr":
        return _verify_rules(request, hybrid=hybrid, provider=provider)
    from .alignment import propose_alignment
    # These copies are solely inputs to candidate discovery. Neither is persisted
    # as human evidence. Even high-confidence ASR remains provisional.
    guarded = request.model_copy(deep=True)
    for segment in guarded.transcript.segments:
        segment.uncertain = True
        segment.uncertainty_reason = "Raw ASR requires human verification of spoken content."
    guarded.transcript.completeness = "unknown"
    result = _verify_rules(guarded, hybrid=hybrid, provider=provider)
    candidate = request.model_copy(deep=True)
    candidate.transcript.source = "manual"
    candidate.transcript.completeness = "unknown"  # never infer omissions from ASR
    proposals = propose_alignment(request.script, request.transcript)
    tentative = {p.segment_ids[0]: p.instruction_ids[0] for p in proposals.proposals
                 if len(p.segment_ids) == len(p.instruction_ids) == 1}
    for segment in candidate.transcript.segments:
        segment.instruction_id = segment.instruction_id or tentative.get(segment.id)
        segment.uncertain = False
        segment.uncertainty_reason = None
        segment.confidence = None
    for finding in _verify_rules(candidate).findings:
        if finding.status == Status.VIOLATION:
            result.findings.append(finding.model_copy(update={
                "rule_id": "ASR.SUSPECTED." + finding.rule_id,
                "status": Status.UNRESOLVED,
                "provider": "provisional-rule-check",
                "explanation": "Suspected only: unverified ASR text and potentially tentative alignment. "
                               + finding.explanation + " Listen to the original audio and verify actual spoken text."}))
    result.decision = Decision.REVIEW_REQUIRED
    return result
