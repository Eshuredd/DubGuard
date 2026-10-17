# DubGuard submission readiness

DubGuard helps a human reviewer compare industrial narration with an approved
script and protected numbers, polarity, warnings and operation order. It preserves
original audio, timestamped provisional ASR, source-linked findings and versioned
human transcript evidence. A model opinion never releases a recording.

## Actual AMD technologies and evidence

- **AMD Token Factory / DeepSeek-V4-Flash:** real HTTPS integration. Visible in
  Quick Test's opt-in AMD Semantic Review and authenticated Full Review. Quick Test
  defaults to Local Verification, records explicit consent, sends text only, caps
  attempts and separates AMD evidence/status from local checks.
- **Historical real observations:** `reports/amd_smoke.json` records one actual
  response (~21.84 s, one attempt) whose detailed evidence was rejected. A later
  call in `reports/amd_smoke_phase2.json` timed out (~40.8 s). Neither establishes
  current citation reliability or a validated semantic demo result.
- **Phase 4 live AMD calls:** exactly one, explicitly authorized, zero retries.
  HTTP 200 from `self-dploy/DeepSeek-V4-Flash` in 16.393 s; 662 prompt / 143 completion
  tokens. Its polarity finding matched requirement `power-state`, instruction
  `power`, segment `s1`, and exact approved/observed text. Zero citation issues;
  the deterministic `CRITICAL_DEVIATION` decision was preserved in a local recorded
  replay. See `reports/phase4/amd_smoke.json` and `reports/phase4/amd_smoke_inspection.json`.
  This is one synthetic manual-text example, not a benchmark or a live recorded-audio
  Quick Test measurement. Browser/backend transport tests still use mocked HTTP.
- **MiMo-V2.6-Flash:** optional separate audio-probe scaffold, not executed or
  substituted for DeepSeek. No MiMo speech-quality result exists.
- **ROCm/GPU/Quark:** diagnostics and feasibility documentation only. No measured
  AMD GPU or Quark execution. Do not list them as implemented submission technologies.

## Deployment and remaining gates

Public URL: **not available or verified**. Secure single-server Docker/Compose/Caddy
files and exact operator commands are in `DEPLOYMENT.md`. Docker's Linux engine is
now available; Phase 5's actual local build/smoke outcomes are in `PHASE5_REPORT.md`.
Public TLS and physical microphone capture remain unverified. No cloud server was
purchased or deployed. Working domain/DNS, authorized server access and private
configuration are needed before those commands can yield a public URL. Phase 4
is already committed/pushed at `c8b688d77a7c8f34f74f1d5ab89e9d8d8564753a`.

Testing and dependency findings are recorded in `PHASE4_REPORT.md`. Local Whisper
weights can be explicitly cached; the CPU smoke uses generated silence and is
not human speech accuracy evidence. Physical microphone/Safari verification and
the six independently adjudicated recordings remain outstanding. Tests with stub
ASR do not establish speech recognition quality.

## Short demonstration walkthrough

1. Open `/test`, enter the operator's demo code and select **On versus off**.
   Show the approved demonstration text, “Switch the power off,” and its protected
   polarity. This fixture is not an organizationally approved production policy.
2. Choose **Local Verification**. Use **Record narration**, grant permission, start,
   speak “Switch the power on,” stop and preview. Do not operate equipment.
3. Click **Analyze recording**. Play original audio and show the actual recognized
   narration, source timestamps, coverage and raw-ASR uncertainty.
4. Show a local suspected polarity violation if ASR recognized the changed word.
   If recognition failed or missed it, show that actual result; never replace it
   with a scripted success. A provisional candidate is not a proven spoken error.
5. For another explicitly consented analysis, select **AMD Semantic Review**, read
   the disclosure, tick the consent checkbox, and submit the recording again.
   Explain that script/policy/transcript text goes to Token Factory; audio does not.
6. Show actual AMD status/model/call identity/latency and source-validated quotes.
   If citations are rejected or the call fails, show the unresolved state and the
   retained local findings. Only a successfully returned source-valid response may
   be presented as validated model evidence. Mocked Playwright screenshots must be
   labeled mocked and cannot stand in for this step.
7. Switch to `/login` using a separate reviewer token. In **Scripts & policies**,
   review and explicitly approve the intended policy. Create Full Review with the
   original clip; transcribe, listen, confirm mapping, enter actual spoken words
   as versioned human evidence, and run verification. A real on/off mistake remains
   critical and blocks approval: request a corrected recording and superseding
   workflow. For a separately correct recording, review every required satisfied
   check, then explicitly sign off only if the backend permits it. Show audit/export.

Quick Test never signs off. A finding correction describes what was actually heard;
it cannot turn a spoken error into an acceptable recording. Background jobs are a
single-process demo implementation and can fail during restarts.

## Missing submission artifacts / final actions

1. Verify the actual remaining deadline in the dashboard; the pasted “23 hours”
   was user-reported context, not a freshly checked deadline.
2. Completed: one authorized DeepSeek smoke with source-valid citations. Preserve
   that evidence; any further remote request requires new explicit authorization.
3. Phase 4 commit/push is complete. Review the separate Phase 5 changes before
   authorizing their commit/push; no Phase 5 commit has been made.
4. Provision the chosen CPU host/domain, populate server-only secrets privately,
   build/test the Linux containers, cache the model, deploy only after approval,
   and verify the resulting public URL and physical microphone flow.
5. Supply consenting human clips and independent ground truth; run the exact
   evaluation commands in `RECORDING_GUIDE.md`. Do not invent accuracy metrics.
6. Record the demo video using real results, capture consent/evidence/review screens,
   prepare the submission description and repository/public URL links, and check
   the hackathon's current required fields/assets. No dashboard submission was made.

Phase 5 provides `SUBMISSION_PACKAGE.md`, `DEMO_SCRIPT.md`,
`MICROPHONE_CHECKLIST.md` and `RELEASE_CHECKLIST.md` for these actions. A new live
AMD demonstration requires fresh authorization; the video script instead offers
the correctly labeled historical text response when no new request is authorized.
