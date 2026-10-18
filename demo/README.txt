DubGuard cinematic hackathon demo

FINAL VIDEO
demo/output/DubGuard_Hackathon_Demo_Final.mp4
The corrected final uses this filename because Windows prevented replacement of the earlier MP4.
Target composition: 215 seconds, 6,450 frames, 1920 x 1080, 30 FPS.
Actual encoded properties and QA results: demo/output/verification.json.
Select the final by the filename AND SHA-256 in that receipt, not by a similar
MP4 filename. If the named file is missing, recover the verified render or rerender
separately; an older video is not a verified substitute. Cleanup does not render.
Complete timed narration: demo/output/Voiceover.txt.
Sidecar captions: demo/output/DubGuard_Subtitles.srt; captions are also burned in.

TIMELINE
00:00-00:25  Illustrative word change, waveform, problem and brand reveal.
00:25-00:45  Genuine local landing page and four-step review workflow.
00:45-01:10  Custom reference and protected OFF/ON requirement; temporary policy.
01:10-01:55  Original on-off.wav upload, preview, real CPU analysis and source citations.
01:55-02:35  Animated architecture; historical live AMD text response and validated spans.
02:35-03:05  Source playback, correction controls, pending confirmation, temporary note/export.
03:05-03:35  Illustrative protected differences, capabilities and closing links.

RERENDER (from the repository root, PowerShell)
rtk proxy npm --prefix demo/remotion ci
rtk proxy npm --prefix demo/remotion run typecheck
rtk proxy npm --prefix demo/remotion run render

The existing ignored public assets are required. No paid API is needed to render.
The renderer uses installed Chrome at C:/Program Files/Google/Chrome/Application/chrome.exe.
Change that path in demo/remotion/remotion.config.ts for another machine.

ASSET REPRODUCTION
1. Preserve the six original WAV files in recorded-evaluation/.
2. Run rtk proxy .venv/Scripts/python.exe demo/inspect_recordings.py
3. Start the real isolated API: rtk proxy .venv/Scripts/python.exe demo/serve_local.py
4. In another terminal: rtk proxy node demo/serve_frontend.mjs
5. Capture: rtk proxy node demo/capture.mjs
6. Prepare clips: rtk proxy .venv/Scripts/python.exe demo/prepare_assets.py
7. Create a separate TTS venv if absent:
   rtk proxy .venv/Scripts/python.exe -m venv demo/private/tts-venv
   rtk proxy demo/private/tts-venv/Scripts/python.exe -m pip install kokoro-onnx==0.6.1 soundfile==0.14.0
8. Download public model files: rtk proxy node demo/fetch_models.mjs
9. Narrate: rtk proxy demo/private/tts-venv/Scripts/python.exe demo/narrate.py
10. Align subtitles: rtk proxy .venv/Scripts/python.exe demo/align_subtitles.py
11. Render with the command above. Capture timing comes from actual event markers.

EVIDENCE SHOWN
Original recording used in footage and soundtrack: recorded-evaluation/on-off.wav.
Original SHA-256: a7df58f2d904e646825794be218fb159670f0aef7e8fc2aeffa3f757bcb983f1.
Recognition: "Switch the power on."
Actual result: REVIEW_REQUIRED; ASR.SUSPECTED.POLARITY.REVERSED (UNRESOLVED).
Actual source span: 0.00-2.00 seconds; approximate ASR segment, not word alignment.
Other unresolved completeness/alignment/missing-evidence findings remain visible.
Temporary decision: NEEDS_REVIEW. No human correction, listening attestation or sign-off is created.
Full private browser result: demo/private/capture/actual-result.json.
Actual exported evidence: demo/private/capture/evidence-export.json.

HISTORICAL AMD EVIDENCE
reports/phase4/amd_smoke.json and reports/phase4/amd_smoke_inspection.json.
Returned model: self-dploy/DeepSeek-V4-Flash.
One previously authorized manual-text request, 16.3927187 seconds, 805 tokens.
Validated exact spans: "Switch the power off." [0,21) and "Switch the power on." [0,20).
Requirement power-state; instruction power; observed segment s1; zero citation issues.
This historical example did not analyze the newly uploaded WAV. No new AMD requests were made.

ALL SIX REAL LOCAL RESULTS (not independently adjudicated ground truth)
correct.wav: "switch the power off"; REVIEW_REQUIRED; completeness/uncertainty.
on-off.wav: "Switch the power on."; REVIEW_REQUIRED; suspected polarity reversal.
fifteen-fifty.wav: "Wait 15 minutes before recording."; REVIEW_REQUIRED; no successful 50-versus-15 detection claimed.
before-after.wav: "Close the valve after starting the pump."; REVIEW_REQUIRED; suspected polarity reversal.
paraphrase.wav: "10. The power of"; REVIEW_REQUIRED; alignment/missing evidence.
unclear.wav: "switch the power"; REVIEW_REQUIRED; alignment/missing evidence.
Measurements, uncertainty, timestamps and original hashes: demo/private/recording-results.json.
Original media probes: demo/private/original-ffprobe.json.

LIMITATIONS AND FINAL SUBMISSION CHECKS
The tool environment cannot directly listen to audio. The actual local recognition and decoded
waveforms were checked, but independent human listening/adjudication of the six recordings
remains pending. Recording prompts and filenames were never treated as ground truth.
The final video explicitly leaves human confirmation pending and plays the genuine source.
No measured accuracy, industrial safety certification or successful numeric detection is claimed.
Generic Kokoro af_heart neural TTS explains the demo; it is not the user's recorded voice.
Original recording playback gain is adjusted only in the final mix; original WAV bytes are unchanged.
No background music is used. Browser capture has genuine cursor actions; pauses are held for narration.
The original continuous capture is retained privately for provenance.
The public HTTPS site and /api/ready were independently checked. It serves an older access-code
interface; the current public custom-review workflow is demonstrated locally, not claimed deployed.
Public deployment SHA is unknown. No deployment was performed.
LabLab's published guidance requires video under 300 MB and within five minutes:
https://lablab.ai/ai-articles/hackathon-guidelines
The authenticated submission form and any event-specific override were not accessible/verified.
A person should perform the final listen-through and check the logged-in form before upload.
No commit, push, external publication, live AMD request or production-backend edit was performed.

LICENSES / ATTRIBUTION
See demo/ASSET_LICENSES.txt. Sources, voice script and project code are kept separate from
ignored recordings, generated media, temporary runtime data and private results.
