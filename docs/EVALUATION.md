# Evaluation and reproducibility

## Synthetic development set

[cases.json](../src/dubguard/data/cases.json) contains 60 separately specified
fixtures with IDs, explicit labels, rationales and transcripts: 24 acceptable,
24 critical and 12 unresolved cases across 17 categories. These are synthetic
development fixtures, not externally adjudicated industrial or held-out data.
Labels are not computed from engine output; fixture reviewer names are placeholders,
not authenticated approvals or industrial experts. [profiles.json](../src/dubguard/data/profiles.json)
supplies policies; [phase2_sets.json](../src/dubguard/data/phase2_sets.json) defines
the overlapping semantic, numeric/logical and uncertainty subsets.

Committed results: [full JSON](../reports/evaluation.json) and
[subset report](../reports/phase2_sets.json). The JSON retains all metrics,
per-category findings and fingerprints; `evaluate` regenerates a Markdown summary
in the selected output directory. The duplicate generated summary is not tracked.

| Path | Critical recall | Critical precision | Acceptable → critical | Review-required decisions |
|---|---:|---:|---:|---:|
| A: normalized text-difference baseline | 24/24 = 100% | 24/45 = 53.33% | 16/24 = 66.67% | 7/60 = 11.67% |
| B: deterministic policy engine | 22/24 = 91.67% | 22/22 = 100% | 0/24 = 0% | 16/60 = 26.67% |

Both have zero unsafe passes **on this set only**. B escalates critical semantic
challenges C22/C23 to review rather than confirming critical deviation; both count
as recall misses. All 12 ambiguous cases require review. B passes 22/24 acceptable
cases; A18/A23 require review because their raw ASR is provisional. Acceptable
escalation is therefore 2/24 = 8.33%, distinct from confirmed false-critical alerts.

Recall counts critical → review as a miss. Precision counts critical alerts on
acceptable or unresolved labels as false positives. False-alert rate uses only
acceptable → critical; acceptable escalation additionally includes review.
Unresolved rate counts `REVIEW_REQUIRED` decisions, not unresolved findings inside
critical decisions. Zero denominators produce `null`, not a perfect score.

A is a deliberately simple comparator with normalization and its original
completeness/evidence gate. It treats text differences as critical and ignores
policy variants, unit conversions and protected ordering. It is not an LLM
baseline or a production approval endpoint.

## Reproduce locally

