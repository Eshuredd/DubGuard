# Phase 4 — AMD visibility and deployment readiness

Prepared 17 October 2026 from `2f4b0d7` (Reviewer workflow). The original Phase 4
work ended with local, uncommitted changes. They were subsequently committed and
pushed as `c8b688d77a7c8f34f74f1d5ab89e9d8d8564753a` (smoke test), verified against
fetched origin/main during Phase 5. After explicit authorization, exactly one
Phase 4 AMD semantic request was completed; no retries or remote benchmark followed.
No public deployment or dashboard submission occurred. The pasted countdown was
not independently checked. Results below are the historical Phase 4 measurements;
see PHASE5_REPORT.md for subsequent container execution and current release status.

## Implementation results

Quick Test now offers **Local Verification** (default, no remote inference) and
**AMD Semantic Review**. Each AMD analysis requires a new explicit text-transfer
consent; the backend rejects missing consent independently of the UI. The existing
DeepSeek-V4-Flash provider runs only after local transcription and deterministic
checks. It receives script, policy and provisional transcript text, never the
original audio or credentials in its payload. MiMo is not substituted.

Local findings are persisted before remote work and displayed separately from
AMD semantic findings. The UI displays requested/reported model, inference status,
call ID, latency, HTTP attempts and classified failures. The existing exact-quote,
source-ID and backend-offset validator rejects unsupported citations. ASR remains
uncertain, source-relative timestamps remain provisional, and even equivalence
cannot establish spoken truth or approve a recording. No approval safeguards or
Phase 3 final-decision rules were weakened.

Quick Test keeps three total analyses/session and adds two AMD runs/session,
including failed attempts. It allows two simultaneous demo jobs and one demo AMD
call, with runtime slots retained across session deletion. SQLite reservations
are transactional. Each Quick Test call has zero retries, at most one HTTP attempt,
1024 output tokens and 40-second read/write timeouts. These are operation timeouts,
not a guaranteed total wall-clock deadline. The existing 20-session/30-admissions
per hour and 30-minute TTL limits remain. Consent/mode/local results and spent
quotas survive interruption reporting. Deleted/expired sessions cannot be resurrected.

Added single-process startup recovery for Full Review transcription, verification
and acoustic jobs: interrupted jobs become failed, invalidate their verification
reference and gain an audit event. No job is automatically replayed or approved.
This is conservative restart handling, not durable/distributed worker execution.

## Actual AMD readiness

Historical evidence was inspected: `reports/amd_smoke.json` has one real response
at 21.84 seconds whose detailed citation was invalid, and
`reports/amd_smoke_phase2.json` has one timeout at 40.8 seconds. The newly authorized
Phase 4 request succeeded as detailed below. Unit/browser results use explicitly
mocked HTTP; this single live text example is not a semantic accuracy benchmark.

### Authorized single live smoke result

The user authorized exactly one request using `examples/critical.json`. Executed
the existing smoke command once, with DeepSeek-V4-Flash, zero retries, a 1024-token
output cap and a 40-second read/write timeout. Saved the returned evidence to
`reports/phase4/amd_smoke.json`. No additional AMD request was made.

| Measurement | Observed result |
|---|---|
| HTTP/inference | HTTP 200; real response; finish_reason `stop`; semantic `DEVIATION` |
| Actual reported model | `self-dploy/DeepSeek-V4-Flash` |
| Call ID | `0f69ad3c1f7c428eb357124d75c0578c` |
| Attempts / retries | 1 / 0 |
| Client-observed latency | 16,392.719 ms (16.393 seconds), not isolated server generation time |
| Token usage | 662 prompt + 143 completion = 805 total |
| Citation validation | One valid finding, two valid source spans; zero issues |
| Requirement/type/instruction | Existing `power-state` / `polarity` matched model `POLARITY` and instruction `power` |
| Approved quote | `Switch the power off.`; exact unique source substring, offsets [0, 21) |
| Observed quote | `Switch the power on.`; exact unique substring in mapped segment `s1`, offsets [0, 20) |
| Timestamps | None supplied or fabricated; this is manually supplied synthetic text |
| Deterministic decision | `CRITICAL_DEVIATION`, preserved with all deterministic findings |
| Timeout / error | None |

