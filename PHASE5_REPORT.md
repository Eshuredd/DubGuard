# Phase 5 — Deployment validation and submission preparation

Prepared 17 October 2026. **Local container validation passed. Public deployment,
physical microphone testing and human-speech accuracy remain pending.** No new
AMD call, cloud purchase, public deployment, commit, push or dashboard submission
occurred in Phase 5.

## Repository audited

Fetched `origin/main` and verified both local `main` and fetched main at exactly
`c8b688d77a7c8f34f74f1d5ab89e9d8d8564753a` — smoke test; divergence 0/0. The working
tree was clean before edits. Phase 4 is committed and pushed, including both live
AMD reports. Corrected stale current-status statements while preserving historical
Phase 4 test counts, latency, token usage and the then-unavailable Docker engine.

`reports/phase5/repository_audit.json` records the audited SHA and SHA-256 of the
committed AMD evidence. A scan found no credential fields or configured secret
values in those reports. Their bytes and measured results remain unchanged.
The existing `.env` file was not edited or displayed. Phase 5 changes are uncommitted.

## Actual container execution

Existing tools were sufficient: Docker Desktop 4.47.0, Linux Docker Engine 28.4.0,
Compose 2.39.4 and running WSL2 distributions. No Windows/WSL service configuration
change, unsupported package installation or GPU setup was performed.

Built the actual backend, frontend and model-cache images. The first backend
build failed on a PyPI ONNX Runtime wheel download read timeout. Added a BuildKit
pip cache and bounded package-install timeout/retries (`120` seconds, two retries);
the subsequent build succeeded. These are **package installation** settings;
AMD transport quotas/retries were not changed. The frontend image builds with
Node 22.22.2 and serves the compiled SPA with Caddy.

Used disposable project `dubguard-phase5`, newly generated test credentials and a
blank AMD key. `compose.local.yaml` replaces public ports with only
`127.0.0.1:18080`, using Caddy's host-independent internal `:8080` listener.
No real `.env` values were copied into the test configuration or build context.
Model setup explicitly downloaded the pinned public tiny.en revision into a named
Docker volume and successfully loaded it on CPU. Runtime was offline/read-only.

| Executed check | Result |
|---|---|
| Compose configuration, without rendering secrets | Passed |
| Backend/frontend/cache-model builds | Passed after resolving the package-download timeout |
| Pinned model cache | `Systran/faster-whisper-tiny.en`, revision `0d3d19a32d3338f10357c0889762bd8d64bbdeba` |
| Runtime identity/configuration | UID 10001; blank AMD key; `HF_HUB_OFFLINE=1`; model mount rejects writes |
| `/api/health` and `/api/ready` | Passed through Caddy on the same origin |
| SPA deep links, JS asset and six scenarios | Passed |
| Microphone permissions header and CSP | Present; production Chrome check passed without page/console errors |
| Upload and actual CPU transcription | Passed on generated two-second silent PCM; full processing coverage |
| Quick Test default local analysis | Passed with real CPU ASR, zero AMD runs and `REVIEW_REQUIRED` |
| Approval integrity | Unresolved synthetic recording could not be signed off |
| SQLite/original-audio persistence | IDs, run reference and original-byte hash survived real stop/start |
| Container recreation | SQLite, quota state and original audio survived forced API recreation |
| Interrupted-job recovery | Explicitly seeded pending Full Review/Quick Test states became failed; verification reference invalidated, audit event retained and stale sign-off blocked |
| Runtime model downloads | ASR succeeded with explicit local model path, offline flag and read-only cache; all model hashes unchanged afterward |
| Container dependency check / Caddy validation | Passed |
| Teardown | Test containers/network stopped and removed with `down`; test volumes/images retained |

Evidence: `reports/phase5/container_build.json` records final image IDs/sizes;
`reports/phase5/container_smoke.json` records executed protocol outcomes, model
hashes, runtime configuration and real transcription metadata. The current
generated-silence CPU transcription took **1.758 seconds**, recognized no segments,
processed all two seconds and preserved unknown completeness/uncertainty. This is
execution evidence, not human speech recognition accuracy or a speedup benchmark.

