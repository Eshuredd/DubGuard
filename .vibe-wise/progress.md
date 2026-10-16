# Learning Progress

No learning events recorded yet. Phase 1 was implemented before learning mode;
its implementation and test results are not evidence of learner understanding.

Onboarding completed: the learner chose normal checkpoints, open-ended reasoning,
and AI-written code after agreeing the design.

## Phase 2A AMD integration design
- Learner proposed and explained a deterministic-first flow: validate requests;
  preserve policy findings; call AMD for structured semantic advice; validate each
  constraint, instruction, segment, quote, and character offset against source;
  reject fabricated/inconsistent findings and escalate uncertainty.
- Learner chose decision precedence: confirmed deterministic violation remains
  critical; suspected model deviation or ambiguity requires review; model
  equivalence never removes deterministic findings or independently approves.
- Learner wants model provenance and reviewable evidence, with a human reviewing
  the relevant audio before any final approval.
- Implementation scope authorized by the earlier Phase 2A build request: real AMD
  transport, strict validation, safe failure handling, mocked HTTP tests, one live
  example call, and opt-in three-path evaluation preparation. No frontend, ASR,
  automatic full benchmark, commit, or push.
- Inspection baseline: 200 tests passed; `.env` exists and is Git-ignored;
  only variable names were inspected, never credential values.
- Implemented real HTTPS chat-completions transport, bounded retries/timeouts,
  environment loading, strict JSON and source-span validation, source-linked
  advisory findings, and an opt-in capped basic-LLM/hybrid evaluation path.
- Added mocked HTTP and evaluation tests. Final local verification: 226 tests
  passed, `pip check` passed, and `git diff --check` passed.
- One live AMD example call completed in one HTTP attempt at 21.84 seconds.
  The actual model explanation identified the off/on reversal. Its cited finding
  failed local validation, so the semantic verdict was UNRESOLVED with a
  `power-state` issue; deterministic outcome remained CRITICAL_DEVIATION.
- The prompt was subsequently supplied exact full-span citation templates;
  this mitigation has mocked HTTP coverage but no second live call yet.
- No full remote evaluation, frontend, ASR, commit, or push was performed.

## Phase 2A.1 and 2B pending build checkpoint
- User requested source-backed semantic reliability, real audio transcription,
  acoustic disagreement review, conservative alignment, human approval workflow,
  and expanded evaluation in an attached Phase 2A.1 + 2B specification.
- Read-only inspection found the existing FastAPI/Pydantic text-first architecture,
  no installed audio toolchain in PATH, and a clean Git worktree. The existing
  virtualenv test suite passes: 226 tests.
- Pending learner design: how to divide the audio-to-review workflow into backend
  components and data handoffs, particularly source audio/timestamps, proposed
  alignment, and human-approved state. No implementation design confirmed yet.
- Learner proposed a modular FastAPI backend with three separated records:
  original audio evidence, versioned AI-generated analysis, and human-approved
  review state. They selected private local artifact storage plus SQLite for the
  MVP, source-audio-relative timestamps, provisional alignments, stable IDs across
  processing runs, background ASR/inference jobs, and explicit authenticated human
  signoff. They proposed separate finding-review and recording-approval workflows
  with superseded approvals retained in audit history.
- Proposed first implementation slice awaiting confirmation: improve AMD citation
  contract to model-selected IDs and exact quotes with backend-derived offsets,
  reject ambiguous or contradictory references, add regression tests, run local
  suite, and make one authorized live semantic smoke call. Audio and review modules
  follow in later slices of the same requested project.
- Learner explicitly paused VibeWise and requested implementation of the full
  project before returning to learning. The earlier implementation checkpoint is
  superseded; proceed autonomously within the user's existing scope.
- Phase 2A.1/2B backend implementation completed while learning was paused:
  quote-only AMD citations with backend offsets; local WAV/MP3/Whisper pipeline;
  provisional alignment and targeted acoustic recheck; SQLite/authenticated
  review actions; opt-in text/audio evaluation contracts. Final local suite:
  247 passed. One requested live AMD semantic attempt timed out after one call;
  citation validity remains unmeasured. No MiMo audio call or human-verified
  recorded-audio evaluation was run. No commit or push was performed.
