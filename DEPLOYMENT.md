# Deployment and operations

The existing installation is a user-reported DigitalOcean Ubuntu 24.04 Droplet
with 4 vCPUs / 8 GB at [Quick Test](https://134-209-145-248.sslip.io/test).
The [GET-only audit](reports/phase6/public-baseline/audit.json) observed HTTP 200
on 17 October 2026 at 18:17 UTC without credentials or mutations. Read-only HEAD
checks of `/test` and `/login` returned HTTP 200 during cleanup on 18 October 2026.
These do not identify the deployed revision or verify API readiness, physical
microphones or the latest repository's public admission controls. Do not assume
latest GitHub code is deployed. No production changes are part of cleanup.

Use the existing-installation upgrade procedure below for that server. Never
initialize new secrets, change the Compose project name or replace its data/model
volumes as though it were a fresh installation. Deployment requires a separately
approved exact committed/pushed revision; never deploy a moving `main` reference.

## Configuration

Private API configuration belongs in the existing `/etc/dubguard/server.env`,
root-owned mode 0600, outside Git/build context. Do not loosen permissions to make
an unprivileged Compose invocation work. Compose interpolation (domain, server-env
path, model revision and network addresses) belongs in the operator's preserved
shell environment or an explicitly selected CLI `--env-file`. API `env_file`
settings do not themselves provide Compose interpolation.

| API setting | Purpose/default |
|---|---|
| `DUBGUARD_REVIEW_TOKENS_JSON` | JSON reviewer-ID → unique random bearer secret; at least 24 characters each; never distribute to anonymous judges |
| `DUBGUARD_DATA_DIR` | Private writable SQLite/audio path; Compose fixes `/home/dubguard/data` in `review_data` |
| `DUBGUARD_WHISPER_MODEL` | Existing cached directory; Compose fixes `/models/tiny.en`, offline/read-only |
| `DUBGUARD_SECONDARY_WHISPER_MODEL` | Optional distinct cached local model for independent acoustic recheck |
| `DUBGUARD_MAX_UPLOAD_BYTES`, `DUBGUARD_MAX_AUDIO_SECONDS` | Core defaults 25 MB / 1,200 seconds; new-install generator chooses 25 MB / 120 seconds; Quick Test always 10 MB / 60 seconds |
| `DUBGUARD_ASR_CHUNK_SECONDS`, `DUBGUARD_ASR_OVERLAP_SECONDS`, `DUBGUARD_ASR_CPU_THREADS` | Defaults 30 / 2 / 2; keep existing validated settings |
| `DUBGUARD_SEMANTIC_PROVIDER` | `disabled` for local-only; `amd` selects general hybrid transport; Quick Test also requires per-request mode/consent |
| `AMD_TOKEN_FACTORY_ENDPOINT`, `AMD_TOKEN_FACTORY_MODEL`, `AMD_TOKEN_FACTORY_API_KEY` | Server-only HTTPS endpoint, `DeepSeek-V4-Flash`, optional provider key; blank key leaves local analysis usable |
| `AMD_TOKEN_FACTORY_CONNECT_TIMEOUT_SECONDS`, `AMD_TOKEN_FACTORY_TIMEOUT_SECONDS`, `AMD_TOKEN_FACTORY_MAX_OUTPUT_TOKENS`, `AMD_TOKEN_FACTORY_MAX_RETRIES` | General defaults 5 / 40 / 1,024 / 2; generator chooses zero retries; Quick Test independently forces zero retries/one attempt |
| `AMD_TOKEN_FACTORY_AUDIO_MODEL`, `AMD_TOKEN_FACTORY_AUDIO_TIMEOUT_SECONDS`, `AMD_TOKEN_FACTORY_AUDIO_MAX_RETRIES` | Separate optional MiMo probe: `MiMo-V2.6-Flash` / 45 / 0; never invoked by the UI |

See [.env.example](.env.example) and [architecture](docs/ARCHITECTURE.md) for the
full evidence/transport boundaries. Never use a Vite variable for server keys.

### Demo admission and trusted proxy

| Variable | Safe default / purpose |
|---|---|
| `DUBGUARD_PUBLIC_LOCAL_DEMO` | `false`; private demo code still required. Only literal `true` enables public local admission. |
| `DUBGUARD_DEMO_ACCESS_CODE` | Existing independent private-session code, at least 24 characters; retained for private mode. |
| `DUBGUARD_AMD_DEMO_ACCESS_CODE` | Empty disables AMD demo access. New independent random secret, at least 24 characters, distinct from every reviewer token, private demo code and provider key. |
| `DUBGUARD_CLIENT_SESSIONS_PER_HOUR` | `4` session-creation attempts per client; bounded to 1–30. Failed/private-code attempts count. |
| `DUBGUARD_CLIENT_UPLOADS_PER_HOUR` | `6` admitted upload attempts per client; bounded to 1–90. Failed decodes and abandoned uploads count. |
| `DUBGUARD_TRUSTED_PROXIES` | Empty: ignore forwarded IPs. Set only Caddy's verified static IP `/32` (default Compose address `172.30.71.2/32`). Never trust all addresses. |
| `DUBGUARD_PROXY_SUBNET` | Compose interpolation variable; default `172.30.71.0/24`. Check for network conflicts first. |
| `DUBGUARD_CADDY_IP` | Compose interpolation variable; default `172.30.71.2`, inside the chosen subnet. Only Caddy is assigned this address. |
| `DUBGUARD_API_IP` | Compose interpolation variable; default `172.30.71.3`, distinct from Caddy and inside the chosen subnet. |

Compose interpolation values belong in the operator's existing Compose environment
or explicitly selected CLI `--env-file`; API settings belong in `server.env`.
Do not dump `docker compose config` or environment values; use `config --quiet`.

To add the separate AMD code without printing it, run this **on the server only
after approval**, as an operator with permission to edit the existing secret file:

```bash
sudo python3 - <<'PY'
from pathlib import Path
import os, secrets
p = Path('/etc/dubguard/server.env')
lines = p.read_text().splitlines()
key = 'DUBGUARD_AMD_DEMO_ACCESS_CODE='
existing = [s[len(key):] for s in lines if s.startswith(key)]
if any(existing):
    raise SystemExit('AMD demo code already configured; left unchanged')
lines = [s for s in lines if not s.startswith(key)]
lines.append(key + secrets.token_urlsafe(32))
tmp = p.with_name(p.name + '.update.tmp')
with tmp.open('x', opener=lambda path, flags: os.open(path, flags, 0o600)) as out:
    out.write('\n'.join(lines) + '\n')
tmp.replace(p)
PY
sudoedit /etc/dubguard/server.env
```

Use the private editor to retrieve/share that demo code privately. Do not paste it
into URLs, public screenshots, command flags or logs. A valid code alone never
initiates inference: the session capability and fresh request consent are also
required. Missing/invalid provider configuration returns unavailable before upload
parsing; local analysis stays available. No live AMD call is part of this runbook.

## Upgrade the existing DigitalOcean installation

### Frontend-only refinement release

This UI change does not require an API restart, migration, credential change or
model download. Use the narrower procedure below **only after the exact release
commit is approved and pushed**, and after confirming the deployed API is compatible
with the starting revision `3abb735db75261a4165d269a0d217054da7b4788`. If its deployed
revision is unknown or backend/configuration changes are pending, stop and use the
full upgrade procedure instead. No deployment was performed as part of refinement.

In the existing server checkout, define `dc` as the operator's **existing exact**
Compose invocation (same project name, files, overrides and interpolation env).
Use the same Docker privilege context throughout. `RELEASE_REVISION` and
`DEPLOYED_REVISION` below must be verified 40-character SHAs, not branch names.
`DUBGUARD_ORIGIN` is the existing HTTPS origin, without a trailing slash.

```bash
# Set these from the approved release and the existing deployment record.
: "${RELEASE_REVISION:?Set the approved pushed 40-character SHA}"
: "${DEPLOYED_REVISION:?Set the verified currently deployed SHA}"
: "${DUBGUARD_ORIGIN:?Set the existing HTTPS origin}"
test -z "$(git status --porcelain)" || exit 1
git fetch origin || exit 1
test "$(git rev-parse "$RELEASE_REVISION^{commit}")" = "$RELEASE_REVISION" || exit 1
# Any change here requires the full deployment procedure, not a web-only release.
git diff --quiet "$DEPLOYED_REVISION" "$RELEASE_REVISION" -- \
  src Dockerfile deploy requirements.txt requirements-audio.txt pyproject.toml \
  frontend/openapi.json frontend/src/generated-api.ts || exit 1
dc config --quiet || exit 1
WEB_CONTAINER="$(dc ps -q web)"
API_CONTAINER="$(dc ps -q api)"
test -n "$WEB_CONTAINER" && test -n "$API_CONTAINER" || exit 1
OLD_WEB_IMAGE="$(sudo docker inspect --format '{{.Image}}' "$WEB_CONTAINER")"
WEB_IMAGE_TAG="$(sudo docker inspect --format '{{.Config.Image}}' "$WEB_CONTAINER")"
test -n "$OLD_WEB_IMAGE" && test -n "$WEB_IMAGE_TAG" || exit 1
sudo docker image tag "$OLD_WEB_IMAGE" dubguard-web-rollback:pre-ux-refinement || exit 1
git checkout --detach "$RELEASE_REVISION" || exit 1
test "$(git rev-parse HEAD)" = "$RELEASE_REVISION" || exit 1
dc config --quiet || exit 1
dc build web || exit 1
# Brief web interruption; preserve API, review/audio/model and Caddy volumes.
dc up -d --no-deps --no-build web || exit 1
test "$(dc ps -q api)" = "$API_CONTAINER" || exit 1
curl --fail --silent --show-error "$DUBGUARD_ORIGIN/api/health" >/dev/null || exit 1
curl --fail --silent --show-error "$DUBGUARD_ORIGIN/test" >/dev/null || exit 1
curl --fail --silent --show-error "$DUBGUARD_ORIGIN/login" >/dev/null || exit 1
dc ps
```

Verify the served HTML references the new build's asset hashes, open desktop/mobile
pages, and inspect an existing authorized review without submitting a decision.
Do not submit AMD analyses or consume public-demo attempts as a deployment smoke
test. HTTP 200 alone does not prove that the new frontend is served. Keep rollback
values and the previous image until acceptance; do not prune images or volumes.

If the web check fails, use the same saved `dc`, `OLD_WEB_IMAGE` and `WEB_IMAGE_TAG`:

```bash
sudo docker image tag "$OLD_WEB_IMAGE" "$WEB_IMAGE_TAG" || exit 1
dc up -d --no-deps --no-build --force-recreate web || exit 1
test "$(dc ps -q api)" = "$API_CONTAINER" || exit 1
curl --fail --silent --show-error "$DUBGUARD_ORIGIN/api/health" >/dev/null
curl --fail --silent --show-error "$DUBGUARD_ORIGIN/test" >/dev/null
# Restore the checkout to its recorded previous revision after rollback acceptance.
git checkout --detach "$DEPLOYED_REVISION"
```

Never run `down -v`, recreate the API, change the project name, or initialize
secrets for a web-only update. The commands above preserve persisted audio and
review history. They intentionally leave server-specific values to the operator;
the local checkout cannot establish those values.

### Full application upgrade

1. Identify the **existing** checkout, Compose project name, Compose override files,
   actual API volume mounts, domain and environment-file path. Inspect container
   labels/mount names only, not their environment. Record the old Git SHA and old
   image IDs. Do not assume the project name is `dubguard`; changing it silently
   selects new empty volumes. Check `docker network ls` / network IPAM for conflicts
   with the new subnet and choose an unused subnet/address if needed.
2. Set `RELEASE_REVISION` to the exact approved 40-character new SHA. In the existing
   clean checkout, fetch and check out that revision detached. Verify
   `test "$(git rev-parse HEAD)" = "$RELEASE_REVISION"`. Keep the old images tagged
   for rollback. Build API/web images while the old containers continue serving.
   Do not run cache-model setup or download a model for this update.
3. Keep `DUBGUARD_PUBLIC_LOCAL_DEMO=false`. Add the new settings privately. Use the
   existing Compose project/config arguments for every command below. Define `dc`
   as the operator's exact existing Compose invocation; preserve domain, model
   revision, server-env path and any subnet interpolation values through sudo.
   Run `dc config --quiet` and `dc build api web`. Builds do not update the server.
4. Schedule a short write-maintenance interval. `dc stop api` waits up to the
   configured graceful shutdown period (100 seconds); one API instance only.
   Leave the web container and Caddy certificate volumes intact. With the API
   stopped, back up the **entire actual review_data volume**, including SQLite,
   journal/WAL files, original audio, review records and quick accounting. Use a
   root-only backup directory and verify archive integrity and a restore copy
   before allowing any migration. Also securely back up the server environment
   and record the Caddy volume names. This is the consistent pre-migration backup.
5. Example backup commands after determining the actual volume name and existing
   stopped API image (replace the placeholders with inspected values):

   ```bash
   BACKUP_DIR="/var/backups/dubguard/$(date -u +%Y%m%dT%H%M%SZ)"
   sudo install -d -m 700 "$BACKUP_DIR"
   # OLD_API_IMAGE is the old local image ID. No image pull or live API is needed.
   sudo docker run --rm --network none --user 0 --entrypoint python \
     --mount "type=volume,src=$REVIEW_VOLUME,dst=/source,readonly" \
     --mount "type=bind,src=$BACKUP_DIR,dst=/backup" "$OLD_API_IMAGE" -c \
     'import tarfile; t=tarfile.open("/backup/review-data.tar.gz","w:gz"); t.add("/source",arcname="review-data"); t.close()'
   sudo chmod 600 "$BACKUP_DIR/review-data.tar.gz"
   sudo tar -tzf "$BACKUP_DIR/review-data.tar.gz" >/dev/null
   sudo sha256sum "$BACKUP_DIR/review-data.tar.gz" | sudo tee "$BACKUP_DIR/review-data.sha256" >/dev/null
   # Test extraction to a separate scratch directory; never extract over the
   # active volume to test the backup.
   sudo install -m 600 /etc/dubguard/server.env "$BACKUP_DIR/server.env"
   ```

6. The Compose network now gives Caddy a stable address. If the existing Compose
   network must be recreated to apply IPAM, `dc down` **without `-v`**, after the
   backup, removes containers/network only. This causes a brief planned outage;
   it preserves named volumes and certificates. Then `dc up -d api web` recreates
   exactly one API against the **same** volumes. If no network change is needed,
   `dc up -d --no-deps --force-recreate api web` suffices. Never use
   `docker compose down -v`, volume prune, or a new project name. There is no
   zero-downtime guarantee on this single-instance deployment.
7. Verify `/api/health`, `/api/ready`, HTTPS certificate/redirect, `/test`, `/login`,
   `/review` authentication, static assets, Caddy headers/CSP, microphone permission,
   policy/review history, audio hashes and current sign-off restrictions. Anonymous
   GET of session/audio and DELETE must return 401. `/api/quick/config` must show
   public access false. Confirm one API process and persistent old review IDs.
8. Make a short **real local recording** in the browser, preview/download it and
   compare original bytes/format. Submit local verification only. Confirm expiry,
   quotas, protected audio retrieval, refresh and deletion. Test that AMD is
   restricted without its separate code; do not authorize/send a real AMD request.
9. Only after the [local security/resource tests](docs/EVALUATION.md#tests-and-browser-captures) and these
   deployment checks pass may the operator explicitly enable
   `DUBGUARD_PUBLIC_LOCAL_DEMO=true`. Set the verified Caddy IP `/32` trust entry
   first; with no trusted proxy all visitors conservatively share Caddy's client
   bucket. Recreate **only the API** using the same volumes; test separate-client
   rate accounting and spoofed X-Forwarded-For rejection through HTTPS. The Caddy
   proxy overwrites incoming forwarded IP values; Uvicorn proxy-header rewriting
   is disabled. Do not expose API port 8000.
10. If validation fails, turn public mode off and restore old image versions and
    old Compose/network configuration. The accounting migration is additive;
    preserve the current volume rather than automatically restoring over newer
    review data. If database restoration is necessary, stop the API and reconcile
    every post-backup review/audio write first. Test rollback on a copy. Never
    delete a production volume as a rollback shortcut.

The shared CPU demo is bounded, not a distributed denial-of-service protection
service. Shared NAT users share client limits; global 20 active sessions, 30 hourly
admissions, 2 jobs, 2 uploads, 60 seconds/10 MB per recording, 3 attempts/session,
2 AMD attempts/session and 1 AMD demo call remain enforced. Do not scale API
workers/replicas without replacing in-process locks with a shared admission system.

## New installation only

Use Ubuntu 24.04, Docker Engine with Compose v2.24.4+, Git and Python 3.
A CPU x86-64 server around 4 vCPUs / 8 GB / 80 GB is a starting configuration,
not a measured capacity guarantee. No GPU is required. Install Docker using its
[official Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/).
Use a controlled hostname/DNS A record, correct IPv6/AAAA if present, reachable
TCP 80/443 and optional UDP 443; restrict SSH and never expose port 8000.
Caddy terminates HTTPS and serves API/SPA on one origin. Browser recording needs
HTTPS or localhost. Keep certificate volumes persistent.

These Bash commands apply only to a new authorized server. Set an exact approved
release SHA containing the desired deployment files; no historical SHA is a
substitute for release review.

```bash
git clone https://github.com/Eshuredd/DubGuard.git
cd DubGuard
export RELEASE_REVISION='REPLACE_WITH_APPROVED_40_CHARACTER_SHA'
git checkout --detach "$RELEASE_REVISION"
test "$(git rev-parse HEAD)" = "$RELEASE_REVISION"
unset DUBGUARD_SERVER_ENV DUBGUARD_LOCAL_PORT
export DUBGUARD_DOMAIN='dubguard.your-domain.example'
export DUBGUARD_WHISPER_REVISION='0d3d19a32d3338f10357c0889762bd8d64bbdeba'
sudo install -d -m 700 /etc/dubguard
sudo python3 deploy/create_env.py /etc/dubguard/server.env
sudoedit /etc/dubguard/server.env
```

The generator refuses to overwrite existing files and creates distinct reviewer,
private-demo and AMD-demo secrets. Retrieve/distribute only the relevant code
privately. Add an AMD key only if paid inference is intended; never show secrets
in command flags, URLs, screenshots or logs. Public local mode stays false by
default. Configure the verified Caddy `/32` before enabling it.

```bash
dc() { sudo --preserve-env=DUBGUARD_DOMAIN,DUBGUARD_WHISPER_REVISION,DUBGUARD_SERVER_ENV,DUBGUARD_PROXY_SUBNET,DUBGUARD_CADDY_IP,DUBGUARD_API_IP docker compose -p dubguard -f deploy/compose.yaml "$@"; }
dc config --quiet
dc build api web cache-model
# Explicit public-weight download/load, not AMD inference; new installations only.
dc --profile setup run --rm --no-deps cache-model
dc up -d api web
dc ps
python3 deploy/smoke.py "https://$DUBGUARD_DOMAIN"
```

`--quiet` avoids rendering environment secrets. The setup profile downloads pinned
tiny.en into `dubguard_whisper_models`; runtime mounts it read-only with
`HF_HUB_OFFLINE=1`. The backend image includes FFmpeg/ffprobe/libgomp and runs as
UID 10001. `.dockerignore` allowlists build inputs and excludes private data.
`/api/health` is liveness; `/api/ready` needs dependencies, FFmpeg and model files.
Readiness does not prove speech accuracy or AMD service availability. Verify a
real consenting recording separately using [the recording guide](docs/RECORDING_GUIDE.md).

## Local container validation

Use disposable configuration with a **blank AMD key**; never copy the real `.env`.
The full recovery harness is intentionally fixed to project `dubguard-phase5`.
Confirm that name belongs only to disposable tests before using it; use a separate
Docker environment if an unrelated project already owns it. The generator below
refuses to overwrite an existing configuration. Do not erase old data to rerun.

From the repository root in PowerShell (Docker Desktop Linux engine/Compose
v2.24.4+, frontend dependencies and desktop Chrome required):

```powershell
New-Item -ItemType Directory -Force .dubguard-data/container-validation | Out-Null
.venv/Scripts/python deploy/create_env.py .dubguard-data/container-validation/server.env
$env:DUBGUARD_SERVER_ENV = (Resolve-Path .dubguard-data/container-validation/server.env).Path
$env:DUBGUARD_CONTAINER_ENV = $env:DUBGUARD_SERVER_ENV
$env:DUBGUARD_DOMAIN = 'http://localhost:8080'
$env:DUBGUARD_WHISPER_REVISION = '0d3d19a32d3338f10357c0889762bd8d64bbdeba'
function dcl { docker compose -p dubguard-phase5 -f deploy/compose.yaml -f deploy/compose.local.yaml @args }
dcl config --quiet
dcl build api web cache-model
dcl --profile setup run --rm --no-deps cache-model
dcl up -d api web
.venv/Scripts/python deploy/smoke.py http://127.0.0.1:18080
.venv/Scripts/python deploy/validate_local.py --env-file $env:DUBGUARD_SERVER_ENV --output reports/local/container_smoke.json
npm --prefix frontend run test:container
dcl exec -T api python -m pip check
dcl exec -T web caddy validate --config /etc/caddy/Caddyfile
dcl down
```

Only `127.0.0.1:18080` is published. Model setup is an explicit download; skip it
only when this test project's pinned model cache is already validated. No runtime
request downloads weights. `down` retains named test volumes. On Linux use the
same commands with `.venv/bin/python`, `mkdir -p`, and this shell setup:

```bash
export DUBGUARD_SERVER_ENV="$PWD/.dubguard-data/container-validation/server.env"
export DUBGUARD_CONTAINER_ENV="$DUBGUARD_SERVER_ENV"
export DUBGUARD_DOMAIN='http://localhost:8080'
export DUBGUARD_WHISPER_REVISION='0d3d19a32d3338f10357c0889762bd8d64bbdeba'
dcl() { docker compose -p dubguard-phase5 -f deploy/compose.yaml -f deploy/compose.local.yaml "$@"; }
```

The harness checks same-origin routing/assets, CSP, real CPU ASR on generated
silence, blocked sign-off, SQLite/audio persistence through stop/start/recreation,
seeded interrupted-job recovery and unchanged read-only/offline model hashes.
Seeded pending states do not represent an actual mid-inference crash. Silence does
not measure speech accuracy. The container browser test exercises the actual
production bundle separately from stubbed development-server E2E.

### Local public-admission protocol

`deploy/validate_public.py` is localhost-only and writes temporary session
capabilities to its private `--state` file. It expects a fresh disposable data
volume, `DUBGUARD_PUBLIC_LOCAL_DEMO=true`, trusted Caddy `172.30.71.2/32`, default
four sessions/hour and a blank AMD key. Use a separate temporary Compose override
for that data volume and settings; do not run it against production or reuse the
private smoke DB with spent quotas. After readiness:

```powershell
.venv/Scripts/python deploy/validate_public.py --state .dubguard-data/container-validation/public-state.json --output reports/local/container-public.json
# Restart only that isolated test API, then wait for /api/ready again.
.venv/Scripts/python deploy/validate_public.py --state .dubguard-data/container-validation/public-state.json --output reports/local/container-public.json --after-restart
```

The second pass deletes the test sessions and private state file after verifying
quota/audio persistence. It checks anonymous audio/delete rejection, forwarded-IP
spoof rejection, oversized bodies and AMD unavailability before parsing. It makes
no paid request. [Historical receipts](docs/EVALUATION.md#tests-and-browser-captures)
are evidence of past local execution, not assertions about this server.

## Local CPU smoke without Docker

Install `requirements-audio.txt`, cache the model as in the [README](README.md#run-locally),
and run from PowerShell:

```powershell
.venv/Scripts/python scripts/cpu_smoke.py --model-path .dubguard-data/models/tiny.en --output reports/local/cpu_smoke.json
$env:DUBGUARD_WHISPER_MODEL = (Resolve-Path .dubguard-data/models/tiny.en).Path
.venv/Scripts/python -m uvicorn dubguard.api:app --host 127.0.0.1 --port 8000
```

Set the separate private demo/reviewer configuration before opening the UI.
PyAV 18.1.0 is deliberately pinned for faster-whisper 1.2.1 compatibility.

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

For backups and rollback use the existing-installation procedure above: stop
the API, back up the actual complete review volume (SQLite/WAL, audio and accounting),
verify a restore copy, and retain private configuration/certificate state. Restart
and verify readiness afterward. Restore data/audio consistently only after
reconciling post-backup writes; never use volume deletion as rollback.

For long-term production add managed identities/roles, durable workers, distributed
admission control, monitored retention and stronger audit storage before expanding
beyond the controlled demo. The shared-token/SQLite implementation does not certify
safety or provide a multi-tenant production review system.