Recovery coverage combines actual stop/start/recreation with **seeded** pending-job
states in the disposable DB. It does not claim an actual mid-inference crash or
durable queue execution. The memory sample after restart was 42.46 MiB / 4 GiB,
**not** peak ASR memory or a concurrent-load measurement. Container checks do not
establish public DNS, certificate issuance/renewal or a physical microphone result.

One production-container Chrome test separately executed the Caddy-served bundle,
private file upload, actual CPU ASR, mode reporting, refresh/delete and unchecked
AMD consent. It made no remote request. Screenshot:
[production localhost UI — generated silence](reports/phase5/production-local.png).
The separate [AMD UI screenshot](reports/phase5/quick-amd-mocked.png) uses explicitly
mocked HTTP and stub ASR and is labeled accordingly.

## Public deployment audit

A CPU-only x86-64 VPS around **4 vCPUs / 8 GB RAM / at least 80 GB disk** is a
reasonable controlled-demo starting point, not a measured capacity guarantee.
Tiny.en's cached files total about 78 MB, but Python, decoding, model execution,
concurrent jobs and Docker add memory/disk overhead. Existing limits remain API
3 cores/4 GB, web 1 core/256 MB, 512-MB temporary decode space, two ASR threads,
16 API request concurrency, two demo jobs and one demo AMD call. Full Review's
deployment config limits clips to 25 MB / 120 seconds; Quick Test is 10 MB / 60 seconds.
No realistic-speech load/peak-memory test has been performed.

DEPLOYMENT.md includes suitable CPU provider options and source links, exact
PowerShell/Linux container-validation commands and directly applicable server
commands once an authorized host/hostname exists. AMD Developer Cloud's public
documentation emphasizes GPU instances; an account-specific CPU Droplet is not
assumed available. A normal CPU VPS can host the app without renting a GPU.

Corrected a deployment instruction issue: the root-owned 0600 server env file
requires the privileged Compose function, not an ordinary user invocation that
cannot read it. Do not loosen its permissions. Production setup clears localhost
test overrides and uses separately generated private reviewer/demo credentials.
Same-origin HTTPS, DNS A/AAAA, ports, certificate volumes, model caching, backups,
disk/log retention, resource limits and restart constraints are documented. No
domain ownership, cloud account, server or billing approval is assumed.

**Public URL: unavailable.** Caddy certificate persistence is configured, but no
public certificate, DNS configuration or cloud deployment was exercised. An
operator must supply/authorize these inputs before the public URL can be verified.

## AMD interface and historical contribution

Both Quick Test modes remain intact. Added explicit **Analyzed mode** and
**Requested model / Returned model** labels so changing the selector cannot
mislabel the result being viewed. Existing consent, status, attempts/latency,
exact source quotes, separate local/advisory findings, rejected citations and
failure states remain visible; browser assertions cover the labels and safeguards.

The committed Phase 4 observation remains: HTTP 200, one attempt/zero retries,
returned `self-dploy/DeepSeek-V4-Flash`, 16.393-second client-observed latency,
662 prompt + 143 completion = 805 tokens, two exact validated off/on citation
spans and zero issues. Requirement/source mappings matched, and local replay
preserved `CRITICAL_DEVIATION`. This was synthetic **manual text**, not a newly
performed microphone analysis. Phase 5 makes **zero AMD calls**. No ROCm, Quark,
MiMo or AMD GPU execution is claimed. A future live AMD demo requires fresh authorization.

## Real speech and submission materials

Actual speech recordings and independent ground truth are still awaited. Added
MICROPHONE_CHECKLIST.md for Chrome physical capture, correct speech, on/off, 15/50,
before/after, approved paraphrase and unclear narration. It includes exact
PowerShell format/hash/manifest/evaluation/report commands and keeps listener
ground truth independent from prompts/ASR. Private files stay outside Git.

Added `inspect_audio.py` to validate signatures/decoding and metadata without ASR,
and `render_audio_report.py` to render existing evaluation JSON without inference.
Tests and `audio_tool_check.json` use generated silence/report fixtures only.
The incomplete six-case template was correctly rejected by preflight. No missing
recordings, labels, WER, token-error rates or acoustic results were fabricated.

Human-readable results separate ASR WER, declared protected-term mismatches,
secondary acoustic disagreement, raw-ASR decisions, optional human-corrected
decisions and processing/timestamp metadata. Missing secondary results remain
**Not measured**, not zero disagreement. Corrections cannot repair spoken errors.

