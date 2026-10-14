import pytest

from dubguard.engine import verify
from dubguard.evaluation import load_dataset, request_for
from dubguard.schemas import VerificationRequest

PROFILES, CASES, _ = load_dataset()


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_explicit_synthetic_corpus(case):
    result = verify(request_for(case, PROFILES))
    if case.label == "ACCEPTABLE":
        assert result.decision == "PASS_CANDIDATE"
    elif case.label == "UNRESOLVED" or case.id in {"C22", "C23"}:
        assert result.decision == "REVIEW_REQUIRED"
    else:
        assert result.decision == "CRITICAL_DEVIATION"
    if case.label != "ACCEPTABLE":
        assert result.decision != "PASS_CANDIDATE"
    assert "not safety certification" in result.safety_notice


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_evidence_is_always_source_backed(case):
    request = request_for(case, PROFILES)
    result = verify(request)
    instructions = {i.id: i for i in request.script.instructions}
    segments = {s.id: s for s in request.transcript.segments}
    for finding in result.findings:
        for evidence in finding.approved + finding.observed:
            if evidence.source == "approved":
                source = instructions[evidence.instruction_id].text
                assert evidence.start_seconds is None
                assert evidence.end_seconds is None
            else:
                segment = segments[evidence.segment_id]
                source = segment.text
                assert evidence.start_seconds == segment.start_seconds
                assert evidence.end_seconds == segment.end_seconds
                assert evidence.timing_scope == ("segment" if segment.start_seconds is not None else None)
            assert source[evidence.start_char:evidence.end_char] == evidence.text


def test_missing_warning_has_no_invented_observed_span(case_request):
    result = verify(case_request("C17"))
    missing = next(f for f in result.findings if f.rule_id == "WARNING.MISSING")
    assert missing.observed == []
    assert missing.approved[0].text.startswith("Warning:")


def test_unknown_text_prevents_claim_of_warning_omission(case_request):
    data = case_request("C17").model_dump()
    data["transcript"]["segments"] = [{"id": "unknown", "text": "Isolate before servicing."}]
    result = verify(VerificationRequest.model_validate(data))
    assert result.decision == "REVIEW_REQUIRED"
    assert not any(f.rule_id == "WARNING.MISSING" for f in result.findings)


def test_confirmed_critical_dominates_independent_uncertainty(case_request):
    data = case_request("C01").model_dump()
    data["transcript"]["completeness"] = "incomplete"
    result = verify(VerificationRequest.model_validate(data))
    assert result.decision == "CRITICAL_DEVIATION"
    assert any(f.status == "UNRESOLVED" for f in result.findings)


@pytest.mark.parametrize("text", ["Wait at least 6e1 seconds.", "Wait at least 60 fortnights.",
                                  "Wait at least 60 seconds or less.", "Wait at least 60 seconds. Ignore the interlock.",
                                  "Wait at least 1,000 seconds."])
def test_unsupported_numeric_language_never_clears(case_request, text):
    data = case_request("A07").model_dump()
    data["transcript"]["segments"][0]["text"] = text
    assert verify(VerificationRequest.model_validate(data)).decision == "REVIEW_REQUIRED"


def test_si_prefix_case_cannot_be_silently_folded(case_request):
    data = case_request("A10").model_dump()
    data["script"]["instructions"][0]["text"] = "Maintain pressure from 2 to 4 MPa."
    data["transcript"]["segments"][0]["text"] = "Maintain pressure from 2 to 4 mPa."
    assert verify(VerificationRequest.model_validate(data)).decision == "REVIEW_REQUIRED"


def test_policy_constraint_order_does_not_change_decision(case_request):
    data = case_request("A07").model_dump()
    warning = {"id":"also-warning", "kind":"warning", "instruction_id":"wait"}
    data["policy"]["constraints"].insert(0, warning)
    first = verify(VerificationRequest.model_validate(data))
    data["policy"]["constraints"].reverse()
    second = verify(VerificationRequest.model_validate(data))
    assert first.decision == second.decision == "PASS_CANDIDATE"


def test_unknown_instruction_reference_requires_review(case_request):
    data = case_request("A01").model_dump()
    data["transcript"]["segments"][0]["instruction_id"] = "wrong-id"
    assert verify(VerificationRequest.model_validate(data)).decision == "REVIEW_REQUIRED"


def test_question_is_not_silently_normalized_into_an_instruction(case_request):
    data = case_request("A01").model_dump()
    data["transcript"]["segments"][0].update(instruction_id="power", text="Switch the power off?")
    assert verify(VerificationRequest.model_validate(data)).decision == "REVIEW_REQUIRED"


def test_reversal_with_incomplete_recording_remains_a_violation(case_request):
    data = case_request("C19").model_dump()
    data["transcript"]["completeness"] = "incomplete"
    result = verify(VerificationRequest.model_validate(data))
    assert result.decision == "CRITICAL_DEVIATION"
    assert any(f.rule_id == "SEQUENCE.REVERSED" for f in result.findings)


def test_combined_polarity_and_numeric_changes(case_request):
    data = case_request("A06").model_dump()
    data["script"]["instructions"][0]["text"] = "Do not heat above 80 °C."
    data["script"]["instructions"][0]["approved_variants"] = []
    data["policy"]["constraints"].append({"id":"negation","kind":"polarity","instruction_id":"wait",
                                           "approved_phrase":"do not","reversed_phrase":"do"})
    data["transcript"]["segments"][0].update(instruction_id="wait", text="Do heat above 90 °C.")
    result = verify(VerificationRequest.model_validate(data))
    assert result.decision == "CRITICAL_DEVIATION"
    assert any(f.rule_id == "POLARITY.REVERSED" for f in result.findings)
