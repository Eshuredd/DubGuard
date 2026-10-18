# DubGuard — Industrial Narration Review

DubGuard helps human reviewers check English, single-speaker industrial narration
against approved instructions. It makes changes to protected numbers, polarity,
warnings and operation order inspectable through original audio and source-linked
findings. It supports browser recording, uploads and a separate reviewer workspace.

**DubGuard is a review aid. `PASS_CANDIDATE` is not safety certification or release
approval. Uncertain evidence and confirmed violations block approval.**

## Try it

The DigitalOcean installation is at
[Quick Test](https://134-209-145-248.sslip.io/test), with a separate
[Reviewer Workspace](https://134-209-145-248.sslip.io/login).
The [recorded public audit](reports/phase6/public-baseline/audit.json) observed
HTTP 200 on 17 October 2026 at 18:17 UTC. Read-only HEAD checks of `/test` and
`/login` also returned HTTP 200 during cleanup on 18 October 2026. These confirm
route reachability, not the running revision, API readiness or microphone behavior.
The latest repository changes must not be assumed deployed.

1. Open Quick Test. Enter the operator's private demo code if prompted; optional
   public local access depends on server configuration.
2. Choose a demonstration scenario and **Local Verification**. Record or upload
   a short clip, preview it, and save the original before submitting if needed.
3. Analyze and inspect playback, recognized words, coverage and findings. Raw ASR
   remains provisional even when it appears correct. Quick Test never signs off.

Local Verification makes no AMD request. AMD Semantic Review requires a separate
operator-issued AMD code and fresh text-transfer consent for every analysis.
Reviewer tokens are separate credentials intended only for authorized reviewers.
Quick Test permits clips up to 60 seconds / 10 MB and three analyses per session;
sessions expire after 30 minutes. See [deployment and access controls](DEPLOYMENT.md).

## How it works

```text
Approved script + reviewer policy       Original recording
                 |                            |
                 |                   FFmpeg + local CPU Whisper
                 |                            |
                 +------ deterministic checks + provisional transcript
                                      |
                        optional AMD semantic advice
                        + exact source citation validation
                                      |
                     human listening + versioned evidence
                                      |
                     current-run review and explicit sign-off
```

The stack is React, TypeScript and Vite; Python, FastAPI and Pydantic;
FFmpeg and faster-whisper/CTranslate2; SQLite; Docker Compose and Caddy HTTPS.
AMD Token Factory provides opt-in **DeepSeek-V4-Flash** text inference. It receives
script, policy and transcript text; original audio stays on the server. Model
advice cannot override deterministic violations, establish spoken truth or approve
a recording. Unsupported citations become unresolved evidence.

## Run locally

Use Python 3.11+ and Node.js 22.22.2+ (22.x), 24.15+ (24.x), or 26+.
From the repository root, in Bash:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt -e .
.venv/bin/python -m dubguard validate examples/policy.json
.venv/bin/python -m dubguard verify examples/critical.json
.venv/bin/python -m pytest -q
npm --prefix frontend ci
```

On Windows use `py -3.12 -m venv .venv` and `.venv/Scripts/python` in place of
`.venv/bin/python`. Deterministic verification requires no key, GPU or model.
CLI exit code 0 means successful execution; read the JSON `decision` for the result.

For recording and transcription, install the audio dependencies and explicitly
cache the pinned public model (this downloads weights, with no AMD inference):

```bash
.venv/bin/python -m pip install -r requirements-audio.txt
.venv/bin/python deploy/cache_model.py --revision 0d3d19a32d3338f10357c0889762bd8d64bbdeba --output .dubguard-data/models/tiny.en
```

Copy [.env.example](.env.example) to a private, ignored `.env` and configure:

- `DUBGUARD_WHISPER_MODEL`: absolute path to that cached model directory.
- `DUBGUARD_DATA_DIR`: private writable directory for SQLite and original audio.
- `DUBGUARD_REVIEW_TOKENS_JSON`: `{"reviewer-id":"unique-random-secret"}`.
- `DUBGUARD_DEMO_ACCESS_CODE`: a different random secret of at least 24 characters.

Keep public local mode disabled for private development. AMD settings are optional;
leave the API key blank for local-only use. Never reuse secrets or put server keys
in Vite configuration. See [complete configuration](DEPLOYMENT.md#configuration).

Start the API and frontend in separate terminals:

```bash
.venv/bin/python -m uvicorn dubguard.api:app --host 127.0.0.1 --port 8000
npm --prefix frontend run dev
```

Open [localhost Quick Test](http://127.0.0.1:5173/test) or
[Create a Review](http://127.0.0.1:5173/workspace). The custom workspace opens
without login. Enable `DUBGUARD_PUBLIC_WORKSPACE=true` only after validating its
isolation and limits; its safe default is false. Private operational reviews use
`/operator`. See [configuration and upgrade notes](PUBLIC_WORKSPACE.md).
Vite proxies `/api` to
FastAPI; the [local API schema](http://127.0.0.1:8000/docs) describes request bodies.
Recording requires HTTPS or localhost. Runtime never downloads missing models.
Use the [local container protocol](DEPLOYMENT.md#local-container-validation) to
test the production build, same-origin routing and persistent storage.

## What has been verified

The [60-case synthetic development evaluation](docs/EVALUATION.md) measured
22/24 critical recall (91.67%), 22/22 critical-alert precision and 0/24
acceptable-to-critical alerts for the deterministic engine. Two critical semantic
challenges escalate to human review and count as recall misses. These fixtures
are neither held-out data nor independent industrial ground truth.

One [live AMD manual-text smoke](reports/phase4/amd_smoke.json) returned two valid
off/on citation spans in 16.393 seconds using 805 tokens. Its
[saved inspection](reports/phase4/amd_smoke_inspection.json) checked provenance and
preserved the local critical decision. One example does not establish general
semantic reliability or audio accuracy. Earlier rejected-citation and timeout
observations are also retained.

Automated browser checks use synthetic microphone audio and stubbed recognition;
container checks exercised real CPU Whisper on generated silence. Physical
microphones, Safari capture, independently adjudicated speech accuracy, realistic
concurrent load, ROCm, Quark and MiMo inference remain unverified or unmeasured.
Numeric/language grammar is intentionally limited. Shared-token authentication,
SQLite history and in-process jobs suit a controlled single-server demonstration.

## Guides and evidence

- [Architecture, evidence and human review](docs/ARCHITECTURE.md)
- [Evaluation methodology, results and test commands](docs/EVALUATION.md)
- [Deployment, upgrades, backups and rollback](DEPLOYMENT.md)
- [Real-audio collection and evaluation](docs/RECORDING_GUIDE.md)
- [Hackathon submission material and demonstration script](docs/SUBMISSION.md)

Representative UI captures: [landing](reports/phase6/after/landing-desktop.png),
[local evidence](reports/phase6/after/local-evidence-desktop.png),
[AMD panel](reports/phase6/after/amd-mocked-desktop.png) and
[mobile review](reports/phase6/after/critical-signoff-mobile.png).
These are automated local captures with synthetic audio, stub ASR and mocked AMD
responses where shown; they are not live inference or speech-quality evidence.
