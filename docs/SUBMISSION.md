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
- Screenshots linked in the [README](../README.md#guides-and-evidence) use
  synthetic audio, stub ASR and mocked AMD where shown. They demonstrate UI only.
- Intended users are training-content reviewers, technical writers and narration
  producers. No customers, adoption, industrial validation or certification claimed.

## Demonstration script — 2 minutes 45 seconds
Use actual Chrome/physical-microphone footage only after the manual checklist.
Hide codes/tokens and private audio. Prerecord slow transitions if necessary and
label prerecorded footage. No additional live AMD request is authorized by repository cleanup.

| Time | Screen/action | Spoken narrative |
|---|---|---|
| 0:00–0:20 | Title and target user | “Industrial narration can change meaning with a single word: off becomes on, or 15 becomes 50. DubGuard helps training-content teams and human reviewers inspect those changes against their approved instructions.” |
| 0:20–0:35 | Quick Test / On versus off; approved text and protected requirement | “This is a demonstration script: Switch the power off. Its policy explicitly protects the power state. Local Verification is the default.” |
| 0:35–1:00 | Physical microphone permission, start, say “Switch the power on,” stop and preview | “Recording and submission are separate. I can preview the original audio before asking DubGuard to analyze it.” |
| 1:00–1:25 | Analyze locally, play original, inspect actual recognized words/timestamps/candidates | “Whisper runs on CPU. These recognized words are provisional. Here is the actual result and its source span.” If no candidate is returned, say so and show the real state; never assert an unreturned violation. |
| 1:25–1:45 | Select AMD Semantic Review, show unchecked consent and requested model; do not submit | “AMD review is an explicit opt-in. It sends script, policy and transcript text to AMD Token Factory using DeepSeek-V4-Flash. Original audio is not sent to DeepSeek. Another live request needs separate authorization.” |
| 1:45–2:10 | Open committed Phase 4 response/inspection, clearly titled HISTORICAL TEXT SMOKE | “This is a previously authorized manual-text smoke, not this microphone recording. The actual response took 16.393 seconds, used 805 tokens, and cited the off/on reversal with two exact valid source spans. The deterministic critical decision stayed intact. This is one example, not an accuracy benchmark.” |
| 2:10–2:35 | Full Review, actual saved human evidence and blocked approval for wrong speech | “A reviewer listens to the original and records what was actually said. AMD advice cannot approve narration. A confirmed wrong power state blocks sign-off and needs a new recording; correcting ASR cannot repair spoken instructions.” |
| 2:35–2:45 | Audit/export and closing frame | “DubGuard combines explicit constraints, AMD advisory inference and inspectable evidence while keeping the final decision with a human. The public installation has historical reachability evidence; independently adjudicated speech accuracy remains unmeasured.” |

If a correct replacement clip has actually completed the full workflow, a short
prerecorded segment can show explicit sign-off bound to its current evidence/run.
Label it prerecorded and use only an actual permitted approval. Otherwise show
the blocked approval and explain the prerequisites; do not manufacture a success.

For a future explicitly authorized live AMD recording segment, replace the historical
portion with that actual call's status and evidence. Label waiting/prerecorded
transitions, preserve failures, and update reported measurements from its saved
result. Do not mix mocked test responses into live footage. Only Token Factory /
DeepSeek is an executed AMD contribution here; no ROCm/Quark/MiMo claims.

## Remaining submission and release checks

- Verify public HTTPS/browser behavior, API readiness and deployed SHA before
  presenting a live demo. Follow [upgrades/backups/rollback](../DEPLOYMENT.md),
  preserving the existing project, volumes, credentials and one-API constraint.
- Complete [physical microphone/independent-label checks](RECORDING_GUIDE.md),
  including failure states, exact original downloads, consent and privacy review.
- Use distinct AMD-demo and reviewer credentials. Public local reviews need no
  activation; pass proxy trust, anonymous audio rejection and quota checks before deployment.
- Supply the actual video link and dashboard assets; label historical, mocked
  and prerecorded content. Check final description lengths in the current form.
- Keep personal recordings/exports private unless consented/redacted. Do not claim
  model advice, raw ASR or pass candidates are release approval.
- Review changes and authorize commit/push, deployment, any new paid inference and
  dashboard submission separately. Cleanup itself performs none of those actions.

Known demo limits: English single speaker, limited numeric/language grammar,
provisional ASR/timestamps, one source-valid live semantic example, shared-token
identity, in-process jobs, operator-managed Full Review retention, unmeasured
realistic concurrent load and unverified physical Safari capture. See
[architecture](ARCHITECTURE.md) and [evaluation](EVALUATION.md) for the exact scope.
