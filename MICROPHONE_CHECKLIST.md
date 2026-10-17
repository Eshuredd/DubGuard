# Physical microphone and real-speech checklist

Status: actual speech clips and independent listener ground truth are awaited.
Run this manually in ordinary desktop Chrome with a physical microphone; automated
Chrome fake-device tests and generated silence do not satisfy this checklist.

## Capture protocol

1. Open `/test` on the verified HTTPS origin, or localhost during local testing.
   Enter only the private demo access code; never show it in the video. Check the
   selected physical input device and browser/site microphone permissions.
2. Select **Local Verification**, choose the matching scenario, click Record
   narration, grant microphone permission, then Start recording. Record one
   consenting adult speaker in English, under 30 seconds, without operating machinery.
3. Stop, preview, and confirm that the captured voice is actually audible. Save
   the original file privately if needed for evaluation; Quick Test data expires.
   File upload accepts WAV, MP3, WebM/Opus and MP4/AAC. Do not rename a container
   extension to pretend it is WAV. Mono 16-kHz PCM WAV is the simplest recording format.
4. Submit explicitly. Check the **Analyzed mode**, analyzed scenario, original
   playback, recognized text, timestamps, coverage and uncertainty. If the words
   are wrong or missing, retain that result; do not substitute the intended script.
5. Repeat with the six rows below. A session permits three attempts, including
   failures; start a new session through the normal flow and respect admission caps.
6. Check denial/cancellation, Stop/preview, delete, refresh, navigation cleanup
   and the 60-second/10-MB Quick Test limits. Confirm device use ends after discard.

| Clip ID / scenario | Recording prompt (not ground truth) | Manual inspection |
|---|---|---|
| correct | Switch the power off. | Actual recognized words, original audio, provisional review state; never automatic approval |
| on-off | Switch the power on. | Candidate protected polarity change if recognized; timestamp seeks original audio |
| fifteen-fifty | Wait 50 minutes before restarting. | Candidate numeric change against approved 15 minutes; inspect word/digit forms |
| before-after | Close the valve after starting the pump. | Compare with approved before wording; inspect actual rule/advisory result without assuming a detection |
| paraphrase | Turn the power off. | Explicitly approved variant; raw ASR still requires human verification |
| unclear | Make the final power-state word difficult to hear, at safe volume | Preserve uncertainty and unresolved text; never infer the word from the approved script |

The `before-after` fixture is a protected polarity/template relation, not a proof
of arbitrary multi-step temporal understanding. Full Review additionally supports
explicit protected sequence constraints. No fixture outcome is a measured speech result.

## AMD contribution inspection without another remote call

Select AMD Semantic Review and inspect its requested-model and text-transfer
disclosure. Consent is unchecked by default and resets after an analysis. Do not
submit this mode without fresh explicit authorization for another paid request.
Inspect the separately committed `reports/phase4/amd_smoke.json` as historical
manual-text evidence: returned model, call ID, attempts, latency, usage and exact
source citations. This is not the newly captured narration. Mocked browser-test
screenshots must be labeled mocked. ROCm, Quark and MiMo were not executed.

If a later request is explicitly authorized, verify fresh consent, requested and
returned model, actual status/attempts/latency, citation rejection, retained local
findings and separate advisory AMD findings. Show failures as failures.

## Private import commands (PowerShell, repository root)

These commands never call AMD. Install the already pinned local dependencies and
cache the pinned Whisper model using DEPLOYMENT.md if not done yet. Do not overwrite
an existing manifest or generate labels from ASR.

```powershell
$privateDir = Join-Path (Get-Location) '.dubguard-data/recorded-evaluation'
New-Item -ItemType Directory -Force $privateDir | Out-Null
$manifestPath = Join-Path $privateDir 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) {
    Copy-Item -LiteralPath examples/phase2c-recordings.template.json -Destination $manifestPath
}
# Copy consenting original files into this private directory, using the six clip IDs.
# Inspect each actual file, including signature, decoding, duration, rate and format:
.venv/Scripts/python scripts/inspect_audio.py "$privateDir/correct.wav"
Get-FileHash -Algorithm SHA256 -LiteralPath "$privateDir/correct.wav"
# Repeat format/hash checks for all six files with their actual extensions.
notepad $manifestPath
```

In the editor, set **absolute** original file paths, actual lowercase SHA-256,
real listener IDs and adjudication notes, what was actually spoken, measured
timestamps or paired nulls, reviewed policies, and independently assigned labels.
A second listener should adjudicate disagreements without seeing ASR. Preserve
`[unclear]` and `UNRESOLVED` when necessary. Do not copy recording prompts as truth.
Retain development/held_out splits and do not tune against held-out clips.

```powershell
.venv/Scripts/python scripts/check_recordings.py $manifestPath
.venv/Scripts/python -m dubguard.audio_evaluation $manifestPath --model-path .dubguard-data/models/tiny.en --output "$privateDir/results.json"
.venv/Scripts/python scripts/render_audio_report.py "$privateDir/results.json" --output "$privateDir/results.md"
```

The template remains intentionally invalid until real evidence is supplied. The
preflight checks schema and original-byte hashes, not the truth of human assertions.
`human_corrected_transcript` is optional and must preserve actual spoken errors.
`confirmed_asr_alignment` must refer to actual ASR segment IDs after a real run.
Use an already cached distinct model with `--secondary-model-path` only when
measuring independent local acoustic disagreement; no secondary model was measured here.

## Read each result category separately

- **ASR word errors:** primary recognized words versus listener ground truth; WER
  needs a nonempty reference denominator. Missing results remain Not measured.
- **Protected tokens:** declared term-presence errors, including number/polarity
  terms; spelling/word-digit differences can affect this lexical metric.
- **Acoustic disagreement:** differences between independent recognizers; absent
  secondary inference is Not measured, not zero disagreement or confirmed truth.
- **Verification:** raw-ASR candidate decision separately from an optional human-
  corrected decision and supplied label. Neither is authenticated production sign-off.
- **Coverage/timing/latency:** processed audio spans and actual runtime; complete
  processing does not prove every word was recognized or heard correctly.

For final production review, an authenticated person must listen to the original,
save actual spoken-text evidence, review every prerequisite and explicitly sign off.
An actual wrong instruction requires a new recording/superseding workflow; an ASR
correction cannot repair the speech. Retain private clips, manifests and reports
outside Git, and publish only consented/redacted evidence.
