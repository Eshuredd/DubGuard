# Phase 6A — UI/UX redesign and bounded public demonstration

## Audit before implementation

Audited local starting revision `9e1c855d3a13667fd34a91da90da2d0e9d032254`.
The existing review and evidence engines remain the foundation. Phase 5 results
are historical validation, not results of this phase.

Priority findings:

1. The first screen explains the sandbox but hides the product and workflow behind
   a code gate. Navigation calls the professional workspace “Full Review”.
2. Scenario buttons disclose little until selected. Recording, verification mode
   and consent compete for attention. The original recording cannot be saved.
3. Results are a long flat panel. Provisional recognition needs a clearer next
   action, and selected versus analyzed scenarios need persistent distinction.
4. Reviewer tools expose the necessary controls but lack stage navigation and a
   clear explanation of approval prerequisites.
5. Existing demo bearer authentication protects session/audio/deletion, but there
   is no anonymous admission mode, persistent client accounting, early upload
   admission, or separate AMD demo credential. Removing the code field alone
   would be unsafe.

Implementation will retain server approval rules and exact citation validation,
add a disabled-by-default public local session mode, and protect AMD separately.
Browser captures use synthetic audio and explicitly mocked ASR/AMD; they do not
demonstrate human speech accuracy or a new live model response.

## Delivered design and interactions

- Compact product landing with the requested value proposition, an explicitly
  illustrative off/on comparison, three types of protected change, and direct
  Quick Test / Reviewer Workspace actions. No invented model output or statistics.
- Shared navy/blue design tokens, quieter surfaces, consistent headings, borders,
  focus states, warning/success states and responsive layouts. Existing components
  and review operations were improved; verification engines were not rebuilt.
- Scenario cards show approved wording, protected requirements, mistake type and
  selected state. A five-step navigation links directly to recording and analysis
  on narrow screens. The selected scenario does not rewrite prior analysis identity.
- Recording requests permission only on explicit interaction. Ready/start/stop,
  elapsed time, permission errors, upload alternative, preview, discard and exact-
  original download are visible. Analysis remains a separate explicit action.
- Completed analysis moves focus to actual evidence. Original playback precedes
  provisional recognized narration, processing coverage, approved text and
  findings. Source details expose instruction/segment IDs and character spans;
  timestamp controls seek original audio. Unverified ASR is never called a
  confirmed spoken error. AMD findings are a separate section with actual returned
  model identity, status, attempt count, latency, call provenance and citation
  failure explanation. Local findings survive AMD errors.
- Reviewer navigation explains independent authentication. The dashboard shows
  current/history filters, actual revision identities, record-stage progress and
  counts explicitly limited to the loaded page. No unqueried global metrics or
  fabricated finding totals are displayed.
- Eight review-stage links connect script, original audio, transcription/alignment,
  human evidence, verification, acoustic resolution, sign-off and audit/export.
  Missing stages say waiting/not run. Approval guidance explains human-evidence,
  critical-deviation, unresolved-evidence and check-review prerequisites. Finalized
  decisions direct the reviewer to a superseding review. Backend restrictions,
  revision binding, original evidence and history are unchanged.
- Policy preparation shows define → protect → save → explicitly approve. Drafts
  and unsaved edits do not become approved policy.

## Public local session architecture

`DUBGUARD_PUBLIC_LOCAL_DEMO=false` is the safe default. Existing private code
admission works when public mode is off. Public mode bypasses only the shared
session-creation code; it does not bypass authentication on session-specific APIs.

Every admitted session receives a fresh `secrets.token_urlsafe(32)` capability,
stored server-side only as SHA-256 and expiring after 1,800 seconds. Reading the
session, analyzing, retrieving audio and deleting all require its bearer token.
Capabilities never authenticate reviewer APIs or authorize AMD on their own.
The browser keeps the capability in tab session storage; it is not a URL parameter.

Persistent SQLite accounting stores an HMAC of the resolved client address, event
kind and event time. It never stores raw client IPs. Expired hourly events are
removed during admission and the periodic cleanup. The random HMAC secret persists
privately so restarts cannot reset the accounting. Deleting/expiring sessions
does not remove client events or hourly global admissions.

Defaults are four creation attempts and six authenticated upload attempts per
client per rolling hour. Failed code/admission attempts count; authenticated AMD
code guesses, decode failures and abandoned uploads consume upload admission.
Configuration has hard ceilings (30/90), and the accounting table has a 600-event
hourly global ceiling to bound cardinality. Repeated security query parameters
are rejected before parsing. HTTP 429 responses use generic messages and Retry-After.

