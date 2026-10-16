# DubGuard reviewer application

React, TypeScript and Vite; actual FastAPI data, with no production fixture-response switch.
Run commands below from the repository root. Python setup is in the root README.

## Development

1. Install Node.js 22.12+ and run `npm --prefix frontend ci`.
2. Install `requirements-audio.txt`. Supply a locally cached Whisper model or local model directory through `DUBGUARD_WHISPER_MODEL`. No automatic model download occurs.
3. In private environment configuration set `DUBGUARD_REVIEW_TOKENS_JSON` to a JSON object mapping reviewer IDs to unique random secrets of at least 24 characters. Set a private `DUBGUARD_DATA_DIR`. For Quick Test set a separate random `DUBGUARD_DEMO_ACCESS_CODE` (24+ characters). Do not commit secrets.
4. Start `.venv/bin/python -m uvicorn dubguard.api:app --host 127.0.0.1 --port 8000`.
5. In another terminal start `npm --prefix frontend run dev`.
6. Open http://127.0.0.1:5173/test or http://127.0.0.1:5173/login.

The API loads ignored .env configuration without overriding exported variables.
Vite proxies /api to port 8000. Reviewer and demo tokens are separate and held in
sessionStorage. Closing a tab ends browser token retention; server demo retention
is bounded independently. Reviewer artifacts remain private persistent review
records until managed by the operator.

## Routes and source structure

| Route | Screen |
|---|---|
| /test | Six demonstration fixtures, capture/upload, local analysis and evidence |
| /login | Reviewer bearer-token authentication |
| /review | Paginated workflow dashboard |
| /review/new | Approved policy selection and capture/upload; optional supersession |
| /review/:id | Audio, raw ASR, mapping, corrections, findings, acoustic resolution, signoff, history and export |
| /policies | Script/constraint/variant editor, draft revision and explicit policy approval |

src/api.ts uses generated-api.ts from the backend's actual OpenAPI document.
components/Audio.tsx owns capture, cleanup, upload and authenticated playback;
components/Evidence.tsx displays source-backed findings and timestamps.
pages contains workflow screens; main.tsx owns routes and session guards.
No simulated confidence or generated successful provider response appears in production.

## Audio compatibility

| Source | Supported container / codec | Validation status |
|---|---|---|
| Chrome MediaRecorder | WebM / Opus, selected via isTypeSupported | Actual browser encoder exercised on localhost with a synthetic microphone |
| Safari MediaRecorder | MP4 / AAC when advertised by isTypeSupported | Detection implemented; actual Safari microphone session not performed |
| Uploaded file | WAV, MP3, WebM / Opus, MP4 / AAC | Backend signature, MIME, stream and decode validation |

The browser requests permission only after Record narration, then waits for Start.
Stop creates a local preview; explicit submission is separate. Cancel/discard and
navigation release tracks, timers and object URLs. Unsupported formats, denial,
disconnect, duration and size failures have visible states.
WebM/MP4 require exactly one supported audio stream and no video. Original bytes
and SHA-256 are preserved. No WAV renaming is used. Timestamp links seek the
original recording with 0.25 seconds of preceding context.

## Quick Test limits and retention

Quick Test needs the operator's demo code and issues a distinct scoped session.
It never creates approved organizational policies or human approvals and never
calls AMD. Six scenarios are explicitly demonstration fixtures.
Limits: 10 MB, 60 seconds, three analyses/session, 30-minute session TTL,
20 active sessions, 30 admissions/hour, two concurrent demo jobs.
Only one current result and audio artifact is retained per session.
DELETE /quick/session explicitly deletes session data; expired sessions are
removed by requests and a 60-second lifespan cleanup loop.
When the service is stopped, physical cleanup waits until restart or:
`.venv/bin/python -m dubguard.quick`.
Restart marks interrupted jobs failed. In-flight work can finish before final
orphan cleanup; cancellation does not pretend to forcibly stop the decoder.
Run one API process: SQLite quota transactions are shared, but startup job recovery
and in-process tasks are not a distributed worker system.

## Validation

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run test:e2e
npm --prefix frontend run generate:api
```

E2E requires installed desktop Google Chrome and free ports 8000/5173.
Playwright creates temporary storage and random test-only credentials, starts the
actual API and Vite, and deletes its data afterward. tests/e2e_server.py stubs ASR
and secondary recognition only; actual recording, upload, decoding, database,
deterministic verification and approval routes run.
Synthetic microphone capture plus stub ASR does not measure recognition accuracy.
Unit tests mock microphone APIs. No live AMD call occurs in these suites.
Screenshots are written under frontend/test-results; selected delivery images are
in reports/phase3.

## Deployment boundary

`npm --prefix frontend run build` emits frontend/dist.
nginx.example.conf is an undeployed reverse-proxy/SPA fallback reference.
Use HTTPS termination, same-origin /api routing and private storage. Do not expose
Vite development hosting as production. Browser microphone use requires a secure
context (HTTPS or localhost). Before production replace shared tokens and
in-process jobs with identity/roles, durable workers and operational controls.
Existing semantic provider remains DeepSeek; MiMo remains a separate opt-in audio
probe. The UI offers explicit AMD semantic verification, not an automatic call.
Missing models, timeouts, invalid evidence and unresolved checks cannot approve
a recording. Human acceptance cannot override critical or unresolved findings.
