# DubGuard — Industrial Narration Review

Phases 1–5: evidence integrity, opt-in AMD semantic review and deployment validation for AMD Developer Hackathon
Act III, **Intelligent Industry**. The deterministic engine compares approved
English single-speaker narration under reviewer-defined constraints; optional
local audio transcription, a versioned human review API, and a React reviewer application now surround it.

See [Phase 5 delivery report](PHASE5_REPORT.md), [release checklist](RELEASE_CHECKLIST.md),
[submission package](SUBMISSION_PACKAGE.md), [Phase 4 delivery report](PHASE4_REPORT.md), [single-server deployment](DEPLOYMENT.md),
[Phase 3 delivery report](PHASE3_REPORT.md) and [frontend setup](frontend/README.md).

**PASS_CANDIDATE is not safety certification, release approval, or a guarantee of
semantic equivalence.** Ambiguous evidence requires human review. ASR is provisional;
only an authenticated reviewer can sign off a recording. AMD semantic inference
is available only when explicitly selected for hybrid verification, consented
Quick Test AMD review, or remote evaluation.

## Run locally

Python 3.11+ is required; historical reports used 3.11.9 and Phase 4 used 3.12.7.
Run these commands from the project directory. Installation fetches ordinary
Python dependencies; deterministic execution needs no API key, network service,
GPU, or model.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt -e .
.venv/bin/python -m pip install -r requirements-audio.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m dubguard validate examples/policy.json
.venv/bin/python -m dubguard verify examples/acceptable.json
.venv/bin/python -m dubguard verify examples/critical.json
.venv/bin/python -m dubguard verify examples/asr-segments.json
.venv/bin/python -m dubguard transcribe-audio /absolute/path/to/recording.wav
.venv/bin/python -m dubguard evaluate --output reports
.venv/bin/python -m dubguard.phase2_evaluation --output reports/phase2_sets.json
.venv/bin/python -m uvicorn dubguard.api:app --host 127.0.0.1 --port 8000
```

The installed `dubguard` entry point and `python -m dubguard` are equivalent.
CLI exit code 0 means successful execution, **not approval**; consume the JSON
`decision`. Invalid input/configuration/file errors return exit code 2.

With the API running in a separate terminal:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail -H 'Content-Type: application/json' --data-binary @examples/policy.json http://127.0.0.1:8000/validate
curl --fail -H 'Content-Type: application/json' --data-binary @examples/critical.json http://127.0.0.1:8000/verify
curl --fail http://127.0.0.1:8000/evaluation/reports
curl --fail 'http://127.0.0.1:8000/evaluation/reports?format=markdown'
```

