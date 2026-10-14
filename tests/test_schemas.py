import pytest
from pydantic import ValidationError

from dubguard.schemas import EvidenceSpan, ScriptPolicy, SemanticAssessment, Transcript, TranscriptSegment, VerificationRequest


@pytest.mark.parametrize("segment", [
    {"id":"s","text":"x","start_seconds":1},
    {"id":"s","text":"x","start_seconds":2,"end_seconds":1},
    {"id":"s","text":"x","confidence":1.1},
    {"id":"s","text":"x","confidence":float("nan")},
    {"id":"s","text":"x","start_seconds":0,"end_seconds":float("inf")},
    {"id":"s","text":"x","uncertainty_reason":"unclear"},
    {"id":"s","text":"x","extra":"unexpected"},
])
def test_bad_segments_rejected(segment):
    with pytest.raises(ValidationError):
        TranscriptSegment.model_validate(segment)


def test_overlapping_and_reversed_timestamps_rejected():
    with pytest.raises(ValidationError):
        Transcript(segments=[TranscriptSegment(id="a", text="a", start_seconds=2, end_seconds=4),
                             TranscriptSegment(id="b", text="b", start_seconds=3, end_seconds=5)])


def test_duplicate_segment_ids_rejected():
    with pytest.raises(ValidationError):
        Transcript(segments=[TranscriptSegment(id="a", text="a"), TranscriptSegment(id="a", text="b")])


@pytest.mark.parametrize("change", ["unknown-reference", "duplicate-constraint", "duplicate-instruction", "unsupported-language", "multiple-speakers"])
def test_invalid_script_policy(case_request, change):
    data = case_request("A01").model_dump()
    if change == "unknown-reference":
        data["policy"]["constraints"][0]["instruction_id"] = "unknown"
    elif change == "duplicate-constraint":
        data["policy"]["constraints"] *= 2
    elif change == "duplicate-instruction":
        data["script"]["instructions"] *= 2
    elif change == "unsupported-language":
        data["script"]["language"] = "fr"
    else:
        data["script"]["speaker_count"] = 2
    with pytest.raises(ValidationError):
        VerificationRequest.model_validate(data)


@pytest.mark.parametrize("case_id,variant", [("A01","Turn the power on."), ("A06","Allow at least 2 minutes.")])
def test_contradictory_approved_variant_rejected(case_request, case_id, variant):
    data = case_request(case_id).model_dump()
    data["script"]["instructions"][0]["approved_variants"][0]["text"] = variant
    with pytest.raises(ValidationError):
        VerificationRequest.model_validate(data)


def test_warning_cannot_be_both_approved_and_forbidden(case_request):
    data = case_request("A19").model_dump()
    data["policy"]["constraints"][0]["forbidden_wordings"] = [data["script"]["instructions"][0]["text"]]
    with pytest.raises(ValidationError):
        VerificationRequest.model_validate(data)


@pytest.mark.parametrize("ids", [["guard","close","disconnect"], ["disconnect","disconnect"], ["disconnect","missing"]])
def test_bad_protected_sequence_rejected(case_request, ids):
    data = case_request("A14").model_dump()
    data["policy"]["constraints"][0]["instruction_ids"] = ids
    with pytest.raises(ValidationError):
        VerificationRequest.model_validate(data)


@pytest.mark.parametrize("text", ["Wait at least 1e3 seconds.", "Wait at least sixty seconds.", "Wait between 1 and 2 seconds.", "Wait from 20 to 10 seconds."])
def test_unsupported_numeric_policy_rejected(case_request, text):
    data = case_request("A06").model_dump()
    data["script"]["instructions"][0]["text"] = text
    data["script"]["instructions"][0]["approved_variants"] = []
    with pytest.raises(ValidationError):
        VerificationRequest.model_validate(data)


def test_fabricated_real_inference_provenance_rejected():
    with pytest.raises(ValidationError):
        SemanticAssessment(provider="fake", status="real", explanation="missing real call")


def test_invalid_evidence_length_rejected():
    with pytest.raises(ValidationError):
        EvidenceSpan(source="approved", text="test", start_char=0, end_char=3)
