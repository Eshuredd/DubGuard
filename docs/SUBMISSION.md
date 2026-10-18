# Hackathon submission material

Prepared material for AMD Developer Hackathon Act III, Intelligent Industry.
Verify the current dashboard's deadline, eligibility, field lengths and required
assets before use; no deadline or dashboard submission is asserted here.

## Submission title

DubGuard: Evidence-Backed Industrial Narration Review

## Short description

DubGuard compares industrial narration with approved instructions, combining local speech transcription, protected-rule checks and opt-in AMD semantic review, with source evidence and human-controlled sign-off.

## Long description

DubGuard helps industrial training-content teams review spoken instructions before release. Small narration changes can matter: power off can become power on, or a protected quantity can change. Reviewers define an approved script and explicit constraints for numbers, polarity, warnings and operation order. Users record or upload English single-speaker audio through a React application. FastAPI preserves the original audio, FFmpeg normalizes it, and local CPU Whisper produces timestamped provisional transcription. Deterministic checks flag supported deviations or uncertainty. An optional, explicitly consented AMD Semantic Review sends script, policy and transcript text to AMD Token Factory using DeepSeek-V4-Flash; original audio is not sent to DeepSeek. Returned findings are advisory and must cite exact source text and valid requirement, instruction and segment IDs. Unsupported evidence is rejected. One previously authorized manual-text AMD smoke returned valid off/on citations in 16.393 seconds using 805 tokens, with zero citation issues; this is one observed example, not an accuracy benchmark. A human listens to the source audio, saves versioned spoken-text evidence and reviews the current findings before any permitted sign-off. Critical or unresolved findings block approval. SQLite retains review history and audit exports. The project includes bounded Quick Test sessions and CPU-only deployment configuration. A DigitalOcean installation has historical public reachability evidence; independently adjudicated real-speech evaluation remains pending. DubGuard is a review aid, not safety certification or automatic release approval.

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

## Repository, deployment and verified claims

- Repository: [Eshuredd/DubGuard](https://github.com/Eshuredd/DubGuard).
- Public installation: [Quick Test](https://134-209-145-248.sslip.io/test).
  [Audit](../reports/phase6/public-baseline/audit.json): HTTP 200 on 17 October 2026
  at 18:17 UTC. HEAD checks of `/test` and `/login` also returned HTTP 200 during
  cleanup on 18 October 2026. Deployed revision and API readiness remain unverified;
  latest source must not be assumed deployed.
- Executed AMD contribution: Token Factory / DeepSeek-V4-Flash. The
  [validated manual-text smoke](../reports/phase4/amd_smoke.json) and
  [inspection](../reports/phase4/amd_smoke_inspection.json) record one attempt,
  16.393 seconds, 805 tokens and two valid citation spans. This is one example,
  not semantic/audio accuracy. No ROCm, Quark, MiMo or AMD GPU execution claim.
- The [synthetic evaluation](EVALUATION.md) measures 22/24 critical recall,
  22/22 precision and 0/24 acceptable-to-critical alerts. Two critical examples
  escalate to review and count as misses. No external industrial ground truth,
  consenting recorded corpus, WER or real acoustic-quality result is supplied.
- Screenshots linked in the [README](../README.md#public-workflows) use
  synthetic audio, stub ASR and mocked AMD where shown. They demonstrate UI only.
- Intended users are training-content reviewers, technical writers and narration
  producers. No customers, adoption, industrial validation or certification claimed.

## Final submission assets and reproduction

The current video source is the 215-second Remotion composition in
`demo/remotion/src/`, with its timed narration, original audio playback and
historical AMD provenance. [Demo reproduction and licenses](../demo/README.txt)
describe the footage capture, narration, render commands and actual local ASR
results. That guide supersedes the earlier 2-minute-45-second demonstration plan.

Final video, pitch deck, PDF, cover image, captions and QA receipts live in ignored
`demo/output/`; original WAVs live in ignored `recorded-evaluation/`. Preserve
these local assets, private evidence, Remotion inputs and lockfile. They are not
disposable build caches. A fresh Git clone needs the separately preserved private
assets before reproducing the final video. Do not upload personal recordings or
credentials with repository source.

Before submission, inspect the actual output filenames, verify the final listen-
through and authenticated submission requirements, and distinguish real local
footage, historical AMD inference and illustrative motion graphics. Source
filenames and supplied scripts are never spoken ground truth. Current public
HTTPS behavior and deployed SHA must be verified separately before a live demo.
No new paid inference, commit, push, deployment or portal submission is authorized
by repository cleanup. Runtime, evaluation and security limitations remain in
[evaluation](EVALUATION.md), [recording](RECORDING_GUIDE.md) and
[operations](../DEPLOYMENT.md), rather than duplicated release checklists here.