The original 20 live sessions, 30 global hourly session admissions, three attempts
per session, 10 MB/60 seconds per audio and two processing jobs remain. A separate
runtime gate admits at most two upload bodies globally and one per client. Runtime
slots cannot be freed by deleting a database row. Single-process operation remains
required; these locks are not a distributed admission service.

An ASGI middleware validates the capability, charges client admission and validates
AMD authorization before multipart parsing. It checks declared and actual body
size, allows only 65,536 bytes of multipart overhead, and has a 30-second body
deadline. Caddy additionally limits Quick Test uploads to 10,065,536 request bytes,
session-creation bodies to 4,096 bytes and body-read time to 30 seconds. Reviewer
upload limits remain unchanged. The Uvicorn concurrency/backlog limits remain.

Forwarded IPs are ignored unless the direct peer belongs to an explicitly configured
trusted proxy address/network. The parser peels the chain from the right and stops
at the first untrusted address, validates IP syntax and bounds header length.
Caddy overwrites incoming X-Forwarded-For with its socket peer and removes Forwarded;
Uvicorn's automatic proxy rewriting is disabled. Compose gives Caddy and API
distinct fixed IPs. With no trust configuration, visitors conservatively share
the proxy's bucket; the operator must configure the verified Caddy `/32` before
enabling public access. Never expose API port 8000.

The SQLite migration is additive (new accounting tables/index only). Existing
session and review records retain their meaning. ReviewStore/sign-off code was
not modified. A consistent backup is required before deployment.

## AMD authorization boundary

Every AMD demo request additionally requires `X-AMD-Demo-Code`, validated against
`DUBGUARD_AMD_DEMO_ACCESS_CODE`, and a fresh explicit `consent=true`. The separate
secret must have at least 24 characters and differ from the private demo code,
all reviewer tokens and the provider key. Missing/malformed configuration or the
wrong model returns unavailable without constructing a transport or making a call.
Only DeepSeek-V4-Flash semantic configuration is accepted. Invalid codes are
rejected before body processing; changing URL parameters cannot upgrade a bearer.

The frontend keeps the AMD code only in React memory and sends it in a header,
never a URL, HTML bundle or storage. Consent resets after every request attempt
and when the mode, code, scenario or recording changes. Each request must opt in.
Public local mode never automatically selects or calls AMD. Authenticated reviewer
operations retain their existing independent authorization boundary.

The original two AMD runs/session, one concurrent AMD demo call, 40-second bounded
timeout, 1,024-token output cap and zero retries remain. Only approved script,
policy and provisional transcript text are passed; original audio is not sent.
Exact source citation validation and unresolved failure behavior are unchanged.
All AMD protocol tests use MockTransport, and screenshots say mock/no-real-AMD.
**Zero live AMD requests were made in this phase.** Historical Phase 4 evidence
is preserved without rerunning inference.

## Recording export

The download link reuses the exact object URL of the original `File` shown in the
preview. MediaRecorder chunks are assembled once into the completed Blob/File;
download performs no re-encoding or transcript reconstruction. MIME parameters are
retained on the file. WebM downloads end in `.webm`, MP4 in `.mp4`; uploaded WAV,
MP3 and M4A retain an appropriate format extension. Safe scenario-based names such
as `dubguard-fifteen-fifty-original.wav` remove path characters and avoid reserved
Windows names. Uploaded originals use the same mechanism.

Downloads require a user click and are available before analysis. No recording
bytes go into localStorage. Discard, replacement and unmount revoke object URLs
and stop recorder tracks. Successful submission clears the local preview; save
before analyzing. The UI explains that server audio expires after 30 minutes and
that downloaded recordings do not constitute ground-truth transcript annotations.
Approved scripts are never automatically used as ground truth.

Chrome E2E compared an actual fake-device MediaRecorder WebM download byte-for-byte
against the preview Blob. Public E2E compared an uploaded WAV download and server
original against the same input bytes. Those originals pass the existing ingest/
decode pipeline. The existing real WebM/MP4 codec regression tests still pass.
MP4 negotiation/export is additionally unit tested; physical Safari/iOS recording
has not been tested.

## Validation

