# DubGuard — 2 minute 45 second demonstration script

Use actual Chrome/physical-microphone footage only after the manual checklist.
Hide codes/tokens and private audio. Prerecord slow transitions if necessary and
label prerecorded footage. No new AMD request is authorized for Phase 5.

| Time | Screen/action | Spoken narrative |
|---|---|---|
| 0:00–0:20 | Title and target user | “Industrial narration can change meaning with a single word: off becomes on, or 15 becomes 50. DubGuard helps training-content teams and human reviewers inspect those changes against their approved instructions.” |
| 0:20–0:35 | Quick Test / On versus off; approved text and protected requirement | “This is a demonstration script: Switch the power off. Its policy explicitly protects the power state. Local Verification is the default.” |
| 0:35–1:00 | Physical microphone permission, start, say “Switch the power on,” stop and preview | “Recording and submission are separate. I can preview the original audio before asking DubGuard to analyze it.” |
| 1:00–1:25 | Analyze locally, play original, inspect actual recognized words/timestamps/candidates | “Whisper runs on CPU. These recognized words are provisional. Here is the actual result and its source span.” If no candidate is returned, say so and show the real state; never assert an unreturned violation. |
| 1:25–1:45 | Select AMD Semantic Review, show unchecked consent and requested model; do not submit | “AMD review is an explicit opt-in. It sends script, policy and transcript text to AMD Token Factory using DeepSeek-V4-Flash. Original audio is not sent to DeepSeek. Another live request needs separate authorization.” |
| 1:45–2:10 | Open committed Phase 4 response/inspection, clearly titled HISTORICAL TEXT SMOKE | “This is a previously authorized manual-text smoke, not this microphone recording. The actual response took 16.393 seconds, used 805 tokens, and cited the off/on reversal with two exact valid source spans. The deterministic critical decision stayed intact. This is one example, not an accuracy benchmark.” |
| 2:10–2:35 | Full Review, actual saved human evidence and blocked approval for wrong speech | “A reviewer listens to the original and records what was actually said. AMD advice cannot approve narration. A confirmed wrong power state blocks sign-off and needs a new recording; correcting ASR cannot repair spoken instructions.” |
| 2:35–2:45 | Audit/export and closing frame | “DubGuard combines explicit constraints, AMD advisory inference and inspectable evidence while keeping the final decision with a human. Public deployment and real-speech accuracy remain pending where stated in our release checklist.” |

If a correct replacement clip has actually completed the full workflow, a short
prerecorded segment can show explicit sign-off bound to its current evidence/run.
Label it prerecorded and use only an actual permitted approval. Otherwise show
the blocked approval and explain the prerequisites; do not manufacture a success.

For a future explicitly authorized live AMD recording segment, replace the historical
portion with that actual call's status and evidence. Label waiting/prerecorded
transitions, preserve failures, and update reported measurements from its saved
result. Do not mix mocked test responses into live footage. Only Token Factory /
DeepSeek is an executed AMD contribution here; no ROCm/Quark/MiMo claims.
