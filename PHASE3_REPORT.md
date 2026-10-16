# Phase 3 delivery report

Implemented against Phase 2C commit 2cc9ad7. Changes remain uncommitted.
The existing deterministic engine, AMD provider abstractions and approval
integrity rules are preserved. No deployment, new AMD inference, model download,
commit or push occurred during Phase 3.

## Implementation and API integration

The React/TypeScript/Vite application uses actual generated FastAPI OpenAPI types.
Routes: /test, /login, /review, /review/new, /review/:id and /policies.
It includes private audio playback, timestamp seeking, polling, error/empty states,
session-scoped credentials, responsive layouts and explicit recording controls.

Full Review connects policy draft/revision/approval, artifact upload, workflow
creation, transcription, alignment proposal/confirmation, human transcript
evidence, deterministic or explicitly selected AMD verification, independent local
acoustic recheck, finding decisions, signoff, history, supersession and export.
Reviewers can request correction, request rerecording or escalate exact run-bound
findings. Confirmed mappings survive refresh. Raw ASR and prior revisions remain
available. No frontend-only approval state is invented.

Added authenticated workflow/policy listing and evidence export endpoints.
Added POST /review/workflows/{id}/acoustic-resolution, binding human listening
attestation to the exact current acoustic and corrected transcript evidence IDs.
It requires complete unambiguous mapped human evidence for affected requirements.
The disagreement remains in history; changed evidence invalidates the resolution.
It never suppresses a deterministic policy violation.

Added scoped /quick sessions, scenarios, analysis, status, private audio and
deletion endpoints. Demo fixtures are explicitly named as demonstrations.
Quick Test is local-only and provisional; unavailable ASR yields a visible failure.
It uses the same ingestion/transcription/verification implementation as review.
Its quotas, bounded retention and single-process limitation are documented in
frontend/README.md.

## Recording and evidence

MediaRecorder MIME detection selects supported WebM/Opus or MP4/AAC.
Permission, start, stop, preview and submit are separate user actions.
Cleanup covers cancellation, unmount, delayed permission responses, disconnect,
duration/size failures and discarded object URLs.

Backend ingestion now accepts WAV, MP3, WebM/Opus and MP4/AAC, checks claimed MIME
against container signatures, probes browser formats for one audio/no video,
validates codec and decodes with FFmpeg. Original bytes and SHA-256 are preserved.
Uploads run decoding outside the event loop. Whisper uses local_files_only,
preventing accidental first-use downloads.

Chrome browser recording passed using the real MediaRecorder encoder and a
synthetic browser microphone, followed by actual upload and decoding.
Safari-compatible MIME detection is implemented; Safari capture and physical
microphone use have not been manually validated. No recognition accuracy is
inferred from synthetic audio or stub recognizers.

## Files changed

- frontend/: routes, typed API client/generated schema, recorder/player, evidence
  displays, policy/review screens, responsive styles, unit and browser tests,
  lockfile, Vite/TypeScript configuration and undeployed nginx reference.
- src/dubguard/audio.py: browser container intake, codec/MIME checks, bounded decode,
  local-only model loading.
- src/dubguard/review.py: listings/export and versioned acoustic resolution.
- src/dubguard/quick.py, ui_contracts.py, data/demo_scenarios.json: bounded demo
  backend and actual OpenAPI response contracts.
- src/dubguard/api.py: router/lifespan integration, private-response headers and
  reviewer authentication for legacy hybrid calls.
- scripts/export_openapi.py: reproducible OpenAPI export.
- tests/test_phase3.py, tests/e2e_server.py, tests/test_api_cli_evaluation.py:
  new regression coverage and test-only recognition fixtures.
- pyproject.toml, __init__.py, schemas.py and evaluation.py: version 0.5.0.
- .env.example, .gitignore, README.md and frontend/README.md: configuration,
  generated/build exclusions, setup and accurate capability/retention notes.

## Measured validation

| Check | Result |
|---|---|
| Full Python pytest suite | 285 passed in 2.83 s; one upstream Starlette/AnyIO deprecation warning |
| Frontend Vitest | 13 passed across 2 files |
| TypeScript + Vite production build | Passed; JavaScript 309.41 kB (95.27 kB gzip) |
| Chrome Playwright | 7 passed in 15.8 s |
| Automated accessibility | Zero axe WCAG 2 A/AA and 2.1 AA violations on Quick Test and critical review workspace |
| Production npm dependency audit | Zero known vulnerabilities at audit time |
| Phase 3 real AMD calls | 0 |
| Real human speech accuracy measurement | Not performed |

Browser coverage includes real encoded synthetic capture, permission/unavailable
states, preview, Quick Test, refresh/delete, full policy approval/upload, mapping,
correction, critical blocking, acoustic disagreement/resolution, human signoff,
authentication/logout, stale-run rejection, navigation and mobile overflow.
Unit/backend tests cover unsupported formats, cancellation and resource cleanup,
upload limits, timestamped evidence, isolated demo tokens, expiry and restart.

## UI and approval integrity audit

Fixed contrast issues found by axe. Desktop and 390-pixel mobile screenshots were
captured. Unsaved transcript edits disable verification and signoff until saved
or discarded; saving invalidates the prior run. Quick Test results identify the
scenario actually analyzed even if the current selector changes.
PASS_CANDIDATE is explicitly labeled not approval. Critical and unresolved checks
cannot be accepted as correct. Signoff requires authenticated explicit action,
current evidence/run, complete reviewed evidence and all satisfied checks reviewed;
the backend independently enforces these conditions. Audit history is versioned,
not claimed to be tamper-proof.

Screenshots (test-only ASR and synthetic audio):
- [Quick Test](reports/phase3/quick-test.png)
- [Critical review workspace](reports/phase3/critical-review.png)
- [Mobile review](reports/phase3/mobile-review.png)

## Remaining limitations and next phase

Validate physical microphone capture on Chrome and Safari, then collect and
independently adjudicate consenting human recordings across the six scenarios.
Measure actual ASR/acoustic/semantic errors separately from UI correctness.
Authorize capped DeepSeek and MiMo probes explicitly before running them;
MiMo is not integrated as a browser review button and remains a separate probe.
Quick Test deliberately has no secondary acoustic inference.
Production requires identity/roles, durable worker recovery, managed retention,
monitoring, reverse-proxy HTTPS and stronger audit storage. Full Review retains
private audit artifacts and does not yet provide an operator retention UI.
No industrial safety certification or automatic release approval is claimed.

Exact setup, API, evaluation and test commands are in README.md and
frontend/README.md. Existing synthetic evaluation fixtures and labels were not
changed to improve scores.
