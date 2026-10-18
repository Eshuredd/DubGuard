# Phase 6A — Existing DigitalOcean update runbook

Preparation only. **Do not execute until the changes are reviewed, an exact new
revision is committed/pushed with approval, and deployment is explicitly approved.**
The current server remains available during local development. The local starting
SHA is `9e1c855d3a13667fd34a91da90da2d0e9d032254`; it does not contain these changes.
There is no new release SHA yet. Never deploy a moving `main` reference.

## Configuration and boundaries

Keep secrets only in the existing `/etc/dubguard/server.env` (mode 0600), outside
Git, the frontend build and the Docker build context. Preserve all existing
reviewer identities, database/audio paths, ASR configuration and provider key.
Do not run `create_env.py` against an existing installation.

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
tmp = p.with_name(p.name + '.phase6.tmp')
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

## Update with preserved data

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
9. Only after the local security/resource tests in the redesign report and these
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
