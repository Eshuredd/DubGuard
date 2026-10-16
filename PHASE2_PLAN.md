# Phase 2A.1 + 2B implementation plan

1. Keep the Phase 1 deterministic engine and Phase 2A transport. Change semantic
   citations to model-selected IDs and exact quotes; derive offsets locally and
   reject ambiguous or contradictory evidence.
2. Add a bounded local audio intake and optional CPU Whisper adapter. Store the
   original by digest, decode and chunk derived PCM with FFmpeg, preserve original
   offsets and processing coverage, and keep ASR output provisional.
3. Add conservative alignment and protected-term acoustic disagreement records.
   Neither tentative mapping nor agreement between recognizers may clear safety
   review. Keep AMD MiMo audio optional pending a separately authorized small test.
4. Add SQLite-backed versioned review records, authenticated reviewer actions,
   explicit final signoff, supersession, and audit events within FastAPI.
5. Expand opt-in evaluation contracts and tests. Run the local suite, one requested
   live DeepSeek semantic example, and report measured results and limitations.

No frontend, automatic release, full remote benchmark, or commit/push is in scope.

Implementation status (2026-10-16): steps 1–4 are implemented as local backend
capabilities with mocked HTTP and ASR tests. The first AMD semantic smoke attempt
timed out after one request, so improved live citation validity is unmeasured.
One small CPU Whisper model was exercised on synthesized speech; no human-verified
recorded-audio corpus or MiMo call is included. The opt-in audio evaluation
manifest and local subset report are prepared, while acoustic/ASR/alignment and
reviewer-workload quality metrics await genuine adjudicated recordings.
