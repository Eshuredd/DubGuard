import json

import httpx
import pytest

from dubguard.engine import verify
from dubguard.providers import AMDTokenFactoryProvider


@pytest.fixture(autouse=True)
def fake_amd_configuration(monkeypatch):
    # Every provider in this file uses a fake HTTPS host and an injected mock
    # transport; running pytest cannot contact AMD or spend credits.
    monkeypatch.setenv("AMD_TOKEN_FACTORY_ENDPOINT", "https://unit.test/radeon/api/v1")
    monkeypatch.setenv("AMD_TOKEN_FACTORY_MODEL", "unit-model")
    monkeypatch.setenv("AMD_TOKEN_FACTORY_API_KEY", "test-only-secret-marker")
    monkeypatch.setenv("AMD_TOKEN_FACTORY_MAX_RETRIES", "0")


def finding(request, *, verdict="DEVIATION", **changes):
    instruction = request.script.instructions[0]
    segment = request.transcript.segments[0]
    item = {
        "requirement_id": request.policy.constraints[0].id,
        "kind": "POLARITY", "verdict": verdict,
        "instruction_id": instruction.id,
        "approved_evidence": [{"instruction_id": instruction.id, "quote": instruction.text,
                               "start_char": 0, "end_char": len(instruction.text)}],
        "observed_evidence": [{"instruction_id": instruction.id, "segment_id": segment.id,
                               "quote": segment.text, "start_char": 0, "end_char": len(segment.text)}],
        "explanation": "The state may differ.",
    }
    item.update(changes)
    return item


def envelope(payload, *, call_id="unit-call", model="unit-model"):
    return {"id": call_id, "model": model,
            "choices": [{"message": {"content": json.dumps(payload)}, "finish_reason": "stop"}]}