Use the [pinned Python dependencies](../requirements.txt) and
[development dependencies](../requirements-dev.txt) from [setup](../README.md#run-locally).
Write fresh outputs to an ignored directory to preserve historical report bytes:

```bash
.venv/bin/python -m dubguard evaluate --output reports/local
.venv/bin/python -m dubguard.phase2_evaluation --output reports/local/phase2_sets.json
```

Windows uses `.venv/Scripts/python`. JSON retains code/dataset SHA-256 fingerprints,
runtime versions, metric definitions, all B findings, per-category errors and every
mismatch with source text. Local output has no varying timestamps, durations or
random seeds; the same source, fixtures and Python/dependencies reproduce bytes.
Different runtimes may change recorded runtime metadata. The committed report
identifies engine 0.4.0 / Python 3.11.9; all six recorded code hashes match historical
revision `2cc9ad7632e7d4ff0422162194e4f85788e251e7`. To reproduce those historical
bytes, use that revision in an isolated checkout with LF line endings, Python
3.11.9 and its pinned dependencies. This checkout runs engine 0.5.0. A cleanup
rerun under Python 3.12.7 reproduced every case decision, finding and metric after
excluding version/fingerprint metadata. Windows CRLF checkout bytes change the
raw code/dataset/subset hashes relative to Git's LF blobs; some code fingerprints
also changed between the historical and current revisions. The historical reports
remain unchanged; compare fingerprints against the exact source bytes/environment
that produced them rather than expecting the old JSON to match a new runtime.
Repeated runs in the same checkout are byte-stable. The regression suite also
checks deterministic report generation. `GET /evaluation/reports` reruns only
local A/B; neither it nor `evaluate --hybrid` starts remote inference.

Remote basic-LLM (D), policy-hybrid (C) and optional policy-prompted LLM comparison
are unmeasured in these reports. Explicit `--remote --max-cases N` is required;
`--policy-baseline` adds the third comparator. Each selected case consumes two or
three calls plus bounded retries. Partial failure suppresses remote aggregates.
Do not execute these options without separate authorization and a disclosed cap.
Mock responses never count as AMD evaluation results.

## Real AMD observations and provenance

All historical reports are retained unchanged, including failures:

| Evidence | Actual observation | Scope |
|---|---|---|
| [Early response](../reports/amd_smoke.json) | One attempt, 21,837.67 ms; returned model identified off/on but detailed citation was rejected; semantic verdict unresolved | Synthetic manual text, old citation protocol |
| [Later timeout](../reports/amd_smoke_phase2.json) | One attempt, 40,804.01 ms; no usable response | Generic old transport diagnostic cannot distinguish connect/read or prove generation latency |
| [Validated smoke](../reports/phase4/amd_smoke.json) | HTTP 200, one attempt/zero retries, 16,392.719 ms; 662 prompt + 143 completion = 805 tokens | One synthetic manual-text example from [critical.json](../examples/critical.json) |
| [Offline inspection](../reports/phase4/amd_smoke_inspection.json) | Input SHA-256, raw response reparsing, exact citations and hybrid replay checked with zero HTTP calls | Local critical decision preserved |

Validated returned model: `self-dploy/DeepSeek-V4-Flash`; call ID
`0f69ad3c1f7c428eb357124d75c0578c`. One polarity finding matched `power-state`,
instruction `power`, segment `s1`, approved `Switch the power off.` at [0,21) and
observed `Switch the power on.` at [0,20). Two valid source spans, zero issues,
no supplied/fabricated timestamps. Client-observed latency includes network/service
time; it is not isolated generation time. Deterministic `CRITICAL_DEVIATION` stayed
intact. This establishes protocol behavior for one example, not general semantic,
ASR or recorded-audio accuracy. No MiMo/ROCm/Quark execution is claimed.

[Repository audit](../reports/phase5/repository_audit.json) retains hashes of the
committed live reports. Smoke commands default to preparation only:

```bash
.venv/bin/python -m dubguard.smoke semantic examples/critical.json
.venv/bin/python -m dubguard.smoke audio /absolute/private/on-off.wav
```

`--execute` requires fresh explicit authorization. Each smoke is capped at one HTTP
attempt. Never overwrite historical evidence with a newly prepared or executed report.

## Audio and hardware evidence

[CPU smoke](../reports/phase4/cpu_smoke.json) records real CPU int8 Whisper on two
seconds of generated silence: 1.182 seconds ASR, 3.099 seconds full smoke, empty
transcript and `REVIEW_REQUIRED`. The pinned tiny.en model revision is
`0d3d19a32d3338f10357c0889762bd8d64bbdeba`, with 78,090,594 top-level cached bytes
and a recorded model.bin hash. The [container smoke](../reports/phase5/container_smoke.json)
records another real silence run (1.758 seconds), persistence, recovery and model
hash checks. Silence and synthetic microphone tests do not measure speech accuracy.

An earlier synthesized-speech invocation returned the expected sentence in 0.46
seconds; an out-of-clip timestamp was clipped and marked uncertain. This was an
invocation/safeguard check without an independently adjudicated speech corpus.
The PyAV 18.1.0 pin preserves faster-whisper 1.2.1's decoder API compatibility.

[Hardware diagnostics](../reports/phase4/hardware.json) identified integrated AMD
graphics and an NVIDIA laptop GPU, without a verified ROCm/PyTorch HIP runtime.
No AMD GPU benchmark or Quark processing was performed. CPU int8 is not Quark,
and hosted Token Factory access does not establish GPU utilization under our control.
`scripts/gpu_diagnostics.py` remains a read-only diagnostic, not a runtime backend.
Future hardware experiments require verified compatible hardware, controlled local
weights, identical audio hashes/model/decoding, separate load/processing timings,
memory/utilization samples and independently checked transcript errors. No validated
Quark-to-Whisper-to-CTranslate2 path was established; do not add execution claims.

Six original demo WAVs and their actual local ASR results are preserved in
ignored `recorded-evaluation/` and `demo/private/`; see [demo provenance](../demo/README.txt).
They are not independently adjudicated ground truth. No human-adjudicated WER,
protected-token speech accuracy or reviewer workload result is supplied. Follow
[the recording protocol](RECORDING_GUIDE.md).
Missing secondary recognition means **not measured**, not zero disagreement.

## Tests and browser captures

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend run test:e2e
.venv/bin/python -m pip check
npm --prefix frontend audit
git diff --check
```

The full suite includes public sample and custom reviews. To run only the sample:

```powershell
npm --prefix frontend run test:e2e -- tests/public.spec.ts
```

E2E requires installed desktop Google Chrome and free ports 8000/5173. It creates
temporary storage and generated credentials, runs the real API/UI, and stubs ASR,
secondary recognition and AMD HTTP in `tests/e2e_server.py`. Actual encoding,
decoding, SQLite, deterministic verification and sign-off protections are exercised.
No live AMD call is made. Unit tests mock microphone APIs. One upstream
Starlette TestClient deprecation warning has historically been non-failing.

Generate API contracts with `npm --prefix frontend run generate:api` after an API
change. Both `frontend/openapi.json` and `frontend/src/generated-api.ts` are
intentionally versioned build inputs, not disposable generated clutter.

The [historical test receipt](../reports/phase6/test_results.json) records 333
backend, 21 frontend, 9 private/reviewer, 1 separately run public and 1 container
browser tests passing. [Verification manifest](../reports/phase6/verification.json)
records that implementation session's file list/secret scan, not current Git or
deployment status. Its original screenshot inventory and XML command are historical;
the old implementation screenshots and XML are reproducible artifacts. Current
[labeled screenshots](../README.md#public-workflows) replace the four stale UI
captures; aggregate JSON receipts and all genuine inference reports are retained.
Earlier JSON receipts retain container build IDs, environment/model hashes,
restart tests and validation scope; their old public-unavailable status is historical.
The later [public GET audit](../reports/phase6/public-baseline/audit.json) establishes
reachability at its recorded instant. Cleanup HEAD checks of `/test` and `/login`
also returned HTTP 200 on 18 October 2026; neither observation identifies deployment
of the latest code or verifies API readiness/physical capture.

`frontend/tests/capture.ts` generates desktop/mobile screenshots under ignored
`reports/local/ux-refinement/` by default. Set `DUBGUARD_VISUAL_DIR` to another
ignored output directory and `DUBGUARD_VISUAL_STAGE` to `before` or `after`.
The `after` stage checks axe WCAG A/AA rules and horizontal overflow; these checks
are not a full accessibility certification. [README screenshots](../README.md#public-workflows)
retain two representative fixture captures in `docs/images/`. Tests also write
disposable traces/downloads under ignored `frontend/test-results/`.

The read-only `frontend/scripts/audit-public.mjs` writes new public GET/HEAD audit
outputs to ignored `reports/local/public-audit/`, preserving the historical audit.
It rejects mutating requests and submits no credentials. Running it contacts the
public site; it is not required for local tests and cannot establish deployed SHA.

For production-bundle Chrome, Compose validation, Caddy validation, real CPU smoke
and recovery testing use [the isolated container protocol](../DEPLOYMENT.md#local-container-validation).
The [public container receipt](../reports/phase6/container-public.json) covers local
admission/authentication, proxy spoof rejection, quotas and real silence ASR; it
does not establish public TLS, physical microphone behavior or realistic capacity.
