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
