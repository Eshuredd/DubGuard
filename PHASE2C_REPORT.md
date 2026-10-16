# Phase 2C implementation report

Inspected clean main at `78acbf0`, fetched origin/main and confirmed zero commits
of divergence before editing. Baseline: 247 tests passed. Retained FastAPI,
Pydantic, HTTPX, the deterministic rules, CPU Whisper/FFmpeg path and SQLite.
No commit, push, frontend, model download, new dependency or .env edit was performed.
Version is now 0.4.0 to identify the changed evidence contract.

## Implemented architecture

Raw ASR remains immutable and provisional. Every raw-ASR verification is
REVIEW_REQUIRED regardless of confidence or model agreement. Existing deterministic
rules also examine a separate, nonpersistent candidate copy. Unique textual
alignment proposals may support candidate discovery, never equivalence. Candidate
violations are emitted as ASR.SUSPECTED.* with UNRESOLVED status, linked constraint
IDs and original source spans/timestamps. The candidate pass cannot establish an
omission from unconfirmed ASR completeness.

An authenticated reviewer listens to original audio and submits actual spoken
words via POST /review/workflows/{id}/transcript-evidence. The record binds the
original audio hash, raw transcription ID, prior correction ID, reviewer identity,
reason and timestamp. Input revision protects against stale submissions. Human
transcripts can remain incomplete/uncertain. Neither alignment confirmation nor
recognizer agreement creates human evidence. GET workflow record_history exposes
successful raw evidence, alignment, correction and verification versions.

The off/on protocol regression uses silent PCM plus stub ASR, **not actual
recorded speech**. Raw “Switch the power on.” produces a suspected polarity
reversal and REVIEW_REQUIRED. Mapping confirmation still yields REVIEW_REQUIRED.
A simulated authenticated human verification of the same words produces
POLARITY.REVERSED / CRITICAL_DEVIATION. Ordinary acceptance and release signoff
are rejected. This measures workflow behavior, not acoustic recognition accuracy.

## Approval invariants

- Approvals bind immutable policy/script records and revisions, exact audio hash,
  human evidence revision ID, verification run ID and full input snapshot.
- Transcription, alignment, acoustic or human-evidence changes invalidate the run.
  Transcription replacement also clears dependent evidence/alignment/acoustic IDs.
  Policy/audio changes require a new workflow; supersedes invalidates old approvals.
- Every finding decision specifies the exact verification run. Only SATISFIED
  findings may be ACCEPTED_AS_CORRECT. Actual critical violations require a new
  corrected recording/workflow; no exception endpoint bypasses this rule.
- Unresolved checks block release. Signoff independently rechecks deterministic
  rules on the human transcript, so even an empty finding list cannot conceal a
  violation. Zero-findings runs have an explicit human signoff path with the same
  evidence, coverage, source hash and current-run prerequisites.
- Complete processing is necessary but not proof of transcription accuracy.
  Human review must attest complete actual spoken content separately.
- SQLite BEGIN IMMEDIATE serializes eligibility and finalization. Repeated and
  concurrent signoff cannot reuse readiness. Input snapshots reject stale results.
  Starting a job invalidates readiness; pending jobs block unrelated input edits.
  Failed or stale jobs cannot restore readiness or change a superseding workflow.
- All reviewer endpoints require configured bearer authentication. Policy identities
  and evidence identities derive from that authentication, not submitted names.
- Additive migrations preserve legacy approvals and label those without evidence
  bindings LEGACY_UNVERIFIED. Old active runs without snapshots must be rerun.

## Measured validation

Final command: `.venv/bin/python -m pytest -q`.
**271 passed, 0 failed**, in 1.59 seconds in this workspace. One upstream
Starlette/AnyIO deprecation warning remains. Tests include the existing suite plus
stale corrections, stale verification output, input invalidation, concurrent and
repeated signoff, critical/unresolved override rejection, zero-findings safeguards,
failed/pending jobs, changed audio, migration, authenticated evidence, timeout
classification, smoke preparation, and audio-report field separation.

Old tests that permitted acceptance of unresolved findings now assert rejection.
Two corpus tests now assert that acceptable raw ASR requires review. Ground-truth
labels were not edited. Reproducible JSON/Markdown reports were regenerated locally:

| Path | Cases | Critical recall | Precision | Acceptable false critical alerts | Unresolved |
|---|---:|---:|---:|---:|---:|
| Text-difference baseline | 60 | 24/24 (100%) | 24/45 (53.33%) | 16/24 (66.67%) | 7/60 (11.67%) |
| Policy engine | 60 | 22/24 (91.67%) | 22/22 (100%) | 0/24 (0%) | 16/60 (26.67%) |

