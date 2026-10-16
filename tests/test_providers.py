import pytest

from dubguard.engine import verify
from dubguard.evaluation import evaluate
from dubguard.providers import AMDTokenFactoryProvider, DisabledProvider, MockProvider, provider_from_env
from dubguard.schemas import SemanticAssessment


@pytest.mark.parametrize("provider", [DisabledProvider(), MockProvider()])
def test_local_providers_never_claim_real_inference(case_request, provider):
    result = verify(case_request("A01"), hybrid=True, provider=provider)
    assert result.decision == "REVIEW_REQUIRED"
    assert not result.semantic.real_inference
    assert result.semantic.status != "real"


def test_invalid_amd_endpoint_never_makes_a_request(monkeypatch, case_request):
    monkeypatch.setenv("AMD_TOKEN_FACTORY_ENDPOINT", "http://insecure.invalid")
    monkeypatch.setenv("AMD_TOKEN_FACTORY_MODEL", "test-model")
    monkeypatch.setenv("AMD_TOKEN_FACTORY_API_KEY", "test-only-secret-marker")
    provider = AMDTokenFactoryProvider()
    assessment = provider.verify(case_request("A01"))
    assert assessment.status == "unavailable"
    assert not provider.real_inference_available
    assert "test-only-secret-marker" not in repr(provider) + assessment.model_dump_json()


def test_semantic_failure_is_graceful_and_redacted(case_request):
    class Broken:
        def verify(self, request):
            raise RuntimeError("sensitive-secret-marker")
    result = verify(case_request("C01"), hybrid=True, provider=Broken())
    assert result.decision == "CRITICAL_DEVIATION"
    assert result.semantic.status == "unavailable"
    assert "sensitive-secret-marker" not in result.model_dump_json()


def test_malformed_provider_result_is_unavailable(case_request):
    class Malformed:
        def verify(self, request):
            return {"status":"real", "explanation":"missing provenance"}
    result = verify(case_request("A01"), hybrid=True, provider=Malformed())
    assert result.decision == "REVIEW_REQUIRED"
    assert result.semantic.status == "unavailable"


def test_mock_equivalence_never_clears_uncertainty(case_request):
    result = verify(case_request("U02"), hybrid=True, provider=MockProvider())
    assert result.semantic.verdict == "EQUIVALENT"
    assert result.decision == "REVIEW_REQUIRED"


def test_real_provider_contract_stub_cannot_override_deterministic_findings(case_request):
    # In-memory contract test only, never included in evaluation reports or AMD metrics.
    class ContractStub:
        def verify(self, request):
            return SemanticAssessment(provider="test-contract", status="real", verdict="EQUIVALENT",
                                      explanation="Test fixture, no network", real_inference=True, response_valid=True,
                                      call_id="test-fixture-call", model="test-fixture-model")
    assert verify(case_request("C01"), hybrid=True, provider=ContractStub()).decision == "CRITICAL_DEVIATION"
    assert verify(case_request("U07"), hybrid=True, provider=ContractStub()).decision == "REVIEW_REQUIRED"


def test_hybrid_evaluation_skips_mock():
    report = evaluate(hybrid=True, provider=MockProvider())
    assert report["paths"]["C_hybrid"] == {
        "status":"skipped", "metrics":None, "cases":[],
        "reason":"Real inference is unavailable or was not requested. No mock/LLM/AMD performance result is claimed."}


def test_failing_real_provider_has_no_aggregate_hybrid_metrics():
    class Failed:
        real_inference_available = True
        def verify(self, request):
            raise TimeoutError()
    path = evaluate(hybrid=True, remote=True, max_cases=1, provider=Failed())["paths"]["C_hybrid"]
    assert path["status"] == "incomplete"
    assert path["metrics"] is None


def test_provider_environment_selection(monkeypatch):
    monkeypatch.setenv("DUBGUARD_SEMANTIC_PROVIDER", "amd")
    assert isinstance(provider_from_env(), AMDTokenFactoryProvider)
    monkeypatch.setenv("DUBGUARD_SEMANTIC_PROVIDER", "unsupported")
    with pytest.raises(ValueError):
        provider_from_env()
