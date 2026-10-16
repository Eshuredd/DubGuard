# Phase 2C recorded-speech protocol

No human-adjudicated recordings are supplied with this repository. The six-case
[manifest template](examples/phase2c-recordings.template.json) is deliberately
invalid until a human supplies recordings, hashes, spoken ground truth, and labels.
The prompts below are recording instructions, not asserted ground truth. Do not
substitute TTS or stub-ASR tests for these measurements. Do not operate machinery.

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
