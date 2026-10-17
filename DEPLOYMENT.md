# Single-server demo deployment

Status: prepared, not deployed. No public URL is verified. Phase 4 is uncommitted;
the Git commands below require an approved Phase 4 commit to be pushed first.
No AMD inference, purchase, or deployment has been authorized by these instructions.

## Server and public URL requirements

Recommended starting point: a Hetzner Cloud **x86-64 AMD CPU** instance in Singapore,
with at least 4 vCPUs, 8 GB RAM and 80 GB disk; choose the current matching plan in
the console. This is a sizing recommendation, not a measured capacity guarantee.
The [provider describes its AMD CPX offering here](https://www.hetzner.com/cloud-singapore/).
Check current regional pricing before ordering. No GPU server is needed for this demo.

Use Ubuntu 24.04 LTS with working Docker Engine and Compose v2, Git and Python 3.
Install Docker using its [official Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/).
The operator must have Docker privileges. Budget for ongoing server, disk and
Token Factory costs; no resources were provisioned during Phase 4.

Obtain a hostname you control, point its DNS A record to the server's public IPv4,
and remove an incorrect AAAA record (or configure working IPv6). Allow inbound
TCP 80/443, optional UDP 443, and restrict SSH to operator IPs. Do not publish 8000.
Caddy serves the compiled SPA and strips `/api` before proxying to FastAPI on the
private Compose network. Its [automatic HTTPS](https://caddyserver.com/docs/automatic-https)
needs reachable DNS/ports and persistent certificate storage. Browser recording
requires HTTPS or localhost. No extra frontend origin/CORS exception is needed.

## Configure and start (operator action after approval)

Run the following Bash commands **on that server** after the reviewed Phase 4
commit has been approved and pushed. Replace the hostname and commit placeholder.

```bash
git clone https://github.com/Eshuredd/DubGuard.git
cd DubGuard
export PHASE4_REVISION='<approved Phase 4 commit SHA>'
git checkout "$PHASE4_REVISION"
export DUBGUARD_DOMAIN='dubguard.your-domain.example'
export DUBGUARD_WHISPER_REVISION='0d3d19a32d3338f10357c0889762bd8d64bbdeba'
sudo install -d -m 700 /etc/dubguard
sudo python3 deploy/create_env.py /etc/dubguard/server.env
sudoedit /etc/dubguard/server.env
```

The generator creates different random reviewer and demo secrets and refuses to
overwrite an existing file. Use the private editor to supply only the Token Factory
API key and retrieve the access codes for private distribution. Do not paste them
into source, command-line flags, logs, screenshots or the frontend. Preserve
`AMD_TOKEN_FACTORY_MODEL=DeepSeek-V4-Flash` and the separate
`AMD_TOKEN_FACTORY_AUDIO_MODEL=MiMo-V2.6-Flash`. The latter is not invoked by the UI.
With a blank AMD key local analysis still works and AMD reports configuration failure.
The generated demo configuration bounds Full Review uploads to 25 MB / 120 seconds;
Quick Test always has its stricter 10 MB / 60-second cap.

```bash
dc() { docker compose -p dubguard -f deploy/compose.yaml "$@"; }
# --quiet avoids rendering secret environment values.
dc config --quiet
dc build api web
# Explicit public model download and CPU model-load validation, not AMD inference.
dc --profile setup run --rm --no-deps cache-model
dc up -d api web
dc ps
python3 deploy/smoke.py "https://$DUBGUARD_DOMAIN"
```

The reviewed tiny.en model revision is downloaded only by the setup command into
`dubguard_whisper_models`; runtime mounts it read-only and has `HF_HUB_OFFLINE=1`.
No first request downloads weights. The CPU image includes FFmpeg/ffprobe and
libgomp, installs both core and audio dependencies, and runs as UID 10001.
Build context is allowlisted by `.dockerignore`; `.env`, recordings, SQLite,
node_modules, Git history and local notes are excluded.

On success, the working public entry points are `https://YOUR_HOSTNAME/test` and
`https://YOUR_HOSTNAME/login`. These are URL patterns until the smoke and microphone
tests succeed. `/api/health` checks API liveness; `/api/ready` returns 503 unless
audio dependencies, FFmpeg and local model files are present. Readiness does not
claim speech accuracy or AMD service availability. Model-load success is checked
by cache setup; test a real short recording next.

## Local container smoke when Docker is available

Use the same setup with `export DUBGUARD_DOMAIN='http://localhost'` and a private
server config file (set `DUBGUARD_SERVER_ENV` to its absolute path). After building
and caching the model, run `python3 deploy/smoke.py http://localhost`. This verifies
SPA deep links, proxy routing, readiness and scenarios without inference. It
does not validate public DNS, TLS issuance, physical microphones or recognition.

The Phase 4 host has a Docker CLI, but the `dockerDesktopLinuxEngine` named pipe
is absent. Therefore no container build/run was performed. Compose config was
validated with temporary empty configuration and fixture hostname/revision;
no real credentials were loaded or displayed by that check.

## Verified local CPU setup in this checkout

The same model revision was explicitly downloaded into the ignored
`.dubguard-data/models/tiny.en` and loaded/executed on CPU. The two-second generated
silence smoke is in `reports/phase4/cpu_smoke.json`; it is not a speech accuracy test.
PyAV is pinned to 18.1.0 because faster-whisper 1.2.1 uses an argument removed by
PyAV 19. The initial real execution failed before this pin; the rerun succeeded.

To reproduce on Windows from the repository root without editing `.env`:

```powershell
.venv/Scripts/python -m pip install -r requirements-audio.txt
.venv/Scripts/python deploy/cache_model.py --revision 0d3d19a32d3338f10357c0889762bd8d64bbdeba --output .dubguard-data/models/tiny.en
.venv/Scripts/python scripts/cpu_smoke.py --model-path .dubguard-data/models/tiny.en --output reports/phase4/cpu_smoke.json
$env:DUBGUARD_WHISPER_MODEL = (Resolve-Path .dubguard-data/models/tiny.en).Path
.venv/Scripts/python -m uvicorn dubguard.api:app --host 127.0.0.1 --port 8000
```

Set the separate private demo/reviewer access configuration before opening the UI;
no access codes were printed by this setup. In another terminal run
`npm --prefix frontend run dev`. Linux uses `.venv/bin/python` and
`export DUBGUARD_WHISPER_MODEL="$PWD/.dubguard-data/models/tiny.en"` instead.

## Judges and demonstration

Privately give judges the URL and **demo code only**. They open `/test`, enter it,
choose a scenario, select Local Verification, record/preview or upload a clip, then
click Analyze recording. Show recognized words, processed coverage and provisional
constraint candidates. For AMD, choose AMD Semantic Review on the next analysis,
read and tick the text-transfer consent, then analyze. Each run needs fresh consent.
Show the actual model, call ID, latency, attempt count and validated citations;
if unavailable or unsupported, demonstrate the honest failure state.

There are three analyses/session, including at most two AMD runs. Failures consume
quota; no automatic retries occur in Quick Test. Admissions are also capped at
20 active sessions and 30/hour, with two demo jobs and one demo AMD call concurrently.
Do not promise unrestricted access to a large judging audience. Wait for quota
windows rather than resetting the database to manufacture unlimited access.
Only authorized reviewers receive a separate reviewer token and enter `/login`.

## Limits, restarts and operations

This is a bounded **single-server demo**, with in-process background tasks. Run
exactly one API process/replica against these volumes; do not add Uvicorn workers,
autoscaling, rolling overlapping replicas or a second server using the SQLite files.
Compose limits API CPU to 3 cores, RAM to 4 GB, processes to 128, request concurrency
to 16 and temporary decode space to 512 MB; Whisper uses two CPU threads per model.
The web service has a separate 1-core/256-MB cap. Proxy bodies are capped at 26 MB.
No automated GPU allocation occurs. Cap disk use operationally: monitor free space,
review retention and logs (10 MB x three rotations/service); Docker volumes have
no intrinsic disk quota. Use encrypted disks/backups and protect Docker access.

SQLite and original audio persist in `dubguard_review_data`. Quick Test TTL is
30 minutes, swept on requests and each minute; deletion can precede the end of
in-flight decoding/inference, whose runtime slots remain occupied until completion.
Work is not forcibly terminated by deleting the browser session. Expired/deleted
sessions cannot regain a result, and orphan files are cleaned after work finishes.
Full Review artifacts remain until operator-managed retention; no retention UI exists.

Stopping the API allows 90 seconds graceful shutdown (Compose allows 100 seconds).
An abrupt restart marks unfinished Quick Test jobs failed and leaves quota spent.
Unfinished Full Review transcription/verification/acoustic jobs become failed,
invalidate their verification reference and add an audit event. They never regain
approval readiness and are never retried automatically. Inspect preserved evidence;
if the failed state cannot resume in the UI, create a new superseding workflow.
An already-sent remote request may have been billed; a failed local job is not
evidence the provider did nothing. Completed runs/evidence remain versioned.

For consistent backups, stop the API, copy the complete data volume privately,
then restart. Example (run from the same shell with `dc` defined):

```bash
sudo install -d -m 700 /var/backups/dubguard
dc stop api
docker run --rm -v dubguard_review_data:/source:ro \
  -v /var/backups/dubguard:/backup alpine:3 \
  tar czf /backup/review-data.tar.gz -C /source .
sudo chmod 600 /var/backups/dubguard/review-data.tar.gz
dc start api
python3 deploy/smoke.py "https://$DUBGUARD_DOMAIN"
```

Never run `down -v` against retained evidence. For an update, stop API work first,
back up, check out the approved revision, rebuild, and recreate the single API.
Restore database and audio together when rolling back. Keep certificate volume
and server config separately backed up. Do not publish an audit export containing
private narration without its owner's permission.

For long-term production, add managed identities/roles, durable workers, distributed
admission control, monitored retention and stronger audit storage before expanding
beyond the controlled demo. The shared-token and SQLite MVP is not a certification
or a multi-tenant production review system.
