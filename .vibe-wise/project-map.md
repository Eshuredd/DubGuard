# Project Map

## Purpose
DubGuard compares approved English industrial instructions against single-speaker
transcripts under explicit reviewer policies. It is a review aid, not certification.

## Requirements
- Detect protected quantities, polarity reversals, warning omissions/changes,
  and explicitly protected sequence changes.
- Allow approved variants; escalate uncertain evidence to human review.
- Preserve actual source evidence and supplied timestamps.
- Local CPU operation; no paid APIs, invented AMD endpoints/results, or automatic approval.
- No frontend or integrated transcription in Phase 1.
- No commits or pushes requested.

## Components
Implemented before learning mode; these are existing code, not learner-proposed designs:
- `src/dubguard/schemas.py`: Pydantic input/output contracts and policy validation.
- `src/dubguard/text.py`, `engine.py`: text/numeric handling and deterministic checks.
- `src/dubguard/providers.py`: disabled/mock semantic providers and unavailable AMD scaffold.
- `src/dubguard/api.py`: FastAPI health, validation, verification, and evaluation endpoints.
- `src/dubguard/cli.py`: local command entry point configured in `pyproject.toml`.
- `src/dubguard/evaluation.py`, `data/`: evaluation runner and explicit synthetic fixtures.
- `tests/`, `examples/`, `reports/`: tests, input examples, and generated reports.

## Main Flow
Script + reviewer policy + transcript segments
→ CLI or FastAPI → typed validation → deterministic checks
→ findings with evidence → pass candidate / critical deviation / review required.

Optional hybrid request → semantic provider interface → advisory result;
actual AMD transport is unimplemented and reports unavailable.

Evaluation fixtures → normalized-difference baseline + policy engine
→ JSON/Markdown metrics; real semantic evaluation is skipped without real inference.

## Data and Trust Boundaries
Inputs and fixtures are local JSON; reports are local JSON/Markdown.
Reviewer identity, transcript completeness, alignment, and ASR confidence are
supplied metadata, not independently authenticated facts. No audio transcription.
AMD configuration uses environment variables; current providers make no network calls.
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
Learner familiarity, experience, learning scope, and next task are not yet specified.
Real AMD endpoint/model/authentication/transport and ASR integration remain pending.
No learner design reasoning has yet been demonstrated or recorded.