Interactive API schemas are at [localhost /docs](http://127.0.0.1:8000/docs).
`POST /validate` validates a `{script, policy}` body. `POST /verify` validates and
analyzes `{script, policy, transcript}`; `?mode=hybrid` requests advisory semantic
verification and requires reviewer bearer authentication. Invalid schemas return HTTP 422. `GET /evaluation/reports` reruns
only local paths A and B; GET never starts remote inference. This is a local
development service. The new `/review/*` routes require configured bearer-token
authentication; local `/validate` and deterministic `/verify` remain public development endpoints.

## What is implemented

| Component | Status |
|---|---|
| Typed scripts, constraints, variants, transcripts, findings, evidence, decisions, labels | Implemented with Pydantic and JSON/OpenAPI schemas |
| Numeric values, bounds, ranges, exact unit conversions | Implemented for the limited grammar below |
| Explicit polarity/negation reversals | Implemented through reviewer-declared phrase pairs |
| Protected warnings and operation sequences | Implemented, including confirmed omissions and reversed relative order |
| Explicit approved variants and unresolved evidence | Implemented; no similarity-based clearance |
| CLI, FastAPI validation/verification/report endpoints | Implemented and tested |
| 60 explicit synthetic fixtures, baseline, reproducible JSON/Markdown | Implemented and measured locally |
| Local semantic provider | Exact-text **mock**, solely for interface/failure tests |
| AMD Token Factory provider | Real OpenAI-compatible chat completions via HTTPS with bounded retries/timeouts and source-validated JSON |
| Real semantic evaluation paths | Prepared as opt-in, capped, separate basic LLM and policy-hybrid paths; local reports skip them |
| Timestamped ASR segment input | Implemented contract and optional local CPU Whisper adapter; ASR output is provisional |
| Audio intake and review | WAV/MP3/WebM Opus/MP4 AAC intake, FFmpeg normalization, complete-file chunking/coverage, SQLite review API |
| Acoustic recheck | Independent local model hook with protected-term disagreement; requires a separately installed secondary model |
| MiMo audio | Documented opt-in probe scaffold; no live audio call or quality result yet |
| CPU container deployment | Backend/frontend images, pinned cache, localhost routing, real CPU silence-ASR, persistence and restart checks executed in Phase 5; public HTTPS still pending |
| React reviewer application | Quick Test, browser recording, authenticated full review, evidence correction, run-bound signoff and export |
| Browser capture | Chrome MediaRecorder exercised with a synthetic device; Safari MIME selection implemented but not manually verified |

Multilingual dubbing, video editing, model training, automatic certification, and
automatic release approval are excluded. ASR requires an already cached model or
local model directory; missing models fail visibly without automatic downloads.

### Start the reviewer application

Node.js 22.22.2+ (22.x), 24.15+ (24.x), or 26+ and the audio dependencies above are required. Configure private
environment variables as described under “Audio and human-review workflow”:
`DUBGUARD_REVIEW_TOKENS_JSON`, `DUBGUARD_DATA_DIR`, and a cached
`DUBGUARD_WHISPER_MODEL`. Quick Test additionally needs a separate random
`DUBGUARD_DEMO_ACCESS_CODE` of at least 24 characters. Never reuse a reviewer token.

Start the API using the uvicorn command above, then in another terminal:

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open http://127.0.0.1:5173/test for Quick Test or /login for Full Review.
The Vite server proxies /api to port 8000. Refresh/deep links are supported.
Microphone permission is requested only after clicking Record narration; capture
and submission are separate explicit actions. HTTPS or localhost is required.

```bash
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run test:e2e
npm --prefix frontend run generate:api
```

End-to-end tests require installed desktop Chrome and free ports 8000/5173.
They use isolated temporary storage, generated test credentials and stub ASR,
not your .env credentials. They do not establish recognition accuracy.
See frontend/README.md for retention, format, and deployment details.

## Policy and evidence model

An approved script has an ID, revision, and ordered atomic `instructions`. Each
instruction has an ID, text, and optional `approved_variants`, each recording its
text, `approved_by`, and reason. A policy has its own ID/revision, reviewer identity,
ASR confidence threshold (default 0.9), and explicitly selected constraints:

- `numeric`: protects **all** parsed quantities in one instruction. Expected
  values come from the approved instruction, preventing duplicate sources of truth.
- `polarity`: declares `approved_phrase` and `reversed_phrase`, for example
  `off` → `on`, `closed` → `open`, or `do not` → `do`.
- `warning`: protects an instruction against omission and optionally declares
  specific dangerous `forbidden_wordings`. Unknown warning rewrites require review.
- `sequence`: lists at least two instruction IDs in required relative order.
  Each listed step is protected against omission. Order is not globally enforced
  unless explicitly protected by a sequence constraint.

See `src/dubguard/data/profiles.json` for complete examples of each constraint.
Validation rejects unknown references, duplicate IDs, conflicting numeric/polarity
variants, contradictory warning wordings, and inconsistent protected sequences.
Arbitrary semantic contradictions cannot be validated mechanically: the person
approving policies must actually review the script and each variant. Recorded
reviewer names are metadata, not proof of authorization. Synthetic fixture
reviewers are placeholders, not industrial experts or real approvals.

Each transcript has `source` (`manual` or `asr`), `completeness` (`complete`,
`incomplete`, or default `unknown`), and ordered `segments`. Segment fields:

```json
{
  "id": "segment-1",
  "instruction_id": "power",
  "text": "Switch the power off.",
  "start_seconds": 1.2,
  "end_seconds": 2.8,
  "confidence": 0.98,
  "uncertain": false
}
```

`instruction_id` is an explicit, reviewer-supplied alignment. Without it, only a
unique exact/approved wording can align automatically. A changed transcription
often needs a reviewed ID; fuzzy matching never establishes equivalence. One
segment per atomic instruction is supported. Duplicate mappings, unknown IDs,
extra unaligned text, and split instructions require review.

Both timestamps may be omitted. If supplied, both are required, finite,
nonnegative, and ordered without overlap. Array order is narration order even
without timestamps. Times describe the **whole segment**, not individual words.
Evidence spans are exact source substrings with character offsets; findings show
the complete approved/observed instruction spans for context. Omitted evidence
has an empty observed list and **no invented timestamp**.

Raw ASR always remains provisional, even with high confidence or recognizer agreement.
It can produce `ASR.SUSPECTED.*` rule findings with status `UNRESOLVED`, using
tentative mappings solely to discover candidates. Confirming alignment does not
verify spoken text. Empty text, unknown markers and uncertain segments remain
unresolved. Authenticated human transcript evidence is a separate versioned record. Explicit complete
coverage is necessary to conclude an omission; incomplete/unknown coverage or
unaligned/uncertain segments prevent a definitive omission claim. A definite
independent violation can still be reported alongside unresolved evidence.

## Analysis boundaries

The decision precedence is:

1. Any proven policy violation → `CRITICAL_DEVIATION`.
2. Otherwise any unresolved finding → `REVIEW_REQUIRED`.
3. Otherwise → `PASS_CANDIDATE` (no violation detected within these rules).

Rule IDs such as `NUMERIC.CHANGED`, `POLARITY.REVERSED`, `WARNING.MISSING`,
`SEQUENCE.REVERSED`, and `EVIDENCE.UNCERTAIN` identify findings independently of
policy constraint IDs. Findings retain both satisfied and unresolved checks.
Changed text without a supported critical constraint remains unresolved.

Generic normalization permits case/whitespace and terminal periods/exclamation
marks; question marks remain significant. It preserves numeric unit-token case
to avoid SI-prefix errors. Pass candidates
require exact/approved wording, or a verified numeric representation change within
an otherwise identical approved template. No embedding distance, edit similarity,
or shared-keyword score asserts semantic equivalence.

Numeric rules support signed decimal digits, `2 to 4` / `2–4` / `2-4` ranges,
counts, and adjacent bounds such as `at least`, `at most`, `below`, and
`at or below`. Exact rational arithmetic handles time, Celsius/Fahrenheit/kelvin,
pressure, length, mass, percentage, rpm, voltage, and current. The supported unit
aliases and conversion constants are in `text.py`. Inclusive and exclusive bounds
are distinct; rounded near-equivalents do not silently pass. SI symbol case is
validated. Counts and unknown unit words may only retain their exact surrounding
wording; no conversion is inferred for an unsupported unit.

Spelled-out numbers, scientific notation, grouped thousands, mathematical bound
symbols, `between` ranges, contextual references, arbitrary paraphrases, and
cross-instruction reasoning are outside the numeric grammar. Changed unsupported
wording requires review; unsupported numeric policy forms are rejected. A numeric
approved variant must itself express the same parsed quantities. Automatic
alignment cannot safely recover arbitrary sentence merges or reordered clauses.

## Reproducible evaluation

`src/dubguard/data/cases.json` contains **60 separately specified cases with IDs,
labels, rationales, and transcripts**, not labels computed from engine results.
There are 24 acceptable, 24 critical, and 12 unresolved cases across 17 categories.
These labels are explicit synthetic development fixtures, not external LLM outputs
or independently adjudicated industrial ground truth. The data is a development
set, not a held-out benchmark.

| Path | Critical recall | Precision | False-alert rate on acceptable | Unresolved rate |
|---|---:|---:|---:|---:|
| A: normalized text-difference baseline | 24/24 = 100% | 24/45 = 53.33% | 16/24 = 66.67% | 7/60 = 11.67% |
| B: deterministic policy engine | 22/24 = 91.67% | 22/22 = 100% | 0/24 = 0% | 16/60 = 26.67% |
| D: basic LLM and C: policy + real semantic provider | Skipped in the local report | — | — | — |

Both measured paths have zero unsafe passes **on this set**. B escalates C22 and
C23 to review instead of calling them critical; both count as recall misses.
Their dangerous meaning falls outside the explicitly declared templates. All 12
ambiguous cases remain review-required. B passes 22/24 acceptable cases; A18 and
A23 now require human review because they are raw ASR, despite high supplied
confidence. Labels were not changed to improve measured results. Acceptable
escalation is 2/24 = 8.33%; confirmed false-alert rate remains 0%.

Path A has only normalization and the same completeness/evidence-quality gate;
it treats any text difference as critical and ignores policy variants, unit
conversions, and protected ordering. It is a deliberately simple comparator,
not a production review endpoint or an LLM baseline.

Generated `reports/evaluation.json` and `reports/evaluation.md` include exact
counts, metric definitions, per-category error counts, and **all** decision
mismatches with original/observed text. JSON also includes every B finding,
dataset/code SHA-256 fingerprints, and runtime versions. No generated timestamps,
durations, or random seeds affect local report bytes. Re-running with the same
source, fixtures, and Python/dependencies produces the same bytes.

The original Phase 2A smoke call is recorded separately in
`reports/amd_smoke.json`. It used the existing `examples/critical.json` and one
HTTP attempt. The returned model alias was `self-dploy/DeepSeek-V4-Flash`; its
measured provider latency was about 21.84 seconds. The model explanation noted
the off→on reversal. Its detailed citation failed local reference validation,
so the semantic verdict became `UNRESOLVED` with an issue linked to
`power-state`. The deterministic engine still returned `CRITICAL_DEVIATION`.
This is one real inference observation, not a benchmark or proof of semantic
accuracy. The provider did not retain the rejected raw citation in the report.
The citation protocol now asks AMD for IDs and exact quotes, calculates offsets
locally, and rejects repeated ambiguous substrings. A Phase 2A.1 live call on
the same critical example is in `reports/amd_smoke_phase2.json`: one attempt
timed out at 40.8 seconds, so there is no new model finding or citation-validity
result. The deterministic decision remained `CRITICAL_DEVIATION`.

Recall counts every critical→review decision as a miss. Precision treats a critical
alert on either acceptable or unresolved labels as a false positive. False-alert
rate means acceptable→critical / acceptable; the report separately includes the
broader acceptable escalation rate (critical **or** review). Unresolved rate counts
`REVIEW_REQUIRED` decisions, not unresolved findings inside critical decisions.
Zero-denominator ratios are `null`, never an invented perfect score.

## Semantic and AMD integration

`SemanticProvider` is a pluggable interface. When selected, the AMD provider
loads `.env` from the current working directory without overriding exported
environment variables. `.env` is Git-ignored; the API key is sent only in the
Bearer header and is never included in the model prompt or returned result.
`.env.example` lists the verified base URL and model with a blank key. Exported
values can override the endpoint, model, timeout, and retry cap. The provider
accepts either the base URL or a full `/chat/completions` URL and requires HTTPS.
Without a configured provider, local deterministic verification remains available.

```bash
DUBGUARD_SEMANTIC_PROVIDER=mock .venv/bin/python -m dubguard verify examples/acceptable.json --hybrid
DUBGUARD_SEMANTIC_PROVIDER=amd .venv/bin/python -m dubguard verify examples/acceptable.json --hybrid
DUBGUARD_SEMANTIC_PROVIDER=amd .venv/bin/python -m dubguard evaluate --hybrid --output reports-local
# Explicitly opt in to two real calls per selected case; this example selects five.
DUBGUARD_SEMANTIC_PROVIDER=amd .venv/bin/python -m dubguard evaluate --remote --max-cases 5 --output reports-amd-5
# Add a third, policy-prompted LLM comparator only with another explicit opt-in.
DUBGUARD_SEMANTIC_PROVIDER=amd .venv/bin/python -m dubguard evaluate --remote --policy-baseline --max-cases 5 --output reports-amd-policy-5
```

The mock is an exact-text stub, not semantic inference. Hybrid verification with
an unavailable/mock provider adds `SEMANTIC.UNAVAILABLE` and requires review
unless an independent critical finding already exists. Deterministic verification
remains available during remote failure.

The AMD call sends the script, policy, and transcript as source data and asks for
structured JSON. It includes source-derived full-span citation templates, but
asks the model to return IDs and exact quotes only. DubGuard derives character
offsets and rejects repeated substring citations. For each finding, local validation checks its requirement,
instruction, and segment IDs; exact quoted text; policy
type; and segment alignment. Timestamps come solely from transcript segments.
Fabricated or inconsistent citations are rejected and become unresolved review
issues. The response records actual model and call IDs, attempts, and measured
latency when available. Model findings are labeled as advisory. A model-declared
deviation requires human review; a model-declared equivalence cannot erase a
deterministic violation or uncertainty. Reviewers must listen to the source audio.

Transport defaults to a 40-second request timeout and at most two retries (three
attempts total) for timeout, transport error, HTTP 429, or common 5xx errors.
`Retry-After` waits are capped at two seconds. Non-retryable HTTP errors, malformed
JSON, and invalid evidence do not expose raw response bodies or credentials.

Remote evaluation is separate from normal verification. `--hybrid` alone never
calls AMD in `evaluate`. `--remote` requires `--max-cases`; it runs a basic LLM
comparison without reviewer policy and the policy-hybrid engine on the **same
explicit subset**. `--policy-baseline` adds a third, well-prompted LLM comparator
with the same reviewer policy but without DubGuard's source-citation validation.
Each selected case makes two or three model calls plus bounded retries.
The basic LLM path is diagnostic only and cannot approve a recording. Partial
failures suppress aggregate remote metrics. The local reports continue to use
only the reproducible baseline and policy engine; no full remote benchmark is run
automatically.

Recommended next phase: independently adjudicate held-out recorded narration,
measure acoustic and semantic errors, replace the in-process queue and shared
tokens for deployment, and run separately authorized capped remote evaluations.
Keep human audio review and final approval outside the model.

## Audio and human-review workflow

Install `requirements-audio.txt` for the bundled FFmpeg binary and the optional
CPU `faster-whisper` adapter. The default `tiny.en` model is about 78 MB and was
chosen for a local development smoke test, not industrial accuracy. Set
`DUBGUARD_WHISPER_MODEL` to a cached model name or local model path; automatic downloads are disabled.
WAV, MP3, WebM/Opus and MP4/AAC are accepted by signature and decoded to 16 kHz mono PCM. Uploads
default to 25 MB and 20 minutes, configurable within bounded limits via `.env`.
The original bytes are stored under a SHA-256 name in a private local directory;
every read checks the hash. The filesystem is not cryptographically immutable.
Working WAV files and chunks are temporary and cleaned after processing. Each
chunk has an owned core and overlap; timestamps are mapped to original audio.
`processed_seconds` covers the entire recording or processing fails. Untranscribed
regions are labeled digital silence, possible silence, or unexplained signal;
possible silence is not proof that speech was absent. ASR never provides a
calibrated confidence score here, so its segments remain uncertain and transcript
completeness stays `unknown` pending human review.

For a local reviewer account, set a **unique random token** (24+ characters) in
`DUBGUARD_REVIEW_TOKENS_JSON`, for example using an environment variable in your
private shell or ignored `.env`. Never put real tokens in Git. The JSON shape is
`{"reviewer-id":"random-secret-token"}`. The `/review/*` API uses Bearer tokens;
deterministic verification remains a public local development API; hybrid calls require reviewer authentication.
Configure `DUBGUARD_DATA_DIR` as a private writable path. In production, deploy
behind HTTPS and replace this MVP shared-secret identity layer with your identity
provider and durable job queue.

The review API sequence is:

1. `POST /review/policy-drafts` with an existing `{script,policy}` payload, or
   `?origin=ai` for an externally proposed draft. A reviewer may submit an edited
   version with `POST /review/policy-drafts/{id}/revise`, then explicitly call
   `POST /review/policy-drafts/{id}/approve`. Approval records the authenticated
   reviewer as the policy and variant approver; draft author strings are not trusted.
2. `POST /review/artifacts` as multipart form field `file` with a WAV, MP3, WebM/Opus or MP4/AAC recording, then
   `POST /review/workflows` with `policy_record_id` and `audio_record_id`.
3. `POST /review/workflows/{id}/transcribe` starts an in-process background job.
   Poll `GET /review/workflows/{id}` for the transcription and its coverage.
4. `POST /review/workflows/{id}/alignments/propose` gives tentative mappings.
   `POST /review/workflows/{id}/alignments/confirm` takes a map of segment IDs to
   instruction IDs and a reason. Confirmation does not clear ASR uncertainty.
   Tentative IDs can support suspected findings only.
5. `POST /review/workflows/{id}/verify` runs deterministic verification. Add
   `?mode=hybrid` to queue AMD semantic analysis. If a separate local model is
   installed, set `DUBGUARD_SECONDARY_WHISPER_MODEL` and call
   `POST /review/workflows/{id}/acoustic-recheck` to independently re-transcribe
   protected regions without supplying approved words.
6. Listen to the entire original audio, then `POST /review/workflows/{id}/transcript-evidence`
   with `expected_revision` from the workflow, `listened_to_original: true`, a
   reason, and a `transcript` with source `manual`, completeness and actual spoken
   segments. Enter the words heard, including errors; do not rewrite narration to
   match the script. Unclear speech stays uncertain. This creates an immutable
   correction linked to audio SHA-256, raw transcription and the preceding human
   evidence version. Re-run verification. Raw ASR and all corrections remain in
   authenticated workflow `record_history`.
7. `POST /review/workflows/{id}/findings/{index}/decision` records one of
   `ACCEPTED_AS_CORRECT`, `CORRECTION_REQUIRED`, `RERECORD_REQUIRED`, or
   `ESCALATED` with a reason and the exact `verification_record_id`. Acceptance
   applies only to SATISFIED findings. Confirmed violations and unresolved checks
   block approval; correct the evidence or re-record using a superseding workflow.
8. `POST /review/workflows/{id}/signoff` with `APPROVED` or `REJECTED` and a reason
   and `verification_record_id` records an explicit human decision bound to exact
   script/policy records and revisions, audio SHA-256, human evidence record and
   verification run. All findings must be SATISFIED and explicitly reviewed.
   A zero-findings run can go directly to this explicit signoff, but still needs
   human-verified complete evidence and complete processing coverage. Coverage
   alone never proves transcription accuracy. Input changes invalidate runs and
   prior finding decisions; concurrent/repeated signoffs cannot reuse readiness.
   Creating a
   new workflow with `supersedes` retains earlier history and marks old approvals
   superseded.

`GET /review/audit-events` returns bounded authenticated audit history, including
policy draft, revision, and approval actions. Recorded reviewer IDs come from
configured bearer-token identity, not an arbitrary request field.

SQLite audit events preserve previous decisions but are not tamper-proof. The
in-process FastAPI background tasks are not a durable production queue. A local
Whisper smoke test on a short synthesized English clip returned “Switch the power
off.” in 0.46 seconds after the model was cached; Whisper reported an end time
beyond the 1.217-second clip, which DubGuard clipped and labeled uncertain. This
test demonstrates invocation and timestamp safeguards, not ASR accuracy.

AMD's [MiMo-V2.6-Flash model documentation](https://amd-aim.github.io/radeon-cloud-docs/zh-cn/models/mimo-v2-6-flash/)
shows `input_audio` with base64 WAV data. `AMD_TOKEN_FACTORY_AUDIO_MODEL` is
separate from `AMD_TOKEN_FACTORY_MODEL`; the MiMo probe has a local 5 MB WAV cap
and no automatic calls. Its actual transcription quality, duration limits,
timestamps, latency, and suitability remain unverified because no MiMo audio
call was authorized or run. Audio-input support alone is not evidence of ASR quality.

`reports/phase2_sets.json` partitions the existing synthetic development cases
into semantic, numerical/logical, and uncertainty subsets. Acoustic confusion,
ASR accuracy, audio alignment, and reviewer-workload sets are explicitly marked
awaiting human-verified recorded audio or review sessions. No result is reported
for those sets, for MiMo, or for remote LLM comparators. The optional capped remote
evaluation remains available through the Phase 2A CLI; a full benchmark is never
started automatically.

For future **human-adjudicated recorded audio**, use
`examples/audio-evaluation.example.json` as a field template, replace every
placeholder with a real local recording, its SHA-256, spoken ground truth, label,
and complete approved policy, then run:

```bash
.venv/bin/python -m dubguard.audio_evaluation /absolute/path/to/manifest.json --model-path tiny.en --output reports/audio_evaluation.json
```

This command is explicitly opt-in, uses a locally cached Whisper model, checks
the recording hash, and never calls AMD. It reports primary ASR word errors,
protected-term errors, processing coverage, provisional alignment, deterministic
decisions, and separate development/held-out counts. Add
`--secondary-model-path /absolute/path/to/different/local/model` to run local
targeted acoustic rechecks. No recorded-audio manifest or quality result is
included in this repository, because no human-adjudicated recordings were supplied.

## CPU container

```bash
docker build -t dubguard:phase2 .
docker run --rm -p 127.0.0.1:8000:8000 dubguard:phase2
docker run --rm dubguard:phase2 python -m dubguard evaluate --output /tmp/reports
```

The image uses ordinary CPU Python and a non-root user. No GPU runtime, remote
model, or credential is required. Docker execution remains unverified in this
workspace because its daemon was not running; local Python and FastAPI tests run
independently of Docker.

## Code map and verification

- `src/dubguard/schemas.py`: public contracts and cross-policy validation.
- `src/dubguard/text.py`, `engine.py`: normalization, numeric grammar, deterministic
  policy rules, source evidence, and decision aggregation.
- `src/dubguard/providers.py`, `semantic_validation.py`: local/mock and real AMD
  providers, response parsing, and source-reference checks.
- `src/dubguard/audio.py`, `alignment.py`, `acoustic.py`, `amd_audio.py`:
  local ASR intake, tentative mapping, targeted disagreement checks, and optional
  MiMo audio probe.
- `src/dubguard/review.py`: authenticated SQLite review workflow and audit events.
- `src/dubguard/phase2_evaluation.py`, `audio_evaluation.py`: development subsets
  and opt-in human-adjudicated recorded-audio evaluation.
- `src/dubguard/evaluation.py`, `data/`: explicit fixtures, metrics, report export.
- `src/dubguard/api.py`, `cli.py`: FastAPI endpoints and local CLI.
- `tests/`: corpus behavior, source-backed evidence, grammar edge cases, policy
  validation, fallback/provenance, independent metric checks, API/CLI, and report
  byte reproducibility.
- `examples/`, `requirements*.txt`, `.env.example`, `Dockerfile`: runnable inputs
  and local setup; `IMPLEMENTATION_PLAN.md` records the initial inspection/plan.

No commit or push was performed in this Phase 2 run. Test output
may include one upstream Starlette/AnyIO deprecation warning; it does not fail
the suite.


## Phase 2C operation and validation

The SQLite migration adds evidence revisions and verification input snapshots;
it preserves legacy records and marks old approvals without bound evidence as
`LEGACY_UNVERIFIED`. Finalized workflows cannot be edited. A new recording or
policy uses a new workflow with `supersedes` to invalidate prior approvals while
retaining history. There is no critical-violation exception endpoint: actual
spoken deviations require correction/re-recording. Input mutations and job starts
invalidate current verification. Job results use revision checks; stale completion
cannot restore approval readiness. Approval validation and writes use one SQLite
write transaction. Authentication covers every `/review` action. Direct `/verify`
and CLI outputs remain advisory and cannot create human approvals.

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m uvicorn dubguard.api:app --host 127.0.0.1 --port 8000
.venv/bin/python -m dubguard evaluate --output reports
```

See [RECORDING_GUIDE.md](RECORDING_GUIDE.md) for six actual-speech recording tasks
and a deliberately incomplete manifest. No real human-audio metrics are claimed.
Regression tests use stub ASR and silent PCM to exercise the full review protocol.

AMD semantic generation now has `AMD_TOKEN_FACTORY_MAX_OUTPUT_TOKENS` (default
1024, range 64–4096), separate connect timeout (default 5 seconds), and read/write
timeout (existing default 40 seconds). Retries remain bounded at the existing
configured count; the smoke commands below force zero retries and semantic output
512 tokens. Connect/read/write/pool timeouts are distinguished without logging
credentials or exception bodies. Read timeout alone cannot distinguish server
queue/generation time from network delay. The prior 21.84-second success and
40.80-second generic failure are historical measurements, not new Phase 2C calls.

Prepare without making a request:

```sh
.venv/bin/python -m dubguard.smoke semantic examples/critical.json
.venv/bin/python -m dubguard.smoke audio /absolute/path/to/on-off.wav
```

Only after authorization, add `--execute --output reports/amd_semantic_phase2c.json`
or `--execute --output reports/amd_audio_phase2c.json` to the respective command.
Each permits at most one HTTP attempt. DeepSeek remains the configured semantic
model; MiMo remains separate. MiMo accepts a real PCM WAV up to 30 seconds / 5 MB
(local limits), with documented base64 `input_audio`; it does not supply validated
timestamps or ground truth. No remote benchmark or smoke call ran in Phase 2C.

Phase 3 implements the reviewer interface and versioned acoustic resolution.
A resolution requires listening attestation and exact current human transcript and
acoustic evidence IDs; it preserves the disagreement and never removes a
deterministic violation. Input changes invalidate resolution and verification.
Collect/adjudicate the six real recordings and authorize bounded remote probes
before making recognition-quality claims. Production still needs durable jobs,
stronger identity/roles and tamper-resistant audit storage.
