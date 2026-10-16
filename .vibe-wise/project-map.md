# Project Map

## Purpose
DubGuard compares approved English industrial instructions against single-speaker
transcripts under explicit reviewer policies. It is a review aid, not certification.

## Requirements
- Detect protected quantities, polarity reversals, warning omissions/changes,
  and explicitly protected sequence changes.
- Allow approved variants; escalate uncertain evidence to human review.
- Preserve actual source evidence and supplied timestamps.
- Local CPU operation for deterministic checks; explicit real AMD inference in
  Phase 2A, with measured calls only and no automatic approval.
- No frontend or integrated transcription in Phase 1.
- No commits or pushes requested.

## Components
Implemented before learning mode; these are existing code, not learner-proposed designs:
- `src/dubguard/schemas.py`: Pydantic input/output contracts and policy validation.
- `src/dubguard/text.py`, `engine.py`: text/numeric handling and deterministic checks.
- `src/dubguard/providers.py`: disabled/mock providers and real AMD HTTPS transport.
- `src/dubguard/semantic_validation.py`: strict model-response and evidence checks.
- `src/dubguard/api.py`: FastAPI health, validation, verification, and evaluation endpoints.
- `src/dubguard/cli.py`: local command entry point configured in `pyproject.toml`.
- `src/dubguard/evaluation.py`, `data/`: evaluation runner and explicit synthetic fixtures.
- `tests/`, `examples/`, `reports/`: tests, input examples, and generated reports.

## Main Flow
Script + reviewer policy + transcript segments
→ CLI or FastAPI → typed validation → deterministic checks
→ findings with evidence → pass candidate / critical deviation / review required.

Optional hybrid request → AMD provider → validated source-linked advisory result;
confirmed deterministic violations and uncertainty keep their precedence.

Evaluation fixtures → normalized-difference baseline + policy engine
→ JSON/Markdown metrics. Explicit `--remote --max-cases N` additionally runs a
basic LLM comparator and policy-hybrid path on the same selected subset.

## Data and Trust Boundaries
Inputs and fixtures are local JSON; reports are local JSON/Markdown.
Reviewer identity, transcript completeness, alignment, and ASR confidence are
supplied metadata, not independently authenticated facts. No audio transcription.
AMD configuration loads the ignored project `.env` when selected; bearer secrets
are not printed or included in the model prompt. Remote calls require hybrid
verification or explicitly capped remote evaluation.
The user reports a verified real AMD Token Factory endpoint, OpenAI-compatible
chat completions API, bearer authentication, and model `DeepSeek-V4-Flash`. The
ignored `.env` contains the four expected configuration variable names; its
credential values have not been printed or changed.
No persistence service or authentication layer was added in Phase 1.

## Build and Deployment
Python >=3.11; FastAPI, Pydantic, Uvicorn; pytest/httpx for testing.
Dependencies: `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`.
Commands: `.venv/bin/python -m pytest -q`,
`.venv/bin/python -m dubguard evaluate --output reports`,
`.venv/bin/python -m uvicorn dubguard.api:app --host 127.0.0.1 --port 8000`.
CPU `Dockerfile` exists. Previous task verified 200 tests and live API endpoints;
Docker daemon was unavailable then. Tests have not been rerun during onboarding.
Git metadata is now present at the workspace root; no Git mutations made by onboarding.

## Unknowns
The learner is new to DubGuard, reports intermediate overall programming and
beginner familiarity with Python/Pydantic/FastAPI, and wants to understand the
whole system. Phase 2A real AMD integration is requested. The learner chose a
deterministic-first, evidence-validated advisory design; implementation is in progress.
AMD transport is implemented; one live example call returned a model explanation
but its detailed citation failed local source validation and was escalated.
ASR integration, calibrated semantic evaluation, and held-out industrial review
remain pending.
The learner's Phase 2A design reasoning is recorded in `progress.md`.