Independently reparsed the saved raw model content using the current citation
validator, checked its input hash, requirement/source mapping and exact source
slices, and replayed the recorded assessment through the hybrid engine locally.
The replay made zero HTTP calls and preserved the local critical decision.
Full local inspection results are in `reports/phase4/amd_smoke_inspection.json`.
This validates the protocol on this one example, not ASR accuracy, general semantic
reliability or a live Quick Test recording. This authorization is consumed; any
future remote request needs fresh authorization.

Afterward reran the relevant local suites (`test_amd_http`, `test_providers`,
`test_phase4`, `test_engine`, `test_phase2c`): **211 passed in 12.81 seconds**, with
one upstream Starlette/AnyIO deprecation warning. Transport tests used mocked HTTP.

The existing smoke utility now uses the latest ID/exact-quote protocol and
per-instance caps. Its execution report retains input SHA-256, requested/reported
model, actual response envelope fields, validated assessment, citation status,
attempts, latency and classified error. Raw model output is untrusted evidence;
credentials, headers, endpoint and non-success error bodies are not stored.

Preparation was run successfully, producing `prepared_only` / zero HTTP calls:

```powershell
.venv/Scripts/python -m dubguard.smoke semantic examples/critical.json --output reports/phase4/amd_smoke.json
```

This command deliberately does not create a success report or execute inference.
The exact command executed once after explicit authorization was (do not rerun
without fresh authorization):

```powershell
.venv/Scripts/python -m dubguard.smoke semantic examples/critical.json --execute --output reports/phase4/amd_smoke.json
```

Execution is capped at one HTTP attempt and 1024 output tokens; it requires
`AMD_TOKEN_FACTORY_MODEL=DeepSeek-V4-Flash`. Timeout/failure is reported honestly;
`AMD_TOKEN_FACTORY_AUDIO_MODEL=MiMo-V2.6-Flash` remains separate. No MiMo probe was
run. A valid response with rejected citations still requires review; inspect
`citation_status`, not only the CLI exit code. The `.env` credential file was neither
read out, edited, nor included in Docker context.

## Deployment and real CPU execution

`DEPLOYMENT.md` gives exact operator commands and requirements for a public URL.
New Compose/Caddy files build and serve the React SPA over HTTPS, route `/api`
on the same origin, retain SQLite/audio/certificates/model volumes, and keep
credentials server-only. The CPU image installs FFmpeg/ffprobe/libgomp and audio
dependencies, runs non-root, and has a liveness health check. `/ready` separately
checks audio dependencies, FFmpeg and cached model files without inference.
Resource limits, read-only mounts, restricted build context, private configuration
generation, backup, shutdown and restart procedures are documented. The proposed
CPU host is an x86-64 Hetzner instance with at least 4 vCPUs / 8 GB RAM; no host
was purchased. See the linked provider source in DEPLOYMENT.md for current plans.