SUBMISSION_PACKAGE.md contains all requested fields, a **210-character** short
description and **1,599-character** long description (measured locally), repository
link, explicit unavailable public URL, historical evaluation and limitations.
DEMO_SCRIPT.md is a practical **2:45** walkthrough: actual recording/local analysis,
explicit unchecked AMD opt-in, correctly labeled historical AMD text evidence and
human review safeguards. It does not trigger another paid request or pretend that
mocked/historical output belongs to the current microphone recording.

## Final validation

| Check | Measured result |
|---|---|
| Complete backend pytest | **305 passed** in 26.16 s; one upstream Starlette/AnyIO deprecation warning |
| Frontend Vitest | **13 passed**, two files; final rerun 4.41 s |
| TypeScript typecheck | Passed |
| Production frontend build | Passed locally and inside Node 22.22.2 image; JS 311.87 kB / 95.92 kB gzip |
| Existing Chrome workflow E2E | **8 passed**, 45.7 s; mocked AMD/stub recognition |
| Production Compose Chrome test | **1 passed**, final run 6.2 s; real CPU ASR on generated silence |
| Host and container `pip check` | Passed |
| Production npm audit | Zero reported vulnerabilities; image npm-ci audit also reported zero |
| Compose/config/build/model/runtime checks | Passed as detailed above |
| Caddy configuration validation | Valid; informational formatting warning only |
| Description character limits | Passed: short 210 <= 255; long 600 < 1,599 <= 2,000 |
| `git diff --check` | Passed |

The host still uses Node 22.19.0, below the declared dependency support range;
checks passed there, while the actual Linux production build used the declared
Node 22.22.2. Container pip check emitted a harmless non-writable cache warning
under the read-only non-root runtime. Neither warning changed test results.

## Files changed

- Dockerfile: bounded/cached dependency installation after observed build failure.
- deploy/compose.local.yaml and deploy/validate_local.py: isolated localhost
  override and real-ASR/persistence/recovery validation harness.
- frontend QuickTest.tsx/reviewer.spec.ts: explicit analyzed/requested/returned
  labels and assertions; package.json/vite.config.ts plus production-container
  Playwright config/test: separate production browser check.
- scripts/inspect_audio.py, scripts/render_audio_report.py, tests/test_phase5.py:
  format/report readiness and meaningful local regression coverage.
- PHASE4_REPORT.md, DEPLOYMENT.md, SUBMISSION_READINESS.md, README.md,
  frontend/README.md and RECORDING_GUIDE.md: corrected current status and reproducible instructions.
- New PHASE5_REPORT.md, RELEASE_CHECKLIST.md, SUBMISSION_PACKAGE.md,
  DEMO_SCRIPT.md and MICROPHONE_CHECKLIST.md: release/submission deliverables.
- reports/phase5/: repository/build/runtime/tool receipts and clearly labeled screenshots.

No backend approval rules, live evidence measurements, secrets or private recordings
were changed. No critical defect remains observed in the exercised local demo path;
this is not a full production security/capacity certification.

## Blockers and exact next user actions

1. Review the Phase 5 diff and authorize commit/push separately. Suggested message:
   `chore(release): validate deployment and prepare hackathon submission`.
2. Choose provider/region and approve billing, then supply an authorized CPU server
   and SSH access through a private mechanism. No server has been purchased.
3. Obtain/control a hostname, authorize its DNS/firewall configuration and explicitly
   authorize public deployment. Execute DEPLOYMENT.md using the reviewed release SHA.
4. Populate server-only secrets privately, verify the actual public HTTPS/API/model
   readiness and physical Chrome microphone flow, and set retention/backups/monitoring.
5. Supply consenting actual speech clips and independent listener ground truth;
   run MICROPHONE_CHECKLIST.md and generate private JSON/Markdown evaluation results.
6. Record the labeled demo, supply video/public-URL/repository assets, check the
   current dashboard deadline and required fields, and authorize final submission.

Public host/DNS/access, physical speech evidence and final dashboard artifacts
remain external blockers. Shared-token identity, in-process single-server jobs,
operator-managed Full Review retention and unmeasured realistic load remain known
demo limitations. Further AMD inference requires fresh explicit permission.