| Executed check | Result |
|---|---|
| Full backend pytest | **333 passed**, one upstream Starlette deprecation warning |
| Frontend Vitest | **21 passed** (original 13 plus 8 recording/export cases) |
| TypeScript typecheck | Passed |
| Production frontend build | Passed locally and with Docker's Node 22.22.2 |
| Chrome private/reviewer E2E | **9 passed**, including keyboard-only scenario selection/navigation |
| Chrome public-mode E2E | **1 passed**, run separately with public mode enabled |
| Production-container Chrome | **1 passed**, actual Caddy/production SPA and real CPU ASR on synthetic silence |
| Accessibility | Zero axe WCAG 2 A/AA / 2.1 AA violations at captured desktop/mobile states; public flow also checked at 768px |
| Responsive overflow | Checked at 320px keyboard flow and 390/768/1440px public flow; captured desktop/mobile states also checked |
| Dependency checks | `pip check` host/container passed; npm audit found **0 vulnerabilities** |
| Docker | API/web built, Compose validated, actual stack started, Caddy config validated |
| Caddy-path public protocol | Passed: public creation, protected audio/delete, spoofed forwarded headers, 413, AMD unavailable before parsing, real local ASR, exact audio bytes, restart and deletion quota persistence |
| Credential artifact scan | Configured secret values absent from built frontend and Phase 6 reports; `.env` not edited |
| `git diff --check` | Passed |

No human speech accuracy metrics were generated. Synthetic silence and fixture
transcripts are test protocols, not evaluation ground truth. The container public
report is [container-public.json](reports/phase6/container-public.json); backend
results are [backend.xml](reports/phase6/backend.xml). The file/screenshot inventory
and credential-scan result are [verification.json](reports/phase6/verification.json).

Reproduce using the existing local environment:

```powershell
rtk proxy .venv/Scripts/python -m pytest -q
rtk proxy npm --prefix frontend test
rtk proxy npm --prefix frontend run typecheck
rtk proxy npm --prefix frontend run build
rtk proxy npm --prefix frontend run test:e2e -- --grep-invert "public local mode"
$env:DUBGUARD_E2E_PUBLIC="true"
rtk proxy npm --prefix frontend run test:e2e -- tests/public.spec.ts
Remove-Item Env:DUBGUARD_E2E_PUBLIC
rtk proxy npm --prefix frontend run test:container
```

The last command requires the local production stack and blank AMD key described
in DEPLOYMENT.md. `deploy/validate_public.py` is hardcoded to localhost and expects
an isolated public-mode test data directory, trusted local Caddy and blank AMD key;
never run it against production. Its private temporary capabilities stay under
ignored `.dubguard-data` and are removed after validation. Test containers are
stopped at the end, retaining named test volumes.

## Before/after visual evidence

Captured and inspected desktop (1440×1000) and mobile (390×844) screenshots.
Full-page images preserve all lower review controls. Overview contact sheets:
[before](reports/phase6/before-visual-index.jpg) /
[after](reports/phase6/after-visual-index.jpg).
The production baseline was also audited read-only: HTTP 200, no page errors,
existing “Hear what changed.” UI, no submitted credentials or mutations.
[Live baseline evidence](reports/phase6/public-baseline/audit.json).

| State | Before desktop / mobile | After desktop / mobile |
|---|---|---|
| Landing/private entry | [Desktop](reports/phase6/before/landing-desktop.png) / [Mobile](reports/phase6/before/landing-mobile.png) | [Desktop](reports/phase6/after/landing-desktop.png) / [Mobile](reports/phase6/after/landing-mobile.png) |
| Scenario selection | [Desktop](reports/phase6/before/scenarios-desktop.png) / [Mobile](reports/phase6/before/scenarios-mobile.png) | [Desktop](reports/phase6/after/scenarios-desktop.png) / [Mobile](reports/phase6/after/scenarios-mobile.png) |
| Microphone/fake device | [Desktop](reports/phase6/before/microphone-desktop.png) / [Mobile](reports/phase6/before/microphone-mobile.png) | [Desktop](reports/phase6/after/microphone-desktop.png) / [Mobile](reports/phase6/after/microphone-mobile.png) |
| Preview/download | [Desktop](reports/phase6/before/recording-preview-desktop.png) / [Mobile](reports/phase6/before/recording-preview-mobile.png) | [Desktop](reports/phase6/after/recording-preview-desktop.png) / [Mobile](reports/phase6/after/recording-preview-mobile.png) |
| Local evidence/stub ASR | [Desktop](reports/phase6/before/local-evidence-desktop.png) / [Mobile](reports/phase6/before/local-evidence-mobile.png) | [Desktop](reports/phase6/after/local-evidence-desktop.png) / [Mobile](reports/phase6/after/local-evidence-mobile.png) |
| AMD/mock only | [Desktop](reports/phase6/before/amd-mocked-desktop.png) / [Mobile](reports/phase6/before/amd-mocked-mobile.png) | [Desktop](reports/phase6/after/amd-mocked-desktop.png) / [Mobile](reports/phase6/after/amd-mocked-mobile.png) |
| Reviewer dashboard | [Desktop](reports/phase6/before/dashboard-desktop.png) / [Mobile](reports/phase6/before/dashboard-mobile.png) | [Desktop](reports/phase6/after/dashboard-desktop.png) / [Mobile](reports/phase6/after/dashboard-mobile.png) |
| Policy editor | [Desktop](reports/phase6/before/policy-editor-desktop.png) / [Mobile](reports/phase6/before/policy-editor-mobile.png) | [Desktop](reports/phase6/after/policy-editor-desktop.png) / [Mobile](reports/phase6/after/policy-editor-mobile.png) |
| Review/critical blocked | [Desktop](reports/phase6/before/critical-signoff-desktop.png) / [Mobile](reports/phase6/before/critical-signoff-mobile.png) | [Desktop](reports/phase6/after/critical-signoff-desktop.png) / [Mobile](reports/phase6/after/critical-signoff-mobile.png) |
| Explicit human approval/test | [Desktop](reports/phase6/before/approved-signoff-desktop.png) / [Mobile](reports/phase6/before/approved-signoff-mobile.png) | [Desktop](reports/phase6/after/approved-signoff-desktop.png) / [Mobile](reports/phase6/after/approved-signoff-mobile.png) |