An actual local CPU smoke uncovered an upstream dependency break:
faster-whisper 1.2.1 called `av.open(metadata_errors=...)`, removed by PyAV 19.
Pinned **av==18.1.0**, then successfully ran real CPU int8 inference. This matches
the [upstream faster-whisper issue](https://github.com/SYSTRAN/faster-whisper/issues/1589)
and [PyAV changelog](https://pyav.basswood.io/docs/stable/development/changelog.html).
Added a real audio-decoder regression test so this boundary is no longer hidden
by ASR stubs.

Explicitly cached public `Systran/faster-whisper-tiny.en` revision
`0d3d19a32d3338f10357c0889762bd8d64bbdeba` in the ignored local model directory.
`reports/phase4/cpu_smoke.json` records actual generated-silence execution:

- Two seconds / 64,044 bytes PCM; all two seconds processed, digital silence gap.
- CPU int8 transcription processing: 1.182 seconds; full smoke wall time: 3.099 seconds.
- Empty recognized transcript, unknown completeness, `REVIEW_REQUIRED`.
- Cached top-level model files: 78,090,594 bytes; model.bin SHA-256 recorded.
- Zero AMD calls, no GPU, no Quark, no human speech or accuracy measurement.

With the explicit local model-path override, readiness returned true. No `.env`
change was made. Runtime still never downloads missing weights automatically.

During Phase 4 the Docker CLI was installed, but its Linux engine named pipe was missing. Compose
configuration validation passed using a temporary empty env file and fixture
hostname/revision, without rendering secrets. **Container build/run and deployed
HTTPS/microphone behavior are not verified. No public URL exists.**

## GPU / ROCm / Quark findings

Read-only `scripts/gpu_diagnostics.py` output is in
`reports/phase4/hardware.json`. Windows reports integrated AMD Radeon graphics
and an NVIDIA RTX 3060 Laptop GPU, but no ROCm utilities/version or PyTorch/HIP
runtime is available. No supported AMD GPU model execution was confirmed.
Stopped GPU experimentation as requested; no optional backend was added.

`GPU_FEASIBILITY.md` includes notebook diagnostics, compatibility references,
the CTranslate2 versus ROCm boundary, a proposed PyTorch Whisper investigation,
and a CPU/HIP benchmark protocol for a future confirmed notebook. Current Quark
documentation was inspected. No validated Quark path for the existing converted
Whisper runtime was established; hosted Token Factory weights cannot be quantized
by this application. No Quark packages, experiments, size/memory/latency/correctness
claims or submission-technology claims were added.

## Real-speech evaluation readiness

Inspected `RECORDING_GUIDE.md`, the six-case template and recorded-audio evaluator.
Added exact Windows/Linux import/preflight/evaluation commands and a no-inference
schema/hash checker. The incomplete supplied template is correctly rejected.
Original recordings and independently listened-to ground truth remain the user's
next inputs. No recordings, human labels or speech accuracy metrics were fabricated.
The evaluator will report WER, protected-term errors, processing time/coverage,
timestamp validity, candidate findings and applicable alignment/corrected-evidence
results, separated by development/held-out splits. Keep these private until reviewed.

## Measured verification

Environment: Windows 11, Python 3.12.7, Node 22.19.0, npm 10.9.3, desktop Chrome.
The existing Node installation is below several dependencies' declared support
range; checks passed but npm emitted engine warnings during installation.
Updated the project requirement to Node 22.22.2+ (22.x), 24.15+ (24.x), or 26+;
the web Docker build uses Node 22.22.2. That Linux build still needs execution.

| Check | Actual result |
|---|---|
| Backend `python -m pytest -q` | **303 passed**, 17.94 s; one upstream Starlette/AnyIO deprecation warning |
| Frontend Vitest | **13 passed**, two files |
| Typecheck | Passed (`npm --prefix frontend run typecheck`) |
| Production build | Passed; JS 311.57 kB / 95.87 kB gzip |
| Chrome Playwright | **8 passed**, 37.0 s |
| Accessibility | Existing Quick Test/review audits plus new AMD-results axe audit passed |
| Real CPU model execution | Passed after PyAV pin; generated silence only |
| Dependency consistency | `pip check` passed |
| npm install audit | Zero reported vulnerabilities at install time |
| Compose schema/config | Passed with fixture configuration and no real env values |
| Whitespace integrity | `git diff --check` passed |
| Container build/run, public TLS | Not executed: Docker engine unavailable |
| Phase 4 AMD / MiMo / ROCm / Quark calls | **1 / 0 / 0 / 0**; single semantic response validated |

New tests cover default-local isolation, server-side consent/authentication,
text-only payloads, quotas, concurrency, wrong semantic model, unavailable ASR,
timeouts/rate limits/malformed responses/unsupported citations, source-relative
evidence, preserved uncertainty, interrupted review/signoff integrity, retained
consent on restart, no-network smoke preparation, raw smoke evidence, readiness,
per-instance retry isolation and actual faster-whisper/PyAV decoding. Existing
human approval integrity tests remain passing. Chrome tests exercise consent,
mocked source validation, rejected citations, refreshed sessions and AMD quotas.

Screenshot: [AMD Quick Test — mocked HTTP and stub ASR only](reports/phase4/quick-amd-mocked.png).
It is evidence of UI behavior, not a live AMD result or real speech recognition.

## Submission actions and blockers

`SUBMISSION_READINESS.md` contains the concise application/AMD description,
seven-step demonstration walkthrough, honest limitations and missing artifacts.
The single authorized semantic smoke is complete, and Phase 4 was subsequently
committed/pushed at the SHA above. Next: collect/independently verify human clips;
supply server/domain/private configuration; validate Linux
containers, deploy only after approval, verify public HTTPS and microphone use,
then record the real demo and complete the dashboard's current required fields.
No GPU/Quark work should delay these P0 steps. Check the actual dashboard deadline.

Suggested commit after approval:
`feat(amd): expose semantic verification and prepare cloud deployment`.
