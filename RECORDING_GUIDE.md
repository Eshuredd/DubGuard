# Phase 2C recorded-speech protocol

No human-adjudicated recordings are supplied with this repository. The six-case
[manifest template](examples/phase2c-recordings.template.json) is deliberately
invalid until a human supplies recordings, hashes, spoken ground truth, and labels.
The prompts below are recording instructions, not asserted ground truth. Do not
substitute TTS or stub-ASR tests for these measurements. Do not operate machinery.

Phase 4 adds a hash/schema preflight below. Recordings and adjudication are still
awaited; no accuracy metrics have been populated from the recording prompts.

| Case ID | Approved text | Recording prompt |
|---|---|---|
| correct | Switch the power off. | Read the approved text clearly. |
| fifteen-fifty | Wait 15 minutes before restarting. | Say “Wait 50 minutes before restarting.” |
| on-off | Switch the power off. | Say “Switch the power on.” |
| before-after | Close the valve before starting the pump. | Say “Close the valve after starting the pump.” |
| paraphrase | Switch the power off. | Say the explicitly permitted variant “Turn the power off.” |
| unclear | Switch the power off. | Make the final state word deliberately difficult to hear, without unsafe noise levels. |

1. Record actual English speech from one consenting adult, preferably mono PCM WAV,
   16 kHz, with a short leading/trailing silence. Keep clips under 30 seconds for
   the separate optional MiMo probe. Preserve original bytes and consent privately.
2. A reviewer listens to the original audio and transcribes what was actually said,
   without copying the prompt. Retain `[unclear]` where speech cannot be resolved.
   A second independent listener should adjudicate disagreements. Record identities
   and notes. Do not guess the final word from the approved instruction.
3. Copy the template to a private manifest. Set absolute paths, actual SHA-256,
   reviewer IDs, notes, spoken_ground_truth and independently assigned labels.
   Replace policy reviewer placeholders. For ambiguity use UNRESOLVED. Never fill
   ground truth from ASR output. Timestamps may be null; only enter measured spans.
4. Optionally enter `human_corrected_transcript` using source `manual`, completeness
   `complete` only after listening to the whole clip, and segments with stable IDs,
   actual text, instruction IDs and measured timestamps. Keep `uncertain: true`
   for unclear text. This evaluation metadata is not authenticated production evidence.
5. Run local evaluation using an already cached model (no automatic download):

```sh
.venv/bin/python -m dubguard.audio_evaluation /absolute/path/manifest.json --model-path /absolute/path/cached-whisper-model --output reports/recorded_audio.json
```

Reports include duration, recognized text, processing coverage and gaps, timestamp
validity, tentative alignments, suspected violations, optional human corrections,
final verification decision and ASR processing latency. Processing coverage measures
which audio was processed, not whether all words were recognized. Evaluation never
performs release signoff. The raw-ASR and corrected-evidence results remain separate.

For production review, use the authenticated transcript-evidence endpoint and retain
the original raw transcript. Correcting an ASR error changes text to what was heard;
it cannot repair an actual spoken instruction error. Re-record actual errors and
create a superseding workflow. Keep held-out recordings separate from tuning cases.

## Phase 4 import and exact commands

Keep clips and the filled manifest outside Git, for example in the already ignored
`.dubguard-data/recorded-evaluation/` directory. Do not put them in `examples/` or
public `reports/`. Close or discard a Quick Test session only after saving any
original recording needed for private evaluation; Quick Test retention is temporary.
Use one consenting speaker and an independent listener who transcribes actual
speech before seeing ASR. A second listener adjudicates unresolved differences.

From the repository root in PowerShell:

```powershell
New-Item -ItemType Directory -Force .dubguard-data/recorded-evaluation
Copy-Item examples/phase2c-recordings.template.json .dubguard-data/recorded-evaluation/manifest.json
Get-FileHash -Algorithm SHA256 'C:/absolute/private/correct.wav'
# Edit the private manifest with the original absolute paths and lowercase hashes,
# real listener IDs, notes, actual spoken_ground_truth, and independently chosen labels.
.venv/Scripts/python scripts/check_recordings.py .dubguard-data/recorded-evaluation/manifest.json
.venv/Scripts/python -m dubguard.audio_evaluation .dubguard-data/recorded-evaluation/manifest.json --model-path .dubguard-data/models/tiny.en --output .dubguard-data/recorded-evaluation/results.json
```

On Linux use `.venv/bin/python` for the same commands, `mkdir -p` / `cp` for setup,
and `sha256sum /absolute/private/correct.wav` for each hash. A cached model can be
prepared explicitly using `deploy/cache_model.py` as documented in DEPLOYMENT.md;
evaluation itself never downloads a model or invokes AMD.

The copied template is intentionally incomplete. Prompts and suggested categories
do not establish labels. Each `spoken_ground_truth` span needs actual heard `text`,
an existing `instruction_id` when known, and paired measured times or two nulls.
Use `UNRESOLVED` when the word cannot be heard. Replace all policy reviewer placeholders.
Retain development/held_out splits without tuning on held-out clips. Optional
`confirmed_asr_alignment` uses IDs from an actual ASR pass; never invent the IDs.
Optional `human_corrected_transcript` must describe what was spoken, including
any actual mistake, not the narration the speaker intended to say.

After complete recordings/labels are supplied, the existing evaluator produces
raw recognized text, processing latency/coverage/gaps, timestamp validity,
word error rate, protected-term error counts, candidate findings and proposed
alignment accuracy where confirmed mappings exist. It reports raw and optional
human-corrected evidence separately, with decisions/metrics split by development
and held-out cases. A secondary cached model is optional via
`--secondary-model-path /absolute/path/to/distinct/model`. No claim of statistical
generalization follows from six clips; protected-term counts do not replace a
human semantic judgment. No evaluation operation signs off a recording.