Additional public-mode [landing](reports/phase6/after/public-landing-desktop.png)
and [local evidence](reports/phase6/after/public-local-evidence-mobile.png) show the
code-free local entry. [Production-container screenshot](reports/phase6/production-local.png)
uses actual CPU ASR on generated silence. All simulated sign-off screens are
protocol fixtures, not approvals of real human narration.

## Final prioritized audit and remaining limits

1. **Deployment gate:** no production update, commit or push has occurred. Public
   local access is implemented and validated locally, but remains off by default.
   The operator must approve an exact new release SHA, back up persistent data,
   verify the proxy network and test real local recording before enabling it.
2. **Physical-device coverage:** Chrome fake-device capture and exact bytes passed.
   Real microphones, OS permission UI, mobile Safari/MP4 recording and screen-reader
   behavior still require device testing. Automated axe results are not a WCAG
   conformance certification. Human speech quality and six real scenario recordings
   remain unmeasured.
3. **Shared-server capacity:** this is a bounded single-instance CPU demonstration.
   Shared NATs share limits; traffic across many addresses can exhaust global
   admission and honestly receive 429. Distributed DDoS protection and horizontal
   scaling are outside this change. No GPU/remote benchmark was run.
4. **Long professional reviews:** stage navigation and source details improve
   scanning, but the full evidence workspace remains a long page on mobile. This
   preserves all correction/sign-off controls. Future usability work could add
   stage-by-stage views after observing actual reviewers.
5. **Dashboard scope:** counts/history filtering cover only the loaded 25-record
   page. The UI labels that scope; a server-backed aggregate queue/finding count
   was deliberately not fabricated from unavailable summary fields.
6. **Visual fixes made after inspection:** hidden skip-link clipping, compact
   scenario cards, spaced policy breadcrumb, finalized-decision guidance and
   direct keyboard step links. No horizontal overflow or axe AA issues remain
   in the tested states. Current source citations and sign-off blocks remain real.

## Files and deployment handoff

Frontend: `main.tsx`, `style.css`, `api.ts`, QuickTest/ReviewPage/Dashboard/Policies,
Audio/Evidence components, recording tests, generated OpenAPI/types, Playwright
configuration, reviewer/public/capture tests and the production-container test.
Backend: `quick.py`, new `quick_admission.py`, API middleware registration and
`ui_contracts.py`; tests in Phase 3/4 were updated for the stronger boundary and
`test_phase6.py` adds the new security cases. No review engine/approval code changed.
Deployment/docs: `.env.example`, Dockerfile, Caddyfile, Compose IPAM/static service
addresses, new-install secret generator, local public validator, README,
DEPLOYMENT.md, this report and [PHASE6_DEPLOYMENT.md](PHASE6_DEPLOYMENT.md).
Local audit helpers and all visual/test evidence live under scripts/frontend scripts
and `reports/phase6`; `verification.json` lists exact paths.

Follow **[the existing-DigitalOcean update runbook](PHASE6_DEPLOYMENT.md)** after
explicit approval. It preserves the actual Compose project and named volumes,
backs up stopped-API SQLite/audio before migration, preserves Caddy certificates,
uses one API process, verifies HTTPS/routes/health/readiness/session policy, and
enables public access only after security/resource and real-recording checks.
Never use `down -v`. There is no new Git SHA until the user approves a commit;
deployment must pin that future exact reviewed revision, not this starting SHA.
