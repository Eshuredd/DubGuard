# Submission package

## Submission title

DubGuard: Evidence-Backed Industrial Narration Review

## Short description

DubGuard compares industrial narration with approved instructions, combining local speech transcription, protected-rule checks and opt-in AMD semantic review, with source evidence and human-controlled sign-off.

## Long description

DubGuard helps industrial training-content teams review spoken instructions before release. Small narration changes can matter: power off can become power on, or a protected quantity can change. Reviewers define an approved script and explicit constraints for numbers, polarity, warnings and operation order. Users record or upload English single-speaker audio through a React application. FastAPI preserves the original audio, FFmpeg normalizes it, and local CPU Whisper produces timestamped provisional transcription. Deterministic checks flag supported deviations or uncertainty. An optional, explicitly consented AMD Semantic Review sends script, policy and transcript text to AMD Token Factory using DeepSeek-V4-Flash; original audio is not sent to DeepSeek. Returned findings are advisory and must cite exact source text and valid requirement, instruction and segment IDs. Unsupported evidence is rejected. One previously authorized manual-text AMD smoke returned valid off/on citations in 16.393 seconds using 805 tokens, with zero citation issues; this is one observed example, not an accuracy benchmark. A human listens to the source audio, saves versioned spoken-text evidence and reviews the current findings before any permitted sign-off. Critical or unresolved findings block approval. SQLite retains review history and audit exports. The project includes bounded Quick Test sessions and CPU-only deployment configuration. A public URL and independently adjudicated real-speech evaluation remain pending. DubGuard is a review aid, not safety certification or automatic release approval.

## Problem statement

Comparing industrial narration by eye alone can miss changes in a number, negation,
warning or protected sequence. ASR and model confidence cannot establish what was
spoken. Reviewers need original-audio access, explicit constraints and traceable
evidence, including an honest unresolved state when automated analysis cannot decide.

## Intended users

Industrial training-content reviewers, operations enablement teams, technical
writers and narration producers reviewing English single-speaker material.
These are target users; no customers, adoption or industrial validation are claimed.

## Product differentiators

- Reviewer-declared constraints and approved variants instead of text similarity as approval.
- Original audio, source-relative timestamps and exact citation checks supporting inspection.
- Local deterministic findings retained alongside separately labeled AMD advisory findings.
- Consent before remote text transfer, backend-only credentials and bounded demo quotas.
- Versioned human evidence, stale-run rejection and explicit human-only sign-off.

## Technical architecture

React/TypeScript/Vite provides recording, upload, policy and evidence screens.
Same-origin Caddy routes the SPA and FastAPI API. FFmpeg validates/normalizes audio;
faster-whisper/CTranslate2 runs Whisper tiny.en on CPU. Pydantic contracts and the
deterministic engine enforce declared requirements. Optional AMD Token Factory
chat completions pass through local source-citation validation. Private local audio
and SQLite retain evidence, review state and audit history. One API process owns
bounded in-process jobs and conservative restart recovery. A reviewer must verify
actual speech and the exact current run before an eligible recording can be signed off.

## Actual AMD technologies used

**AMD Token Factory with DeepSeek-V4-Flash** is the executed AMD integration.
Committed historical evidence: `reports/phase4/amd_smoke.json` and
`reports/phase4/amd_smoke_inspection.json`. Actual returned model:
`self-dploy/DeepSeek-V4-Flash`; one HTTP 200 attempt, zero retries, 662 prompt and
143 completion tokens, two exact valid citation spans, deterministic critical
decision preserved. Phase 5 makes no new AMD calls.

ROCm, AMD GPU acceleration, Quark and MiMo are not claimed as executed technologies.
CPU int8 Whisper is not Quark quantization. A hosted endpoint does not establish
direct control or measured utilization of its underlying GPU hardware.

## Repository

[Eshuredd/DubGuard](https://github.com/Eshuredd/DubGuard)

Latest main commit audited: `c8b688d77a7c8f34f74f1d5ab89e9d8d8564753a` (smoke test).
Phase 5 edits require separate review/commit/push approval.

## Deployment URL

**UNAVAILABLE — no verified public deployment.** Replace this statement only after
an authorized server/hostname has passed HTTPS, API readiness and physical microphone checks.
Localhost is not a public submission URL. See PHASE5_REPORT.md for actual local container results.

## Honest evaluation results

- Historical Phase 4 checks: 303 backend tests, 13 frontend tests and eight Chrome
  E2E tests passed. Phase 5 rerun counts and container outcomes are in PHASE5_REPORT.md.
- Historical AMD smoke: one synthetic manual-text example, 16.393-second client
  latency, 805 tokens and zero citation issues. It is not a speech or accuracy benchmark.
- Existing 60-case synthetic development evaluation reports 22/24 critical recall
  (91.67%), 22/22 alert precision, and 0/24 acceptable-to-critical false alerts for
  the deterministic path. Two critical cases escalate to review and count as recall
  misses. This is not independently adjudicated industrial ground truth.
- Automated browser recognition uses explicit stubs. Real CPU execution checks use
  generated silence. Neither substitutes for independently verified human recordings.
- WER, protected-token errors and real acoustic-disagreement metrics are unavailable
  until the user provides actual clips and independently listened-to ground truth.

## Known limitations

English single speaker; limited deterministic language/numeric grammar; provisional
ASR/timestamps; one live semantic example; shared-token demo authentication;
SQLite/in-process single-server jobs; operator-managed retention; no public HTTPS
or physical-microphone verification yet; no held-out real-speech accuracy result.
No automatic certification, release approval, GPU speedup or Quark processing.

## Final submission checklist

- [ ] Review the actual deadline, track eligibility and current dashboard requirements.
- [ ] Review Phase 5 changes and authorize commit/push separately.
- [ ] Supply cloud account/budget approval, authorized host and controlled DNS hostname.
- [ ] Deploy only after approval; verify public HTTPS, microphone access and readiness.
- [ ] Complete MICROPHONE_CHECKLIST.md with actual speech and independent ground truth.
- [ ] Generate private JSON/Markdown evaluation reports; publish only consented/redacted evidence.
- [ ] Record the 2–3 minute DEMO_SCRIPT.md, labeling historical, prerecorded and mocked material.
- [ ] Supply the final video link, public URL if required, repository link and permitted screenshots.
- [ ] Check description lengths and technology claims; submit through the dashboard only when authorized.