def provider_with(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return AMDTokenFactoryProvider(client=client)


def test_real_transport_shape_and_valid_suspected_finding(case_request):
    request = case_request("A01")
    seen = []

    def handler(http_request):
        seen.append(http_request)
        payload = {"verdict": "DEVIATION", "explanation": "State may be wrong.",
                   "findings": [finding(request)]}
        return httpx.Response(200, json=envelope(payload))

    provider = provider_with(handler)
    result = verify(request, hybrid=True, provider=provider)
    assert len(seen) == 1
    assert str(seen[0].url) == "https://unit.test/radeon/api/v1/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer test-only-secret-marker"
    body = json.loads(seen[0].content)
    assert body["model"] == "unit-model"
    assert body["messages"][0]["role"] == "system"
    assert "power-state" in body["messages"][1]["content"]
    source = json.loads(body["messages"][1]["content"].split("\n", 1)[1])
    assert source["citation_templates"]["approved"][0]["end_char"] == len(request.script.instructions[0].text)
    assert source["citation_templates"]["observed"][0]["quote"] == request.transcript.segments[0].text
    assert result.decision == "REVIEW_REQUIRED"
    assert result.semantic.status == "real"
    assert result.semantic.call_id == "unit-call"
    assert result.semantic.attempts == 1
    assert result.semantic.latency_ms >= 0
    suspect = next(f for f in result.findings if f.rule_id == "SEMANTIC.SUSPECTED_DEVIATION")
    assert suspect.constraint_id == "power-state"
    assert suspect.approved[0].text == "Switch the power off."
    assert suspect.observed[0].text == "Switch the power off."
    assert suspect.model_call_id == "unit-call"
    assert "test-only-secret-marker" not in result.model_dump_json() + repr(provider)


@pytest.mark.parametrize("change", [
    {"requirement_id": "invented"},
    {"instruction_id": "invented"},
    {"observed_evidence": [{"instruction_id":"power", "segment_id":"invented", "quote":"x", "start_char":0, "end_char":1}]},
    {"approved_evidence": [{"instruction_id":"power", "quote":"fabricated", "start_char":0, "end_char":10}]},
    {"observed_evidence": [{"instruction_id":"power", "segment_id":"s1", "quote":"Switch the power off.", "start_char":1, "end_char":22}]},
    {"kind": "WARNING_POLICY"},
    {"observed_evidence": [{"instruction_id":"power", "segment_id":"s1", "quote":"Switch the power off.", "start_char":0, "end_char":21, "start_seconds":99}]},
])
def test_invalid_model_reference_becomes_linked_review(case_request, change):
    request = case_request("A01")
    payload = {"verdict": "DEVIATION", "explanation": "Concern.",
               "findings": [finding(request, **change)]}
    provider = provider_with(lambda _: httpx.Response(200, json=envelope(payload)))
    result = verify(request, hybrid=True, provider=provider)
    assert result.decision == "REVIEW_REQUIRED"
    assert not result.semantic.findings
    assert result.semantic.issues
    issue = next(f for f in result.findings if f.rule_id == "SEMANTIC.INVALID_EVIDENCE")
    assert issue.constraint_id == (None if change.get("requirement_id") == "invented" else "power-state")
    assert "fabricated" not in issue.model_dump_json()


@pytest.mark.parametrize("case_id,kind,verdict", [
    ("C06", "NUMERIC_LIMIT", "DEVIATION"),
    ("C19", "PROCEDURE_ORDER", "DEVIATION"),
    ("C18", "WARNING_POLICY", "DEVIATION"),
    ("U07", "PARAPHRASE", "EQUIVALENT"),
])
def test_requirement_linked_model_categories(case_request, case_id, kind, verdict):
    request = case_request(case_id)
    segment = request.transcript.segments[0]
    instruction_id = segment.instruction_id
    if instruction_id is None:
        instruction_id = next(i.id for i in request.script.instructions if i.text == segment.text)
    instruction = next(i for i in request.script.instructions if i.id == instruction_id)
    requirement = next(c for c in request.policy.constraints if
                       (instruction_id in c.instruction_ids if c.kind == "sequence" else c.instruction_id == instruction_id))
    model_finding = {
        "requirement_id": requirement.id, "kind": kind, "verdict": verdict,
        "instruction_id": instruction_id,
        "approved_evidence": [{"instruction_id": instruction_id, "quote": instruction.text,
                               "start_char": 0, "end_char": len(instruction.text)}],
        "observed_evidence": [{"instruction_id": instruction_id, "segment_id": segment.id,
                               "quote": segment.text, "start_char": 0, "end_char": len(segment.text)}],
        "explanation": "Mocked category-specific advisory finding.",
    }
    payload = {"verdict": verdict, "explanation": "Mocked category-specific comparison.",
               "findings": [model_finding]}
    result = verify(request, hybrid=True,
                    provider=provider_with(lambda _: httpx.Response(200, json=envelope(payload))))
    assert result.semantic.status == "real"
    assert result.semantic.findings[0].kind == kind
    assert result.semantic.findings[0].requirement_id == requirement.id
    assert result.semantic.findings[0].observed[0].text == segment.text
    if case_id == "U07":
        assert result.decision == "REVIEW_REQUIRED"  # Model equivalence cannot clear deterministic uncertainty.
    else:
        assert result.decision in {"CRITICAL_DEVIATION", "REVIEW_REQUIRED"}


def test_valid_finding_survives_independent_bad_finding(case_request):
    request = case_request("A01")
    payload = {"verdict": "DEVIATION", "explanation": "Mixed response.",
               "findings": [finding(request), finding(request, requirement_id="invented")]}
    result = verify(request, hybrid=True,
                    provider=provider_with(lambda _: httpx.Response(200, json=envelope(payload))))
    assert len(result.semantic.findings) == 1
    assert len(result.semantic.issues) == 1
    assert result.decision == "REVIEW_REQUIRED"


def test_observed_time_is_copied_from_request_not_model(case_request):
    request = case_request("A18")
    payload = {"verdict": "DEVIATION", "explanation": "Concern.",
               "findings": [finding(request)]}
    result = verify(request, hybrid=True,
                    provider=provider_with(lambda _: httpx.Response(200, json=envelope(payload))))
    span = result.semantic.findings[0].observed[0]
    assert (span.start_seconds, span.end_seconds, span.timing_scope) == (1.2, 2.8, "segment")


def test_deterministic_violation_survives_model_equivalence(case_request):
    request = case_request("C01")
    payload = {"verdict": "EQUIVALENT", "explanation": "No concern.", "findings": []}
    result = verify(request, hybrid=True,
                    provider=provider_with(lambda _: httpx.Response(200, json=envelope(payload))))
    assert result.decision == "CRITICAL_DEVIATION"
    assert any(f.rule_id == "POLARITY.REVERSED" for f in result.findings)


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_http_failures_escalate_without_echoing_body(case_request, status):
    result = verify(case_request("A01"), hybrid=True,
                    provider=provider_with(lambda _: httpx.Response(status, text="test-only-secret-marker")))
    assert result.decision == "REVIEW_REQUIRED"
    assert result.semantic.status == "unavailable"
    assert "test-only-secret-marker" not in result.model_dump_json()


def test_rate_limit_retry_is_bounded(case_request, monkeypatch):
    monkeypatch.setenv("AMD_TOKEN_FACTORY_MAX_RETRIES", "1")
    sleeps = []
    monkeypatch.setattr("dubguard.providers.time.sleep", sleeps.append)
    request = case_request("A01")
    calls = []

    def handler(http_request):
        calls.append(http_request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "500"})
        return httpx.Response(200, json=envelope({"verdict":"EQUIVALENT", "explanation":"Exact.", "findings":[]}))

    result = verify(request, hybrid=True, provider=provider_with(handler))
    assert result.semantic.status == "real"
    assert result.semantic.attempts == 2
    assert len(calls) == 2
    assert sleeps == [2.0]


def test_timeout_is_bounded_and_unavailable(case_request, monkeypatch):
    monkeypatch.setenv("AMD_TOKEN_FACTORY_MAX_RETRIES", "1")
    monkeypatch.setattr("dubguard.providers.time.sleep", lambda _: None)
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("test-only-secret-marker", request=request)

    result = verify(case_request("A01"), hybrid=True, provider=provider_with(handler))
    assert result.semantic.status == "unavailable"
    assert result.semantic.attempts == 2
    assert len(calls) == 2
    assert "test-only-secret-marker" not in result.model_dump_json()


@pytest.mark.parametrize("content", ["not JSON", "{}", '{"verdict":"DEVIATION","findings":[]}'])
def test_invalid_json_or_unsupported_shape_is_unavailable(case_request, content):
    result = verify(case_request("A01"), hybrid=True, provider=provider_with(
        lambda _: httpx.Response(200, json=envelope(json.loads(content) if content.startswith("{") else content))))
    assert result.decision == "REVIEW_REQUIRED"
    assert result.semantic.status == "unavailable"
