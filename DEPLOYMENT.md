# Deployment and operations

The existing DigitalOcean installation is at
[DubGuard](https://134-209-145-248.sslip.io/). The reported host is Ubuntu 24.04,
4 vCPUs / 8 GB. The deployed Git SHA is not recorded in this checkout. Historical
HTTP 200 observations establish reachability only; verify the running image and
release record before choosing an upgrade procedure. Cleanup does not access or
modify the running server.

Use the existing project, environment, volumes and credentials for upgrades.
Never initialize an existing installation as a new one. Deploy only an approved,
pushed exact commit, with backups and retained rollback images.

## Configuration

Both `/test` and `/workspace` allow temporary local reviews without login or
access codes, within server limits. Optional public AMD requires the provider,
enable switch and quotas below. Private reviewers use `/operator/login` or
`/operator`; the public navigation contains only Try a Sample and Create a Review.
Operator credentials are exchanged for expiring HttpOnly cookies. Authentication,
policy approval, audit history and sign-off remain protected; see
[trust boundaries](docs/ARCHITECTURE.md#public-sessions-and-private-reviewers).

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
| `DUBGUARD_PUBLIC_AMD_ENABLED` | `false`; set `true` only after quota tests pass and the release is approved. Emergency stop: set `false` and recreate the API with the preserved Compose invocation. |
| `DUBGUARD_AMD_REQUESTS_PER_HOUR` | `10`, rolling hour, shared by all public flows; ceiling 100; zero stops admission. |
| `DUBGUARD_AMD_REQUESTS_PER_DAY` | `40`, rolling 24 hours, persisted in SQLite across restart; ceiling 1000; zero stops admission. |
| `DUBGUARD_AMD_CLIENT_REQUESTS_PER_DAY` | `4`, rolling 24 hours for both signed browser and HMAC network buckets; ceiling 20; zero stops admission. |
| `DUBGUARD_CLIENT_SESSIONS_PER_HOUR` | `4` session-creation attempts per client; bounded to 1–30. Failed attempts count. |
| `DUBGUARD_CLIENT_UPLOADS_PER_HOUR` | `6` admitted upload attempts per client; bounded to 1–90. Failed decodes and abandoned uploads count. |
| `DUBGUARD_TRUSTED_PROXIES` | Empty: ignore forwarded IPs. Set only Caddy's verified static IP `/32` (default Compose address `172.30.71.2/32`). Never trust all addresses. |
| `DUBGUARD_PROXY_SUBNET` | Compose interpolation variable; default `172.30.71.0/24`. Check for network conflicts first. |
| `DUBGUARD_CADDY_IP` | Compose interpolation variable; default `172.30.71.2`, inside the chosen subnet. Only Caddy is assigned this address. |
| `DUBGUARD_API_IP` | Compose interpolation variable; default `172.30.71.3`, distinct from Caddy and inside the chosen subnet. |

Compose interpolation values belong in the operator's existing Compose environment
or explicitly selected CLI `--env-file`; API settings belong in `server.env`.
Do not dump `docker compose config` or environment values; use `config --quiet`.

### Public AMD inference

Sample and custom AMD review require fresh consent, with no public access code,
login or reviewer authorization. The old AMD demo code is ignored; remove its
obsolete entry using the existing private editor. Preserve reviewer credentials,
provider keys, the accounting secret and all data volumes.

Before release, run `pytest tests/test_public_amd.py tests/test_phase4.py
tests/test_phase6.py tests/test_workspace.py` and the complete regression suite.
Tests use mocked HTTP only. Leave `DUBGUARD_PUBLIC_AMD_ENABLED=false` until these
checks pass. No paid call is authorized by this runbook.

Use `sudoedit /etc/dubguard/server.env` on the approved server to configure the
four controls in the table and the existing private `AMD_TOKEN_FACTORY_API_KEY`,
HTTPS `AMD_TOKEN_FACTORY_ENDPOINT`, and exact `AMD_TOKEN_FACTORY_MODEL=DeepSeek-V4-Flash`.
No secret belongs in frontend variables, command flags, logs or screenshots.
Use the full application upgrade below, including the stopped-API volume backup,
with the existing project name, volumes and pinned approved release SHA. This is
a backend release with an additive `amd_attempts` table, not a frontend-only update.

After approval and successful quota validation, set the switch to `true` and
run `dc up -d --no-deps --force-recreate api` using the existing preserved `dc`
invocation. Check `/api/quick/config` and `/api/workspace/config`: `amd_available`
must be true when configuration and global budgets permit. These endpoints inspect
configuration/accounting only and never call AMD. This proves local readiness,
not provider reachability; a live inference check requires separate authorization.

Emergency stop: set `DUBGUARD_PUBLIC_AMD_ENABLED=false` in the private server env
and recreate the API with the same command. Do not change the reviewer credential
or delete accounting. A request already sent may finish and be billed. There is
no browser switch capable of overriding the server control.

Admission takes a SQLite `BEGIN IMMEDIATE` write transaction before scheduling
work. Global and client budgets and the session's two-AMD-attempt limit reserve
together. Reservations include failed decoding, ASR errors, provider failures and
timeouts; no refund occurs after session deletion or process restart. Old AMD
events expire after 24 hours. Browser IDs are signed, random, HttpOnly,
SameSite=Strict cookies expiring after 24 hours; network identifiers are HMACs,
never stored raw. Both limits must pass, so clearing cookies or recreating sessions
does not reset the network budget. Shared NAT users share the network bucket.
This bounds abuse rather than identifying people; distributed clients remain
bounded by the global budget. Keep exactly one API process/replica.

The public transport forces zero retries, a 40-second HTTP read/write timeout,
1,024 maximum output tokens and a conservative 32,768 input-token ceiling
(UTF-8 content bytes plus framing allowance). Oversized text is rejected without
truncating source evidence. Only script, policy and transcript text leave the
server; local deterministic results survive remote failures. HTTP 429 includes
`Retry-After`; Local Verification remains available within its own limits.

Monitor counts without reading client identifiers or secret configuration:

```bash
dc exec -T api python - <<'PY'
from dubguard.quick import database
import time
with database() as db:
    now = time.time()
    for name, seconds in [('hour', 3600), ('day', 86400)]:
        count = db.execute('SELECT count(*) FROM amd_attempts WHERE created>?', (now-seconds,)).fetchone()[0]
        print(name, count)
PY
```

Counts are admitted attempts, not billed usage. Inspect model-reported usage and
errors in consented session reports, and reconcile billing privately with the AMD
account. Never export provider keys or raw transport error bodies. Back up the
whole existing volume with API stopped; rollback preserves the additive table
and post-backup writes. Do not restore an older quota database to reset allowance.

## Upgrade the existing DigitalOcean installation

### Frontend-only update

Use this procedure for a frontend-only release after confirming that the
deployed API matches the release's backend and contracts. If the deployed revision
is unknown, or any backend/deployment configuration differs, use the full upgrade
below. Documentation and unused CSS removal require no database migration,
credential rotation or model download. No update is executed by this guide.

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
sudo docker image tag "$OLD_WEB_IMAGE" dubguard-web-rollback:before-update || exit 1
git checkout --detach "$RELEASE_REVISION" || exit 1
test "$(git rev-parse HEAD)" = "$RELEASE_REVISION" || exit 1
dc config --quiet || exit 1
dc build web || exit 1
# Brief web interruption; preserve API, review/audio/model and Caddy volumes.
dc up -d --no-deps --no-build web || exit 1
test "$(dc ps -q api)" = "$API_CONTAINER" || exit 1
curl --fail --silent --show-error "$DUBGUARD_ORIGIN/api/health" >/dev/null || exit 1
curl --fail --silent --show-error "$DUBGUARD_ORIGIN/test" >/dev/null || exit 1
curl --fail --silent --show-error "$DUBGUARD_ORIGIN/operator/login" >/dev/null || exit 1
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

This procedure updates **API and web**, including persistent accounting when an
approved release adds it. Execute only after approval, commit and push. Use the existing server
checkout and inspect its running containers' Compose project labels and mounts
first. The values below must come from that installation; never guess a new project
or volume. Preserve all existing Compose overrides and interpolation settings.
Local workflows need no activation flag. Public AMD remains controlled by
`DUBGUARD_PUBLIC_AMD_ENABLED`; do not enable it until quota tests pass. Preserve
existing reviewer/provider credentials and accounting data.

Run the following in Bash from the existing clean checkout. Define `dc` as the
**same existing Compose command**, including `-p`, every `-f`/`--env-file`, and
the existing Docker privilege context. For a standard installation its form is
`dc() { sudo --preserve-env=DUBGUARD_DOMAIN,DUBGUARD_SERVER_ENV,DUBGUARD_WHISPER_REVISION,DUBGUARD_PROXY_SUBNET,DUBGUARD_CADDY_IP,DUBGUARD_API_IP docker compose -p "$PROJECT" -f deploy/compose.yaml "$@"; }`.
Use that form only after confirming it matches the running installation. Do not
print expanded Compose environment configuration or regenerate `server.env`.

```bash
set -euo pipefail
# Set from the approved release and inspected deployment, not a moving branch.
: "${RELEASE_REVISION:?Set the approved pushed 40-character Git SHA}"
: "${PROJECT:?Set the existing Compose project name}"
: "${SERVER_ENV:?Set the existing private server.env absolute path}"
export DUBGUARD_SERVER_ENV="$SERVER_ENV"
ORIGIN='https://134-209-145-248.sslip.io'
declare -F dc >/dev/null
test -z "$(git status --porcelain)"
dc config --quiet
API_ID="$(dc ps -q api)"
WEB_ID="$(dc ps -q web)"
test -n "$API_ID" && test -n "$WEB_ID"
test "$(sudo docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$API_ID")" = "$PROJECT"
OLD_REVISION="$(git rev-parse HEAD)"
OLD_API_IMAGE="$(sudo docker inspect -f '{{.Image}}' "$API_ID")"
OLD_WEB_IMAGE="$(sudo docker inspect -f '{{.Image}}' "$WEB_ID")"
API_IMAGE_TAG="$(sudo docker inspect -f '{{.Config.Image}}' "$API_ID")"
WEB_IMAGE_TAG="$(sudo docker inspect -f '{{.Config.Image}}' "$WEB_ID")"
REVIEW_VOLUME="$(sudo docker inspect -f '{{range .Mounts}}{{if eq .Destination "/home/dubguard/data"}}{{if eq .Type "volume"}}{{.Name}}{{end}}{{end}}{{end}}' "$API_ID")"
test -n "$REVIEW_VOLUME"  # Stop here if this installation uses a bind mount.
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
sudo docker image tag "$OLD_API_IMAGE" "dubguard-api-rollback:$STAMP"
sudo docker image tag "$OLD_WEB_IMAGE" "dubguard-web-rollback:$STAMP"

git fetch origin
test "$(git rev-parse "$RELEASE_REVISION^{commit}")" = "$RELEASE_REVISION"
git checkout --detach "$RELEASE_REVISION"
test "$(git rev-parse HEAD)" = "$RELEASE_REVISION"
dc config --quiet
dc build api web                  # Old application still serves during build.

dc stop api                      # Begin short maintenance; one API only.
BACKUP_DIR="/var/backups/dubguard/$STAMP"
sudo install -d -m 700 "$BACKUP_DIR" "$BACKUP_DIR/restore-check"
sudo install -m 600 "$SERVER_ENV" "$BACKUP_DIR/server.env"
sudo docker inspect -f '{{range .Mounts}}{{println .Type .Name .Destination}}{{end}}' "$WEB_ID" \
  | sudo tee "$BACKUP_DIR/web-mounts.txt" >/dev/null
sudo docker run --rm --network none --user 0 --entrypoint python \
  --mount "type=volume,src=$REVIEW_VOLUME,dst=/source,readonly" \
  --mount "type=bind,src=$BACKUP_DIR,dst=/backup" "$OLD_API_IMAGE" -c \
  'import tarfile; t=tarfile.open("/backup/review-data.tar.gz","w:gz"); t.add("/source",arcname="review-data"); t.close()'
sudo chmod 600 "$BACKUP_DIR/review-data.tar.gz"
sudo tar -tzf "$BACKUP_DIR/review-data.tar.gz" >/dev/null
sudo sha256sum "$BACKUP_DIR/review-data.tar.gz" \
  | sudo tee "$BACKUP_DIR/review-data.sha256" >/dev/null
sudo tar -xzf "$BACKUP_DIR/review-data.tar.gz" -C "$BACKUP_DIR/restore-check"
# Verify every restored SQLite DB on the scratch copy; never migrate the original backup.
sudo docker run --rm --network none --user 0 --entrypoint python \
  --mount "type=bind,src=$BACKUP_DIR/restore-check,dst=/check" "$OLD_API_IMAGE" -c \
  'from pathlib import Path; import sqlite3; files=[p for p in Path("/check").rglob("*") if p.is_file() and p.suffix in (".db",".sqlite",".sqlite3")]; assert files, "No SQLite backup found"; checks=[sqlite3.connect(str(p)).execute("PRAGMA integrity_check").fetchone()[0] for p in files]; assert all(v=="ok" for v in checks), checks; print("Restored SQLite integrity checks passed")'

# Existing network and named volumes are retained, including both Caddy volumes.
dc up -d --no-deps --no-build --force-recreate api web
test "$(dc ps -q api | wc -l)" -eq 1
NEW_API_ID="$(dc ps -q api)"
test "$(sudo docker inspect -f '{{range .Mounts}}{{if eq .Destination "/home/dubguard/data"}}{{.Name}}{{end}}{{end}}' "$NEW_API_ID")" = "$REVIEW_VOLUME"
for attempt in $(seq 1 60); do
  if curl --fail --silent --show-error "$ORIGIN/api/ready" >/dev/null; then break; fi
  sleep 2
done
curl --fail --silent --show-error "$ORIGIN/api/health"
curl --fail --silent --show-error "$ORIGIN/api/ready"
curl --fail --silent --show-error "$ORIGIN/test" >/dev/null
curl --fail --silent --show-error "$ORIGIN/workspace" >/dev/null
curl --fail --silent --show-error "$ORIGIN/api/quick/config"
curl --fail --silent --show-error "$ORIGIN/api/workspace/config"
test "$(curl --silent --output /dev/null --write-out '%{http_code}' "$ORIGIN/api/workspace/session")" = 401
test "$(curl --silent --output /dev/null --write-out '%{http_code}' "$ORIGIN/api/workspace/audio")" = 401
test "$(curl --silent --output /dev/null --write-out '%{http_code}' "$ORIGIN/api/review/workflows")" = 401
dc ps
```

Before acceptance, confirm the deployed asset hashes, HTTPS, preserved private
review IDs/audio hashes, sign-off blocks and trusted Caddy address. In two separate
browser contexts, complete a sample and a custom local review, preview/download
the original, inspect evidence, export a temporary decision, and confirm isolation
and deletion. Check real microphone permission/recording. No AMD request is needed.
Both config responses must report local public availability; AMD availability
depends on its configuration, switch and remaining quota.
Keep existing data/model/Caddy volumes and the backups; never use `down -v`.

If validation fails, retain the same shell variables and roll back images:

```bash
dc stop api
sudo docker image tag "$OLD_API_IMAGE" "$API_IMAGE_TAG"
sudo docker image tag "$OLD_WEB_IMAGE" "$WEB_IMAGE_TAG"
git checkout --detach "$OLD_REVISION"
dc up -d --no-deps --no-build --force-recreate api web
curl --fail --silent --show-error "$ORIGIN/api/ready"
```

Roll back with the current volume; reconcile any post-backup writes before any
separate data restore. If the running installation has a different mount path,
bind mount or network configuration, adapt the inspected values using the full
procedure below before stopping it. Do not substitute an empty volume.

If a release changes network IPAM or Caddy's address, plan that migration separately
after the backup. Verify the configured subnet is unused and trust only Caddy's
specific address; never expose API port 8000. Keep the same volume mounts and
Compose project. Bind-mounted deployments need an equivalent stopped-API backup
of the actual host path before using this procedure. Never substitute an empty
volume or restore over post-backup review writes without reconciling them.

The demo enforces 20 active sessions, 30 global hourly admissions, two processing
jobs, two uploads (one per client), 60 seconds/10 MB per recording, three attempts
per session, two AMD attempts per session and one concurrent public AMD call.
Hourly/daily/client AMD budgets persist independently of session deletion.
Shared NAT clients share a network bucket. Do not add API workers/replicas or
overlap old/new instances against the same SQLite files.

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

The generator refuses to overwrite existing files and creates reviewer credentials.
Retrieve/distribute the reviewer credential
privately. Add an AMD key only if paid inference is intended; never show secrets
in command flags, URLs, screenshots or logs. Both public local workflows are
available immediately. Configure the verified Caddy `/32` before opening access.

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
volume, trusted Caddy `172.30.71.2/32`, default
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

Local public reviews need no access configuration. Set private reviewer credentials
only for organizational workflows; AMD analysis requires fresh consent and the public inference switch/budgets.
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