Policy-engine mismatches: C22/C23 are critical semantic challenges escalated to
review instead of confirmed deviation; A18/A23 are acceptable raw ASR escalated
under the new evidence boundary. Acceptable escalation is 2/24 (8.33%). There are
zero unsafe passes on this synthetic development set only. Remote baseline/hybrid
paths were skipped. The text baseline retains its original simple gate for a
stable comparator and is never eligible for production signoff.

## Actual audio and AMD status

Human-verified recorded cases available/run: **0**. No real-audio accuracy,
confusion recall or human-workload results are claimed. RECORDING_GUIDE.md and
examples/phase2c-recordings.template.json prepare six cases: correct, 15/50, on/off,
before/after, approved paraphrase and unclear. Placeholders deliberately fail
manifest validation. Audio evaluation now exports raw transcript, duration,
coverage/gaps, timestamp validity, tentative alignment, suspected findings,
optional human-corrected evidence, final verification decision and ASR latency.
Evaluation does not create approvals; manifest adjudicator metadata is not
production authentication.

New real AMD calls: **0**, pending authorization. Both smoke preparation commands
returned prepared_only / http_calls=0. Historical reports show:

- reports/amd_smoke.json: one successful DeepSeek response, 21,837.67 ms; off/on
  semantic concern but invalid citation rejected by the evidence validator.
- reports/amd_smoke_phase2.json: one unavailable attempt, 40,804.01 ms. The old
  generic transport/timeout diagnostic cannot identify connect versus read timeout
  or prove model generation latency. No new diagnosis is invented from this data.

Provider now caps output tokens (default 1024, configurable 64–4096) and distinguishes
connect/read/write/pool timeout and other transport failures. Connect timeout is
separately configurable; configured semantic retry count was not increased.
Smoke commands cap semantic output at 512 tokens and force one HTTP attempt.
MiMo remains independently configured and uses documented base64 WAV input;
its probe defaults to zero retries, with configurable audio timeout. A small real
WAV can be supplied after recording; no fabricated sample was sent.

## Changed files

- src/dubguard/engine.py, schemas.py: provisional findings and human evidence schemas.
- src/dubguard/review.py: migration, evidence history, run snapshots, transaction
  checks, authenticated corrections, job invalidation and guarded human signoff.
- src/dubguard/providers.py, amd_audio.py, smoke.py: bounded requests, diagnostics
  and explicit opt-in probes.
- src/dubguard/audio_evaluation.py: requested per-recording evidence report fields.
- tests/test_phase2c.py plus test_phase2.py, test_engine.py and
  test_api_cli_evaluation.py: new regression coverage and changed boundary assertions.
- pyproject.toml, src/dubguard/__init__.py, api.py, evaluation.py: version 0.4.0.
- .env.example, README.md, RECORDING_GUIDE.md, this report and the six-case template.
- reports/evaluation.json, evaluation.md and phase2_sets.json: local refreshed reports.

## Run commands and next phase

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m uvicorn dubguard.api:app --host 127.0.0.1 --port 8000
.venv/bin/python -m dubguard evaluate --output reports
.venv/bin/python -m dubguard.smoke semantic examples/critical.json
.venv/bin/python -m dubguard.smoke audio /absolute/path/to/on-off.wav
.venv/bin/python -m dubguard.audio_evaluation /absolute/path/manifest.json --model-path /absolute/path/cached-model --output reports/recorded_audio.json
```

The smoke commands above only prepare. After explicit authorization, append
`--execute --output reports/amd_semantic_phase2c.json` or the corresponding audio
report name. They never change .env. No remote full benchmark is automatic.

Collect/adjudicate the six recordings, then authorize single-attempt DeepSeek and
MiMo probes. Review actual evidence and error cases before frontend integration.
A subsequent frontend should display original audio, raw ASR, correction history,
tentative/confirmed mapping, blocking checks and run-bound human signoff.

Remaining limits: in-process jobs are not durable; SQLite history is not
tamper-proof; shared-token authentication has no enterprise identity/role lifecycle;
acoustic disagreements remain blocking without a dedicated human-resolution
endpoint; no live validation of the new AMD token bound/citation protocol has run;
Docker execution was not validated here. Human attestation is an accountability
record, not proof that a listener was truthful. DubGuard does not certify safety.
