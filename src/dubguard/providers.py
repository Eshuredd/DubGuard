"""Pluggable advisory verification. This module makes no network calls."""

from dataclasses import dataclass, field
import os
from typing import Protocol

from .schemas import SemanticAssessment, VerificationRequest
from .text import normalize


class SemanticProvider(Protocol):
    name: str
    real_inference_available: bool

    def verify(self, request: VerificationRequest) -> SemanticAssessment: ...


@dataclass
class DisabledProvider:
    name: str = "disabled"
    real_inference_available: bool = False

    def verify(self, request: VerificationRequest) -> SemanticAssessment:
        return SemanticAssessment(provider=self.name, status="unavailable",
                                  explanation="Remote inference is disabled; deterministic findings remain available.")


@dataclass
class MockProvider:
    """An exact-text stub for interface tests, never an LLM or AMD result."""

    name: str = "local-mock"
    real_inference_available: bool = False

    def verify(self, request: VerificationRequest) -> SemanticAssessment:
        approved = [normalize(i.text) for i in request.script.instructions]
        observed = [normalize(s.text) for s in request.transcript.segments]
        return SemanticAssessment(provider=self.name, status="mock",
                                  verdict="EQUIVALENT" if approved == observed else "UNRESOLVED",
                                  explanation="Local exact-text mock only; no semantic model or remote call was used.")


@dataclass
class AMDTokenFactoryProvider:
    endpoint: str | None = field(default_factory=lambda: os.getenv("AMD_TOKEN_FACTORY_ENDPOINT"), repr=False, init=False)
    model: str | None = field(default_factory=lambda: os.getenv("AMD_TOKEN_FACTORY_MODEL"), repr=False, init=False)
    api_key: str | None = field(default_factory=lambda: os.getenv("AMD_TOKEN_FACTORY_API_KEY"), repr=False, init=False)
    name: str = "amd-token-factory-scaffold"
    real_inference_available: bool = False

    def verify(self, request: VerificationRequest) -> SemanticAssessment:
        missing = [name for name, value in (("endpoint", self.endpoint), ("model", self.model), ("API key", self.api_key)) if not value]
        reason = "Missing configuration: " + ", ".join(missing) if missing else "Configuration present; the AMD request/response contract is not implemented"
        # TODO: Confirm AMD's actual endpoint, model ID, authentication, payload,
        # structured output format, timeout/retry rules, and usage/cost controls.
        # TODO: Validate cited source spans, log request/model provenance without
        # secrets, and mark status=real only after a successful real inference call.
        return SemanticAssessment(provider=self.name, status="unavailable",
                                  explanation=reason + ". No network request was made.")


def provider_from_env() -> SemanticProvider:
    name = os.getenv("DUBGUARD_SEMANTIC_PROVIDER", "disabled")
    providers = {"disabled": DisabledProvider, "mock": MockProvider, "amd": AMDTokenFactoryProvider}
    if name not in providers:
        raise ValueError("DUBGUARD_SEMANTIC_PROVIDER must be disabled, mock, or amd")
    return providers[name]()
