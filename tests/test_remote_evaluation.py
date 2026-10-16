import pytest

from dubguard.evaluation import evaluate
from dubguard.providers import MockProvider
from dubguard.schemas import SemanticAssessment


def test_remote_evaluation_requires_explicit_case_cap():
    with pytest.raises(ValueError, match="max_cases"):
        evaluate(hybrid=True, remote=True, provider=MockProvider())
    with pytest.raises(ValueError, match="positive"):
        evaluate(hybrid=True, remote=True, max_cases=0, provider=MockProvider())
    with pytest.raises(ValueError, match="hybrid"):
        evaluate(remote=True, max_cases=1, provider=MockProvider())


def test_hybrid_switch_alone_never_calls_provider():
    class WouldFail:
        real_inference_available = True
        def verify(self, request):
            raise AssertionError("remote call was not authorized")
    report = evaluate(hybrid=True, provider=WouldFail())
    assert report["paths"]["C_hybrid"]["status"] == "skipped"
    assert report["remote_request_attempts"] == 0


def test_policy_baseline_requires_remote_opt_in():
    with pytest.raises(ValueError, match="policy baseline"):
        evaluate(policy_baseline=True)


def test_remote_paths_compare_same_explicit_subset_with_stub():
    class ContractStub:
        real_inference_available = True
        calls = 0
        def result(self):
            self.calls += 1
            return SemanticAssessment(provider="in-memory-contract", status="real",
                                      verdict="EQUIVALENT", explanation="Synthetic protocol fixture.",
                                      real_inference=True, response_valid=True,
                                      call_id=f"fixture-{self.calls}", model="fixture-model", attempts=1)
        def verify_basic(self, request):
            return self.result()
        def verify(self, request):
            return self.result()
    stub = ContractStub()
    report = evaluate(hybrid=True, remote=True, max_cases=2, provider=stub)
    assert stub.calls == 4
    assert report["remote_request_attempts"] == 4
    assert report["dataset"]["remote_selected_count"] == 2
    assert report["paths"]["B_policy_engine"]["metrics"]["total"] == 60
    for name in ("B_policy_engine_selected_cases", "D_basic_llm", "C_hybrid"):
        assert report["paths"][name]["metrics"]["total"] == 2
    assert report["paths"]["D_basic_llm"]["status"] == "measured"
    assert report["paths"]["C_hybrid"]["status"] == "measured"


def test_optional_policy_baseline_uses_same_selected_cases():
    class ContractStub:
        real_inference_available = True
        calls = 0
        def result(self):
            self.calls += 1
            return SemanticAssessment(provider="in-memory-contract", status="real",
                                      verdict="UNRESOLVED", explanation="fixture",
                                      real_inference=True, response_valid=True,
                                      call_id=f"fixture-{self.calls}", model="fixture-model",
                                      attempts=1, usage={"total_tokens": 10})
        def verify_basic(self, request):
            return self.result()
        def verify_policy_baseline(self, request):
            return self.result()
        def verify(self, request):
            return self.result()
    stub = ContractStub()
    report = evaluate(hybrid=True, remote=True, max_cases=1,
                      policy_baseline=True, provider=stub)
    assert stub.calls == report["remote_request_attempts"] == 3
    assert report["paths"]["E_policy_llm"]["status"] == "measured"
    assert report["remote_token_usage"]["total_tokens"] == 30
