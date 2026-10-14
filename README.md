# DubGuard — Industrial Narration Review

Phase 1 for AMD Developer Hackathon Act III, **Intelligent Industry**. A CPU-local,
text-first review engine compares an approved English industrial script with
single-speaker narration transcripts under reviewer-defined constraints.

**PASS_CANDIDATE is not safety certification, release approval, or a guarantee of
semantic equivalence.** Ambiguous evidence requires human review. No audio is
transcribed by this project, and no AMD-backed inference has been run.

## Run locally

Python 3.11+ is required; the delivered reports were generated with Python 3.11.9.
Run these commands from the project directory. Installation fetches ordinary
Python dependencies; execution needs no API key, network service, GPU, or model.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt -e .
.venv/bin/python -m pytest -q
.venv/bin/python -m dubguard validate examples/policy.json
.venv/bin/python -m dubguard verify examples/acceptable.json
.venv/bin/python -m dubguard verify examples/critical.json
.venv/bin/python -m dubguard verify examples/asr-segments.json
.venv/bin/python -m dubguard evaluate --output reports
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
verification. Invalid schemas return HTTP 422. `GET /evaluation/reports` reruns
only local paths A and B; GET never starts remote inference. This is a local
development service with no identity/authentication or approval workflow.

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
| AMD Token Factory provider | **Scaffold**, unavailable even when environment fields are set |
| Real semantic evaluation path C | Implemented runner; **skipped** without real inference provenance |
| Timestamped ASR segment input | Implemented contract; **no audio/ASR integration** |
| CPU Dockerfile | Provided; container build/run not verified because the local daemon is unavailable |

No frontend, multilingual dubbing, video editing, model training/downloads,
automatic certification, or automatic release approval is included.

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

ASR requires supplied confidence at or above the policy threshold. Missing/low
confidence, empty text, explicit unknown markers, or `uncertain=true` produce
`UNRESOLVED`, including when the remaining words look exact. Confidence is
unvalidated input metadata, not proof of transcription accuracy. Explicit complete
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
| B: deterministic policy engine | 22/24 = 91.67% | 22/22 = 100% | 0/24 = 0% | 14/60 = 23.33% |
| C: policy + real semantic provider | Skipped | — | — | — |

Both measured paths have zero unsafe passes **on this set**. B escalates C22 and
C23 to review instead of calling them critical; both count as recall misses.
Their dangerous meaning falls outside the explicitly declared templates. All 12
ambiguous cases remain review-required. All 24 acceptable cases pass B.

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

Recall counts every critical→review decision as a miss. Precision treats a critical
alert on either acceptable or unresolved labels as a false positive. False-alert
rate means acceptable→critical / acceptable; the report separately includes the
broader acceptable escalation rate (critical **or** review). Unresolved rate counts
`REVIEW_REQUIRED` decisions, not unresolved findings inside critical decisions.
Zero-denominator ratios are `null`, never an invented perfect score.

## Semantic and AMD integration

`SemanticProvider` is a pluggable interface. Provider configuration is read only
from environment variables; `.env.example` has empty AMD fields and no invented
endpoint or model. `.env` files are ignored by Git and Docker; they are not
automatically loaded. The default provider is `disabled`.

```bash
DUBGUARD_SEMANTIC_PROVIDER=mock .venv/bin/python -m dubguard verify examples/acceptable.json --hybrid
DUBGUARD_SEMANTIC_PROVIDER=amd .venv/bin/python -m dubguard verify examples/acceptable.json --hybrid
DUBGUARD_SEMANTIC_PROVIDER=amd .venv/bin/python -m dubguard evaluate --hybrid --output reports-amd-pending
```

The mock is an exact-text stub, not semantic inference. The AMD scaffold reports
missing configuration or an unimplemented transport, even if all environment
fields are populated. Neither makes a network call. Hybrid verification with an
unavailable/mock provider adds `SEMANTIC.UNAVAILABLE` and requires review unless
an independent critical finding already exists. Deterministic verification is
unaffected by remote unavailability.

A future real assessment must supply provider/model identity and a real call ID.
Malformed responses and provider exceptions preserve deterministic evidence,
return unavailable status, and do not expose exception text or secrets. Semantic
advice is deliberately advisory: it cannot erase deterministic violations or
unresolved evidence, and a provider-reported deviation requests review. Path C
is measured only when real inference is available and all cases have validated
real-call provenance; partial failures suppress aggregate hybrid metrics. Unit
tests use in-memory protocol fixtures, never exported as real measurements.

Once AMD Token Factory access is available:

1. Confirm the actual endpoint, supported model ID, authentication, request and
   response formats, limits, and data-handling expectations with AMD.
2. Implement the transport in `providers.py`, with finite timeouts, bounded
   retries, secret redaction, structured-output validation, and real call/model
   provenance. Preserve the unavailable fallback and conservative decision rules.
3. Design policy-aware prompts that treat transcript text as untrusted data and
   request source-grounded evidence. Validate returned spans against supplied
   scripts/transcripts; do not trust an LLM equivalence assertion by itself.
4. With authorization for any paid usage, run a genuine smoke call and then path C
   over the unchanged fixtures. Record actual calls and failures. Report accuracy,
   latency, or AMD claims only from those real measurements.
5. Have industrial reviewers adjudicate a separate held-out corpus, expand numeric
   and semantic challenge coverage, and decide whether any semantic findings can
   graduate beyond advisory review. Build an ASR adapter separately with tested
   timing/confidence calibration; do not confuse it with the current text API.

## CPU container

```bash
docker build -t dubguard:phase1 .
docker run --rm -p 127.0.0.1:8000:8000 dubguard:phase1
docker run --rm dubguard:phase1 python -m dubguard evaluate --output /tmp/reports
```

The image uses ordinary CPU Python and a non-root user. No GPU runtime, remote
model, or credential is required. Docker execution remains unverified in this
workspace because its daemon was not running; local Python and FastAPI tests run
independently of Docker.

## Code map and verification

- `src/dubguard/schemas.py`: public contracts and cross-policy validation.
- `src/dubguard/text.py`, `engine.py`: normalization, numeric grammar, deterministic
  policy rules, source evidence, and decision aggregation.
- `src/dubguard/providers.py`: disabled/mock providers and AMD integration TODOs.
- `src/dubguard/evaluation.py`, `data/`: explicit fixtures, metrics, report export.
- `src/dubguard/api.py`, `cli.py`: FastAPI endpoints and local CLI.
- `tests/`: corpus behavior, source-backed evidence, grammar edge cases, policy
  validation, fallback/provenance, independent metric checks, API/CLI, and report
  byte reproducibility.
- `examples/`, `requirements*.txt`, `.env.example`, `Dockerfile`: runnable inputs
  and local setup; `IMPLEMENTATION_PLAN.md` records the initial inspection/plan.

The initial workspace was empty and was not a Git repository. No code was
replaced, and no Git initialization, commit, or push was performed. Test output
may include one upstream Starlette/AnyIO deprecation warning; it does not fail
the suite.
