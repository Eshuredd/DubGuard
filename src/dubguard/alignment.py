"""Provisional script-to-ASR mapping; only reviewed IDs may enter verification."""

from difflib import SequenceMatcher
from enum import StrEnum

from pydantic import Field

from .schemas import ApprovedScript, Model, Transcript
from .text import normalize


class AlignmentStatus(StrEnum):
    PROPOSED = "PROPOSED"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED = "UNMATCHED"


class AlignmentProposal(Model):
    segment_ids: list[str] = Field(min_length=1)
    instruction_ids: list[str] = Field(default_factory=list)
    status: AlignmentStatus
    match_type: str
    explanation: str


class AlignmentRun(Model):
    proposals: list[AlignmentProposal]
    missing_instruction_ids: list[str]
    repeated_instruction_ids: list[str]
    extra_segment_ids: list[str]
    order_uncertain: bool
    note: str = "These mappings are proposals, not reviewer-confirmed instruction IDs."


def propose_alignment(script: ApprovedScript, transcript: Transcript) -> AlignmentRun:
    proposals: list[AlignmentProposal] = []
    mapped: dict[str, list[int]] = {item.id: [] for item in script.instructions}
    for index, segment in enumerate(transcript.segments):
        observed = normalize(segment.text)
        exact = [item.id for item in script.instructions if observed == normalize(item.text)]
        variant = [item.id for item in script.instructions if any(
            observed == normalize(v.text) for v in item.approved_variants)]
        candidates = list(dict.fromkeys(exact + variant))
        match_type = "EXACT" if exact else "APPROVED_VARIANT" if variant else "CHANGED_OR_EXTRA"
        if not candidates and observed:
            # Similarity only proposes a mapping. It never establishes meaning.
            scores = [(item.id, max(SequenceMatcher(None, observed, normalize(w)).ratio()
                                     for w in item.wordings())) for item in script.instructions]
            high = [item_id for item_id, score in scores if score >= 0.68]
            candidates = high[:5]
            if candidates:
                match_type = "POSSIBLE_CHANGED_WORDING"
        status = (AlignmentStatus.UNMATCHED if not candidates else
                  AlignmentStatus.PROPOSED if len(candidates) == 1 and match_type in {
                      "EXACT", "APPROVED_VARIANT"} else AlignmentStatus.AMBIGUOUS)
        if status == AlignmentStatus.PROPOSED:
            mapped[candidates[0]].append(index)
        proposals.append(AlignmentProposal(segment_ids=[segment.id], instruction_ids=candidates,
                                           status=status, match_type=match_type,
                                           explanation="Textual mapping only; reviewer confirmation is required."))
    for first in range(len(transcript.segments) - 1):
        left, right = transcript.segments[first], transcript.segments[first + 1]
        joined = normalize(left.text + " " + right.text)
        split_matches = [item.id for item in script.instructions if joined in {
            normalize(wording) for wording in item.wordings()}]
        if split_matches:
            proposals.append(AlignmentProposal(segment_ids=[left.id, right.id],
                instruction_ids=split_matches, status=AlignmentStatus.AMBIGUOUS,
                match_type="POSSIBLE_SPLIT_INSTRUCTION",
                explanation="Two segments may form one instruction; reviewer confirmation and segmentation are required."))
    for segment in transcript.segments:
        merged = normalize(segment.text)
        for left, right in zip(script.instructions, script.instructions[1:]):
            if merged == normalize(left.text + " " + right.text):
                proposals.append(AlignmentProposal(segment_ids=[segment.id],
                    instruction_ids=[left.id, right.id], status=AlignmentStatus.AMBIGUOUS,
                    match_type="POSSIBLE_MERGED_INSTRUCTIONS",
                    explanation="One segment may contain two instructions; reviewer confirmation and segmentation are required."))
    missing = [item_id for item_id, positions in mapped.items() if not positions]
    repeated = [item_id for item_id, positions in mapped.items() if len(positions) > 1]
    positions = [mapped[item.id][0] for item in script.instructions if len(mapped[item.id]) == 1]
    reordered = positions != sorted(positions)
    grouped_ids = {segment_id for p in proposals if p.match_type.startswith("POSSIBLE_SPLIT") or
                   p.match_type.startswith("POSSIBLE_MERGED") for segment_id in p.segment_ids}
    return AlignmentRun(proposals=proposals, missing_instruction_ids=missing,
                        repeated_instruction_ids=repeated,
                        extra_segment_ids=[p.segment_ids[0] for p in proposals if p.status == AlignmentStatus.UNMATCHED
                                           and p.segment_ids[0] not in grouped_ids],
                        order_uncertain=reordered or bool(missing or repeated or any(
                            p.status != AlignmentStatus.PROPOSED for p in proposals)))


def apply_confirmed_alignment(transcript: Transcript, confirmations: dict[str, str],
                              script: ApprovedScript) -> Transcript:
    """Materialize only explicit reviewer confirmations for the existing engine."""
    known_segments = {s.id for s in transcript.segments}
    known_instructions = {i.id for i in script.instructions}
    if not set(confirmations) <= known_segments or not set(confirmations.values()) <= known_instructions:
        raise ValueError("confirmed alignment references an unknown ID")
    return transcript.model_copy(update={"segments": [s.model_copy(update={
        "instruction_id": confirmations.get(s.id)}) for s in transcript.segments]})
