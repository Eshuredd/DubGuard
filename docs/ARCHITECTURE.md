# Architecture and evidence boundaries

[Setup](../README.md#run-locally), [operations](../DEPLOYMENT.md) and
[evaluation](EVALUATION.md) describe how to run and assess DubGuard.

## Components and data flow

| Component | Responsibility |
|---|---|
| `frontend/src/main.tsx`, `pages/` | Routes, session guards, Quick Test, dashboard, policies and reviewer workspace |
| `frontend/src/components/Audio.tsx`, `Evidence.tsx` | Explicit capture/upload, original download/playback, source spans and timestamp seeking |
| `frontend/src/api.ts`, `generated-api.ts` | Typed API client generated from committed `frontend/openapi.json` |
| `src/dubguard/api.py`, `cli.py` | FastAPI and local validation, verification and evaluation entry points |
| `schemas.py`, `text.py`, `engine.py` | Contracts, policy validation, numeric grammar and deterministic decisions |
| `audio.py`, `alignment.py`, `acoustic.py` | Bounded intake, CPU Whisper, provisional mapping and independent protected-term recheck |
| `providers.py`, `semantic_validation.py`, `amd_audio.py` | AMD text transport, strict citations and separate optional MiMo probe |
| `review.py` | Authenticated SQLite workflow, evidence versions, audit events and transactional sign-off |
| `quick.py`, `quick_admission.py`, `public_amd.py`, `workspace.py` | Scoped demo sessions, persistent quotas and admission before body parsing |
| `evaluation.py`, `phase2_evaluation.py`, `audio_evaluation.py`, `data/` | Corpus, subsets and opt-in recorded-audio evaluation |

Caddy serves the built SPA and routes `/api/*` to one private API process. Vite
supplies that proxy during development. SQLite/audio, model cache and certificate
state persist separately. Background jobs run in-process, not in a durable queue.

## Public sessions and private reviewers

Public navigation contains only `/test` (samples) and `/workspace` (custom
references). `/operator/login` and `/operator` are private reviewer entry points;
`/login` remains a compatibility route. Authenticated reviewers retain `/review`,
`/review/new`, `/review/:id` and `/policies`. Dashboard counts cover its loaded
25-record page, not a server-wide aggregate.

Public sessions use random 256-bit capabilities stored as digests. Capabilities
are isolated by sample/custom scope, expire after 30 minutes and cannot enumerate
other sessions. Public changes never write organizational approval records.
Shared limits include 20 active sessions, 30 global hourly admissions, three
analyses/session, 10 MB/60-second recordings, two processing jobs and two admitted
uploads (one per network client). Early admission bounds the body before multipart
parsing; HMAC client attempt accounting survives session deletion and restarts.

Custom references allow 12 instructions, 30 constraints and 12,000 characters
including alternatives. Visitor corrections allow 50 segments/12,000 characters;
notes allow 2,000 characters. Each temporary workspace allows 30 metadata changes
and retains up to 20 demo activity descriptions. Optimistic revisions reject
stale edits. Analysis admission rechecks the exact reference snapshot and version
inside its SQLite transaction. Changed references or recordings invalidate prior
acknowledgements. Corrections require a listening attestation and reason, validate
audio hashes and timestamp bounds, preserve raw ASR and rerun local rules.
Exported demo decisions carry no authenticated organizational authority.

Operator login exchanges an independent reviewer credential for an expiring
HttpOnly, SameSite=Strict cookie (Secure outside localhost); only its digest is
stored. Cookie mutations check origin. Logout, expiry and reviewer-configuration
rotation revoke it. The browser retains only a non-secret signed-in hint. Backend
authorization remains independent of that hint and of public session capabilities.

## Script, policy and deterministic verification

Scripts have IDs, revisions and ordered atomic instructions. Approved variants
record text, approver and reason. Policies have independent revisions and selected
constraints; see [profile fixtures](../src/dubguard/data/profiles.json).

- `numeric` protects every parsed quantity using approved text as expected values.
- `polarity` declares approved/reversed phrase pairs, such as off/on.
- `warning` protects omission and optionally explicit forbidden wordings.
- `sequence` protects presence and relative order of named instructions.

Validation rejects unknown references, duplicate IDs, conflicting numeric/polarity
variants, contradictory warning wordings and inconsistent sequences. Arbitrary
semantic contradictions still need human policy review. Submitted reviewer names
are metadata; production identities derive from authentication.

Normalization permits case/whitespace and terminal periods/exclamation marks;
question marks and numeric unit-token case remain significant. Signed decimals,
ranges and adjacent inclusive/exclusive bounds are supported. Exact rational
conversions cover time, temperature, pressure, length, mass, percentage, rpm,
voltage and current. Unknown units/counts require unchanged surrounding wording.
Spelled-out numbers, scientific notation, grouped thousands, mathematical bound
symbols, `between` ranges, arbitrary paraphrases and cross-instruction reasoning
are outside this grammar. Rounded near-equivalents do not silently pass.

Transcripts declare source (`manual`/`asr`), completeness (`complete`, `incomplete`,
`unknown`) and ordered segments. Reviewed `instruction_id` supplies alignment;
otherwise only unique exact/approved wording aligns automatically. One segment
per atomic instruction is supported. Duplicates, unknown mappings, extra text and
split/merged instructions need review. Fuzzy similarity never proves equivalence.
Optional times must be paired, finite, nonnegative, ordered and nonoverlapping.
Array order is narration order; times describe whole segments, not words.

Evidence uses exact substrings/character offsets. Omission has no invented observed
span or timestamp and requires confirmed complete evidence. Unknown coverage cannot
prove absence. Decision precedence is proven violation → `CRITICAL_DEVIATION`,
otherwise unresolved evidence → `REVIEW_REQUIRED`, otherwise `PASS_CANDIDATE`.
Rule IDs (`NUMERIC.CHANGED`, `POLARITY.REVERSED`, `WARNING.MISSING`,
`SEQUENCE.REVERSED`, `EVIDENCE.UNCERTAIN`) are distinct from policy constraint IDs.
CLI and public local `/verify` outputs cannot create human approvals.

## Audio, ASR and acoustic evidence

WAV, MP3, WebM/Opus and MP4/AAC intake checks signatures, claimed MIME, codec,
duration and decoding. Browser containers require one audio stream and no video.
Original bytes are saved by SHA-256 privately and checked on read; the filesystem
is not cryptographically immutable. FFmpeg derives mono 16-kHz PCM and temporary
chunks with owned cores/overlap. Processing must cover the whole file or fail.
Digital/possible silence and unexplained gaps remain distinct; processing coverage
does not prove recognition coverage.

Cached CPU faster-whisper supplies provisional uncertain segments with unknown
completeness. Raw ASR remains immutable and can produce `ASR.SUSPECTED.*` unresolved
candidates. Confidence, mapping confirmation and recognizer agreement do not verify
spoken words. Independent acoustic recheck requires a distinct cached model,
does not receive approved words and retains protected-term disagreements.

MediaRecorder negotiates WebM/Opus or MP4/AAC. Permission, start, stop, preview and
submission are explicit actions. Downloads preserve original bytes/MIME; save
before submitting because submission clears the preview. Discard/replacement and
navigation stop tracks and revoke object URLs. Playback seeks the original with
0.25 seconds of context. Chrome's encoder was exercised with a synthetic device;
physical Safari/iOS capture remains unverified.

## AMD Token Factory

DeepSeek-V4-Flash uses HTTPS OpenAI-compatible chat completions. Private `.env`
does not override exported values. Keys go only in the Bearer header, never the
prompt, browser or result. A base URL or full chat-completions URL is accepted.
Script/policy/transcript text is source data; the model returns IDs and exact
quotes. Local checks validate requirement/type, instruction/segment mapping and
unique exact substrings, then derive offsets. Timestamps come only from input
segments. Invalid/ambiguous citations become unresolved issues.

Local findings survive remote failure. Model deviation needs human review;
equivalence cannot remove deterministic violations or ASR uncertainty. The mock is
an exact-text interface stub. Unavailable/mock hybrid requests cannot clear review.

General defaults: 5-second connect timeout, 40-second operation timeout, 1,024
output tokens (64–4,096 configurable) and at most two retries for transport errors,
timeouts, 429 and common 5xx responses. Retry-After waits cap at two seconds.
Quick Test separately forces one attempt, zero retries and 1,024 output tokens.
Operation timeouts do not bound total wall time. Connect/read/write/pool failures
are distinguished without exposing raw error bodies or credentials; read timeout
cannot isolate server generation from network delay.

Public sample and custom AMD reviews require a temporary session capability and
fresh consent, without an access code. Server configuration and the emergency
switch gate availability. SQLite atomically reserves rolling global hourly/daily
and browser/network client budgets with the session attempt. Failed attempts
persist across session deletion and process restarts. Public calls force zero
retries, 1,024 output tokens and a conservative 32,768 input-token bound; excess
text is rejected before HTTP without truncating citations. Custom findings remain
bound to the analyzed reference version and raw provisional transcript. Reviewer
hybrid calls retain independent bearer authentication.
[Access limits/proxy trust](../DEPLOYMENT.md#configuration) are enforced server-side.

MiMo-V2.6-Flash is a separate optional audio-probe scaffold: base64 PCM WAV, local
30-second/5-MB cap, no executed quality/timestamp result and no UI invocation.
CPU int8 Whisper is not Quark; hosted inference establishes no local GPU/ROCm use.

## Human review and approval

All `/review/*` routes require configured reviewer bearer authentication. The API
sequence (see actual request bodies in the local `/docs` schema) is:

1. `POST /review/policy-drafts`, optional `/{id}/revise`, then `/{id}/approve`.
   Authenticated identity supplies policy/variant approval.
2. `POST /review/artifacts` (multipart `file`), then `/review/workflows` with
   `policy_record_id` and `audio_record_id`.
3. `/review/workflows/{id}/transcribe`; poll the workflow for job/evidence state.
4. `.../alignments/propose` and `.../alignments/confirm` with actual segment IDs,
   instruction IDs and reason. Mapping confirmation does not verify speech.
5. Listen to the whole original and `.../transcript-evidence` with
   `expected_revision`, `listened_to_original: true`, reason and actual manual
   transcript. Preserve errors/unclear text. Evidence binds audio hash, raw
   transcription, reviewer and prior correction. All versions remain in history.
6. `.../verify` or explicitly selected `?mode=hybrid`; optional
   `.../acoustic-recheck`. `.../acoustic-resolution` needs listening attestation
   and exact current acoustic/human evidence IDs and retains the disagreement.
7. `.../findings/{index}/decision` with reason/current `verification_record_id`:
   `ACCEPTED_AS_CORRECT`, `CORRECTION_REQUIRED`, `RERECORD_REQUIRED` or `ESCALATED`.
   Only satisfied findings may be accepted as correct.
8. Explicit `.../signoff` with `APPROVED`/`REJECTED`, reason/current run ID.
   Approval needs complete human evidence/processing and reviewed satisfied checks.
   Zero-findings runs retain these requirements; the server independently rechecks
   deterministic rules so an empty finding list cannot conceal violations.

Approvals bind immutable script/policy records/revisions, audio hash, human evidence
and verification snapshot. Changes/job starts invalidate runs and decisions;
stale/failed completions cannot restore readiness. Pending jobs block conflicting
edits. SQLite `BEGIN IMMEDIATE` serializes eligibility/finalization, preventing
repeated/concurrent reuse of readiness.

Actual spoken errors require a new recording and `supersedes` workflow. Correcting
ASR cannot repair speech. Finalized workflows are immutable; supersession retains
history and invalidates old approval. Legacy unbound approvals are labeled
`LEGACY_UNVERIFIED`; old snapshot-less runs must be rerun. Authenticated workflow
history/export and `/review/audit-events` retain decisions, but SQLite is not
tamper-proof and human attestation does not prove listener truthfulness.
Quick Test cannot approve policies or recordings.

## Frontend presentation

`frontend/src/studio.css` is the single application stylesheet. The navy sidebar,
teal controls, responsive mobile menu, reduced-motion rules and keyboard focus
styles share one design system. Original-audio waveforms are decoded from actual
source samples, with native playback fallback. Text comparisons highlight wording
differences; those highlights are not policy verdicts or model confidence.
Local deterministic and AMD advisory findings remain separately inspectable,
including rejected-citation explanations and original source references.
