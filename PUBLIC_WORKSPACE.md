# Public custom reviews — local implementation handoff

Access-barrier removal starts from `8be42ec77be6e79d39728a4e753e91f2d415f013`.
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

Sample and custom local reviews are always public. There is no enable flag,
shared demo code or configuration fetch required to start either workflow.
Compatibility config endpoints report `public_local: true` and `enabled: true`.
Existing legacy enable flags and sample codes have no effect and can be removed
from server configuration during a separately approved maintenance change.
This update does not edit existing credentials or `.env`.

`DUBGUARD_CLIENT_EDITS_PER_HOUR=60` (ceiling 120) and
`DUBGUARD_OPERATOR_LOGINS_PER_HOUR=8` (ceiling 30) remain operational controls.
Creation/upload budgets remain 4/6 hourly per client, shared across both flows.
The AMD code is independent of reviewer credentials and the provider key; absent
or invalid AMD configuration leaves local verification available.

Use [the full application upgrade runbook](DEPLOYMENT.md#full-application-upgrade)
and [the exact update commands](DEPLOYMENT.md#public-workspace-update-commands)
only after approval and pinning the new reviewed Git SHA. Build while the old
release serves, stop the single API for a full SQLite/audio volume backup, verify
a restore copy, then update API and web using the existing project and volumes.
Never regenerate credentials, use `down -v`, or deploy a moving branch. Public
availability begins on deployment; finish isolation/resource tests before release.
Keep old image tags for rollback, preserving every post-backup review write.

## Verification and remaining limits

Current access-removal results and desktop/mobile browser captures are under
`reports/local/public-access/` (ignored local artifacts). Development browser
tests use explicitly labeled synthetic audio/stub ASR/mock AMD fixtures. The
separate production-container test runs real CPU Whisper on generated silence.
Executed checks: **363 backend tests, 28 Vitest tests, 15 development Chrome E2E
tests and 2 production-container Chrome tests passed**. TypeScript typecheck,
host/container production builds, pip dependency checks, npm audit (zero known
vulnerabilities), generated API contracts and `git diff --check` passed. Captured
desktop/mobile states passed axe WCAG A/AA checks with zero reported violations;
this is not a full accessibility certification. Four configured secret values
were checked against the production bundle; none were present. Deployment command
blocks passed Bash syntax validation; they have not been executed on DigitalOcean.
No speech-accuracy claim is made.

Regression coverage includes missing/false/true legacy flags, code-free creation,
unavailable/stale config responses, actual custom rules, original-byte downloads,
corrections and demo exports, capability isolation/expiry, quotas, spoofed headers,
private operator boundaries, critical sign-off blocks, and separately authorized
AMD consent/citation/timeout behavior using mocks only.

Inspected captures: [sample landing](reports/local/public-access/after/public-landing-desktop.png),
[custom editor desktop](reports/local/public-access/after/custom-reference-desktop.png),
[custom editor mobile](reports/local/public-access/after/custom-reference-mobile.png).
The disabled-feature warning and code prompt are absent. The form remains usable
at both sizes, with original audio and evidence downstream. Backend JUnit is
`reports/local/public-access/backend.xml`. Local capture files are intentionally ignored.

Physical microphones and Safari/iOS remain unverified. Anonymous attestations are
untrusted demonstration evidence. The workspace is a temporary, single-instance,
English/single-speaker demo, not persistent organizational collaboration. Custom
AMD review is unavailable; the protected sample AMD flow remains available where
configured. Shared NAT clients share limits. Both public local workflows are always
available within those limits. DigitalOcean remains unchanged until approval.
