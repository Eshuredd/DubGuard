# Release checklist and ownership

Baseline audited: fetched `origin/main` equals local `main` at
`c8b688d77a7c8f34f74f1d5ab89e9d8d8564753a` (smoke test). Phase 4 is committed/pushed.
Phase 5 files are local until separately reviewed and approved for commit/push.

## Completed or independently checkable in this checkout

- [x] Check clean working tree before editing; fetch and verify main.
- [x] Verify both AMD evidence reports are committed and scan them for credentials.
- [x] Preserve the successful historical one-call AMD measurements without rerunning it.
- [x] Correct stale Phase 4 commit/push statements while preserving historical results.
- [x] Inspect Docker/Compose/Caddy/model setup, secret generation and smoke tooling.
- [x] Diagnose existing Docker/WSL: Linux engine is available; no system changes made.
- [x] Prepare localhost-only isolated Compose override, blank-key configuration and real-ASR/restart protocol.
- [x] Prepare physical-microphone protocol, format/hash/import/evaluation/Markdown commands.
- [x] Prepare title, 210-character short description and 1,599-character long description.
- [x] Prepare a 2:45 demo script distinguishing historical, live and mocked evidence.
- [x] Execute backend/frontend builds, pinned model cache, health/readiness, same-origin routing, real local ASR and persistence/recovery checks.
- [x] Execute production-bundle Chrome/CSP check on generated silence; no AMD request.
- [x] Complete validation: 305 backend tests, 13 frontend tests, eight workflow E2E tests and one production-container Chrome test passed; typecheck/build/dependency checks passed.
- [ ] Review PHASE5_REPORT.md and final diff before approving release.

## Public deployment: user-controlled requirements

| Step | Codex can prepare/perform | User action / gate |
|---|---|---|
| Choose CPU provider | Recommend x86-64 4 vCPU / 8 GB / at least 80 GB; audit current options | Choose provider/region and explicitly approve billing; no server has been purchased |
| Provision host | Apply approved setup once access and permission exist | Supply an authorized host/public IP and SSH access through an approved private mechanism |
| Domain/DNS | Check supplied records and prepare Caddy hostname | Obtain/control a hostname, provide it and authorize DNS changes; no domain ownership assumed |
| Release source | Prepare reviewed files and exact commands | Approve Phase 5 commit/push separately, then identify the release SHA |
| Server configuration | Generate distinct new private tokens and validate configuration | Privately supply AMD key/reviewer identities; do not paste secrets into source, chat or screenshots |
| Deployment | Build/cache/start the complete app on that approved host | Explicitly authorize public deployment; never reuse localhost test credentials |
| DNS/TLS | Test reachable 80/443, HTTPS issuance and persisted Caddy state | Authorize needed firewall/DNS actions; TLS stays unverified until the real hostname exists |
| Physical capture | Provide exact Chrome test procedure | A consenting person records actual speech and verifies the input device/permission |
| Real-speech accuracy | Validate hashes, run offline evaluation and render reports | Supply original clips, independent ground truth, labels and publication consent |
| Further AMD inference | Prepare a separately capped request | Fresh explicit authorization; the one Phase 4 request is already consumed |
| Final dashboard | Prepare descriptions/assets/checklist | Verify deadline/requirements and authorize submission; no dashboard entry was submitted |

## Before exposing the public service

- [ ] Use DEPLOYMENT.md's production commands and an approved release SHA containing required fixes.
- [ ] Keep only one API process; no replica overlap against the same SQLite/job state.
- [ ] Use a private root-owned 0600 env file and privileged Compose CLI; never make it public-readable.
- [ ] Keep the AMD key out of Vite/browser configuration and Docker build context.
- [ ] Mount SQLite/audio and certificates persistently; keep the pinned model read-only/offline at runtime.
- [ ] Confirm FFmpeg, `/api/health`, `/api/ready`, SPA deep links and same-origin API operation.
- [ ] Confirm HTTPS microphone permissions on physical Chrome; Safari remains separately unverified.
- [ ] Confirm upload/duration/resource limits, no automatic approvals, quotas and failed-job recovery.
- [ ] Monitor disk, `dc ps`, health, CPU/memory and rotated logs; alert on restarts and low free disk.
- [ ] Set an operator retention/backup policy; Quick Test TTL is not Full Review retention.
- [ ] Verify a private consistent SQLite-plus-audio backup and restoration procedure.
- [ ] Test capacity with consented realistic clips before promising concurrent judge access.

4 vCPUs / 8 GB is a starting configuration, not a measured production capacity
guarantee. Tiny.en weights are approximately 78 MB; runtime/decoder/Python memory
and concurrency are additional. Compose bounds API RAM at 4 GB and CPU at 3 cores,
web RAM at 256 MB, threads at two per ASR model, request concurrency at 16 and demo
jobs at two. Single silence checks do not measure peak memory or realistic load.

## Human evidence and demonstration

- [ ] Run MICROPHONE_CHECKLIST.md for all six actual recording cases and capture failure states.
- [ ] Keep human labels independent of model output, preserve unclear text and held-out separation.
- [ ] Report ASR WER, protected-token errors, acoustic disagreement and verification decisions separately.
- [ ] Treat missing secondary recognition as unmeasured, not agreement.
- [ ] Show the source audio and exact current human evidence before any eligible sign-off.
- [ ] Do not call a raw-ASR candidate a confirmed spoken violation or certification.
- [ ] Label Phase 4 AMD evidence historical manual text; label Playwright evidence mocked/stubbed.
- [ ] Publish no private recordings, credentials, fabricated customers, URLs, speedups or accuracy results.
- [ ] Include only actually executed AMD Token Factory / DeepSeek use; no ROCm, Quark or MiMo claims.

## Final review

- [ ] Read PHASE5_REPORT.md's actual container status and test counts.
- [ ] Resolve critical defects, or state blocking limitations openly.
- [ ] Approve commit/push only after reviewing the final diff.
- [ ] Verify final public URL/video/repository links in the actual submission dashboard.

Suggested Phase 5 commit after approval:
`chore(release): validate deployment and prepare hackathon submission`.
