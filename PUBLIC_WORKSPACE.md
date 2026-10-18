# Public custom reviews — local implementation handoff

Starting revision: `8a471ce6496e57396b2739e1ea584b143c5e347f` (clean at start).
No commit, push, deployment, production data change or live AMD call was made.

## User journey and isolation

`/test` keeps the six samples and links to **Create Your Own Review**. `/workspace`
opens an editable custom workspace immediately, without login or policy IDs.
Visitors enter a title and reference instructions, add supported number/polarity/
warning/order requirements and optional alternative wording, save a Demo Policy,
then record/upload and explicitly analyze. Requirements use the existing validated
schemas and verification engine. Nothing is presented as organizational approval.

Original playback/download, provisional ASR, source spans, visitor corrections,
reviewed findings, notes, demo decisions and JSON evidence export are supported.
Corrections require a listening attestation and reason, preserve raw ASR, validate
instruction/timing/audio-hash integrity, and rerun actual local rules. Changed
references or recordings invalidate review acknowledgements. Critical deviations
and unresolved evidence remain visible. A demo decision never creates approval,
authenticated reviewer identity, release authorization or a ReviewStore record.

Custom and sample sessions share Quick Test's random 256-bit capabilities,
30-minute fixed expiry, cleanup, HMAC client accounting, 20 active sessions,
30 global hourly admissions, 3 analyses/session, 10 MB/60-second audio limits,
two processing slots and two admitted uploads (one per client). SQLite adds only
`scope` and `custom` columns; existing sessions default to sample scope. A capability
can access only its own scope/data. There are no public record IDs/list/admin or
genuine approval endpoints. Deletion/expiry/restart retain admission accounting.

The early admission middleware and Caddy now cover custom uploads and 32 KiB JSON
mutations. References are bounded to 12 instructions, 30 constraints and 12,000
characters including alternatives; corrections to 50 segments/12,000 characters;
notes to 2,000 characters. Each session allows 30 metadata changes and retains up
to 20 demo activity descriptions. All state changes use optimistic revisions.
Existing trusted-proxy handling, body deadlines and runtime locks remain shared.

## Privileged access and AMD

`/operator` is the separate private entry. Existing `/review`, `/policies` and
bearer-authenticated API clients retain their protected behavior. Operator UI
login exchanges the credential for a random expiring HttpOnly, SameSite=Strict
cookie (Secure outside localhost). Only its digest is persisted. Logout, expiry
and reviewer-configuration rotation revoke it; cookie mutations check origin.
The frontend stores only a non-secret signed-in hint, never the reviewer key.
Old tab-stored reviewer keys are removed on navigation. Sign-off rules are unchanged.

Custom workspaces deliberately support **local verification only**. Attempts to
select AMD directly are rejected before multipart parsing. Quick Test retains its
separate AMD code, fresh consent, two-run quota, single AMD slot, zero retries,
model provenance and exact citation checks. Audio is never sent to DeepSeek.

## Configuration and safe DigitalOcean update

New settings: `DUBGUARD_PUBLIC_WORKSPACE=false` (disabled by default),
`DUBGUARD_CLIENT_EDITS_PER_HOUR=60` (hard ceiling 120), and
`DUBGUARD_OPERATOR_LOGINS_PER_HOUR=8` (ceiling 30). Operator login attempts have a
separate client bucket. Existing public creation/upload budgets remain 4/6 hourly
by default and are shared between sample/custom workspaces.

After explicit approval, use [the existing data-preserving runbook](DEPLOYMENT.md):

1. Approve, commit/push and pin the **new exact SHA**; none exists for these edits yet.
   Preserve the existing Compose project name, paths, named volumes and certificates.
2. Build while old containers serve. Keep the new flag false. Stop the single API
   for a consistent full-volume SQLite/audio backup, verify a restore copy, and
   retain old images/configuration. Never use `down -v` or run the new-install secret
   generator against the existing server environment.
3. Start one API instance against the same volumes. Validate additive migration
   (`sessions.scope`, `sessions.custom`), preserved private review IDs/audio hashes,
   operator cookie login/logout, sign-off restrictions and invalid public capabilities.
   Check HTTPS, `/api/health`, `/api/ready`, `/test`, `/workspace`, `/operator`, Caddy
   headers/body limits and trusted Caddy `/32`. Existing operators sign in again;
   their configured server credentials do not change.
4. After isolation/resource tests and a real browser recording check, explicitly
   enable only `DUBGUARD_PUBLIC_WORKSPACE=true` in the private server env and recreate
   the API. This flag is independent of Quick Test's private/public admission mode.
   Verify independent custom sessions, limits, deletion and local-only analysis.
   Do not change production AMD settings or run a real AMD request.
5. Roll back by disabling the flag and restoring old images/configuration, preserving
   volumes. Additive columns are compatible with old code. Stop writes and reconcile
   any post-backup records before a necessary data restore; never overwrite newer
   organizational evidence blindly. No schema downgrade or volume deletion is needed.

## Verification and remaining limits

Results and screenshots are under `reports/local/public-workspace/` (ignored local
artifacts). Screenshots carry synthetic-audio/stub-ASR/mock-AMD labels; the separate
container capture uses real CPU Whisper on generated silence. No speech accuracy
or human ground-truth claim is made. Executed checks: **359 backend tests, 28 frontend
unit tests, 13 main Chrome tests, 1 separately enabled public-sample Chrome test and
2 production-container Chrome tests passed**. TypeScript, production builds,
Compose/Caddy validation, pip dependency checks, npm audit (0 vulnerabilities),
credential artifact checks and `git diff --check` passed. Captured desktop/mobile
states had zero axe WCAG A/AA violations. `backend.xml` contains backend results.

Physical microphones and Safari/iOS remain unverified. Anonymous attestations are
untrusted demonstration evidence. The workspace is a temporary, single-instance,
English/single-speaker demo, not persistent organizational collaboration. Custom
AMD review is unavailable; the protected sample AMD flow remains available where
configured. Shared NAT clients share limits. Public access remains off until the
operator explicitly enables it after deployment validation.
