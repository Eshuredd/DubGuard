# DubGuard UI design record

## Visual redesign — screenshot mapping recorded before implementation

The new baseline is the **uncommitted refined application**, not Git HEAD. It was captured with the real Chrome fixture suite at 1440 and 390 px in `reports/local/visual-redesign/before/`. Existing source/tests/docs were preserved in `reports/local/visual-redesign/preserved/pre-redesign.zip`. The baseline suite passed 10 tests, with the public-mode test run separately later. No reset, stash or revert was used.

The five largest visual problems are: identical white rounded panels throughout; weak separation between application chrome and working content; a browser-native player with no visible relation to evidence; short comparisons floating in large report sections; and oversized queue cards instead of an operational list.

The five largest usability problems are: recording controls below repeated scenario copy; results requiring a long vertical read; no selected finding/inspector relationship; limited orientation within an individual review; and mobile pages requiring repeated travel between audio and evidence.

| Primary visual reference | Layout, type, spacing and navigation observed | Adopt in DubGuard | Do not copy / important adaptation |
| --- | --- | --- | --- |
| Attached image 1: audio editor | Dark compact horizontal transport; large green play control; fixed-width time display; overview and detailed waveform tracks; narrow ruler; transcript blocks aligned to time; selected segment outlined; channel labels and a clear shared playhead. Dense working content is grouped by thin separators instead of many cards. | A dark source-audio transport with actual play/pause, seek, speed and elapsed time; **decoded original-audio** waveform; timestamped ASR segment buttons; obvious selection; a recording stage with the same audio-tool character. | One original source track, not invented second channels. No editing/splicing or Add Segment controls, copied icons, screenshot assets or random waveform. ASR spans remain approximate. Unsupported decoding gets an honest fallback and playable audio. A playhead uses the accent rather than red error semantics. |
| Attached image 2: diff viewer | Large plain heading; parallel equal-width comparison panes; aligned gutters/line numbers; monospace text; colored line and word differences; search and match navigation in a distinct right rail; compact count cards and a visible legend. Dark neutral surfaces create clear pane boundaries. | Parallel approved/recognized panes, source labels and line numbers; whole-word marks; search; actual text-change counts labeled as text differences; an evidence inspector in a separate right-hand column; selected finding and linked timestamps. | Keep light comparison surfaces for sustained reading. Never treat additions/removals as confirmed policy violations. Preserve source text; do not provide Clear buttons that remove evidence, copy sample content, invent counts, or use green as release approval. No claim that this is DubGuard's current UI. |

The current DubGuard screenshots have a full-width white top navigation and a narrow centered stack of panels. Neither the dark audio transport nor the dedicated diff/inspector structure is present. This redesign changes those structural features, not just their colors.

Three browser-rendered concepts are stored under `reports/local/visual-redesign/concepts/`: A, Precision Workspace (dark sidebar, compact operational list); B, Evidence Studio (wide audio/diff canvas and contextual inspector); C, Modern SaaS Product (editorial landing, modular onboarding). Concepts are explicitly illustrative and contain no inference or simulated audio data.

| Direction | Visual character / brand fit | Workflow and accessibility | Mobile / implementation tradeoff |
| --- | --- | --- | --- |
| A | Crisp industrial navy/teal; strongest persistent orientation | Clear task navigation; high contrast chrome | Sidebar becomes a labeled menu; moderate shell work |
| B | Most specific to narration verification; closest to both attached references | Audio, source comparison and selected evidence occupy one workspace | Panes stack and inspector moves below; greatest component work, justified by priority |
| C | Strongest marketing composition; friendly but less specialized | Fast entry; a generic card dashboard would weaken evidence focus | Easy stacking; useful for landing only |

Selected direction: **B's Evidence Studio inside A's Precision Workspace**, with C's concise editorial landing. One navy/off-white/teal system ties these together. No unrelated visual styles are mixed. Existing recording, consent, quotas, original-byte downloads, corrections and sign-off handlers remain authoritative.

Secondary sources were revisited: [Mobbin's public pattern discussion](https://mobbin.com/mcp) is accessible but its app library is gated; [Page Flows](https://pageflows.com/) and [Saaspo's Linear section](https://saaspo.com/sections/linear-hero-section) could not be fetched; [Dark.design](https://www.dark.design/) exposes its gallery taxonomy but individual visuals were not accessible. No inaccessible product screen is claimed as inspected. The two user-provided images are the primary visual evidence.

### Implemented visual change and self-review

| Extent | Components / resulting interface |
| --- | --- |
| Substantially restructured | `Shell` in `main.tsx`: persistent navy navigation, workspace breadcrumbs, Overview/queue/history destinations, native mobile menu. `QuickTest`: desktop scenario rail, compact mobile selector, read-aloud script beside a dark capture stage, inline landing session entry. `QuickResults`: audio/diff canvas plus independent findings/completeness inspector; clicking a finding focuses its source details. `TextComparison`: numbered parallel panes, text search and match navigation, actual approved-only/recognized-only word counts, selected source lines. `Dashboard`: column-based queue with identity, actual evidence readiness, workflow state and next action. `ReviewPage`: source comparison beside human correction, explicit stage readiness, split mapping/verification tools, finding inspector and protected decision area. |
| Newly created | `AudioTransport.tsx`: actual playback/pause, ±5-second seeking, playback rate, real elapsed time, original-audio decoding and amplitude waveform, approximate source-span buttons, native playback fallback. `EvidenceInspector.tsx`: local/AMD groups, actual counts and persistent unresolved status. `Icon.tsx`: a small consistent original SVG set; no icon dependency or external artwork. |
| Preserved functionality with smaller changes | `Audio.tsx` retains recorder lifecycle, permission handling, real meter, limits and original-byte downloads; it composes the new transport. `Evidence.tsx` retains exact-source references and original action indices while supporting selected review evidence. Policy editing and login handlers remain intact and inherit the new visual system. No backend, generated API contract, approval prerequisite or credential changes. |
| Design system | `studio.css` is now the single imported stylesheet: navy chrome, off-white canvas, focused teal actions, amber uncertainty and red confirmed critical findings; editorial serif page headings, system UI controls and monospaced evidence; shared spacing, borders, radii, responsive behavior, focus and reduced-motion rules. Earlier styles remain preserved on disk and in the pre-redesign archive rather than being layered into the new interface. |

The implemented result follows the supplied references structurally: a dark transport controls a real source waveform; the narration is inspected in parallel numbered panes; a distinct inspector connects selected findings to source text. Added/removed text counts are descriptive comparisons, never model confidence or policy verdicts. Source audio is one trace combining the actual channel peaks, not invented editing tracks.

Manual screenshot review led to these correction passes:

- Darkened low-contrast labels, gutters and muted copy against their actual surfaces; corrected short-height sidebar overflow instead of masking the resulting contrast failure.
- Replaced tall mobile scenario cards with a selector and moved active recording controls ahead of the meter. Disabled upload options disappear while capturing. The microphone, source preview and Analyze action use distinct treatments.
- Made the transport timer non-announcing; kept keyboard-operated native playback available. Selected findings focus and scroll their detailed evidence into view. New evidence revisions reset visual selection.
- Restored rejected AMD citation explanations as always-visible warnings outside the selected-finding view. Local and AMD findings stay distinct, and every original approval blocker remains explicit.
- Reduced the correction editor's desktop height with paired timestamp fields and reset screenshot scroll positions so sticky chrome is captured in its actual top-of-page position.

The [comparison gallery and three visual concepts](../reports/local/visual-redesign/index.html) pair the **current-local baseline** and redesign at 1440×1000 and 390×844, including landing, scenarios, recording, preview, local results, mocked AMD, queue, evidence review, sign-off and policy editing. Full-page and focused views are retained under ignored `reports/local/visual-redesign/`. After captures carry an injected development-fixture banner; that banner is created by the capture helper and is absent from the product. All captures use fake-device/synthetic audio, stub ASR and mocked AMD, not accuracy demonstrations.

Remaining limits: long transcripts and the full reviewer audit/attestation process still require vertical scrolling, especially on mobile. Waveforms depend on browser decoding and are omitted for files over 15 MB; original/native playback remains available. No multi-track audio editing is provided. Dense source inspection should still receive real reviewer usability testing. Physical microphone quality, screen-reader speech output, non-Chromium browsers and the production Docker build have not been manually verified. Local Node is 22.19.0, below the declared engine floor; the deployment Dockerfile remains pinned to 22.22.2.

The frontend-only deployment/rollback procedure in [DEPLOYMENT.md](../DEPLOYMENT.md#frontend-only-refinement-release) still applies after approval of an exact pushed SHA. Existing API/data/model/Caddy volumes and server credentials must be retained. No commit, push, server rebuild or deployment was performed. Suggested eventual commit: `feat(frontend): overhaul DubGuard interface and evidence workspace`.

### Verification of the visual redesign

| Check | Final result |
| --- | --- |
| TypeScript | Passed; `npm run build` executes `tsc -b` before Vite |
| Frontend unit tests | 28 passed across 4 files; previous tests preserved, 2 waveform tests added |
| Production build | Passed; JavaScript 355.99 kB / 107.36 kB gzip; CSS 39.57 kB / 9.32 kB gzip; no added dependency |
| Full private Chrome suite | 10 passed; public-only test intentionally skipped |
| Separate public Chrome suite | 1 passed; isolated public fixture configuration only |
| Accessibility | Zero axe WCAG 2 A/AA and 2.1 AA violations across audited landing, session, recording/preview, local/AMD evidence, queue, policy and sign-off captures; expanded evidence is also audited |
| Interaction and viewport checks | Keyboard skip link, scenario selection, stage anchors, source disclosure, finding selection, text search, mobile menu closing on navigation, Overview/history navigation, custom play/pause and actual playback-rate change; reduced-motion mode; no horizontal overflow at 320, 390, 768 and 1440 px |
| Backend regressions | 333 passed, 1 existing Starlette/AnyIO deprecation warning; no backend source changes |
| Patch hygiene | `git diff --check` passed; screenshots, prototypes, logs, JSON/JUnit and preservation archive remain under ignored `reports/local/` |

The existing browser suite continues to exercise original-byte downloads, private audio access, refresh, microphone permission failure, restricted AMD access/consent/quotas, invalid citations, human corrections, acoustic conflict resolution, critical approval blocking, explicit sign-off, stale-run rejection, unsaved-edit blockers and retry recovery. UI restructuring changed selectors only where the new controls or evidence-selection interaction required it. Final machine-readable browser results and backend JUnit are in `reports/local/visual-redesign/`.

Reproduce from `frontend` on PowerShell:

```powershell
rtk npm run typecheck
rtk npm test
rtk npm run build
rtk proxy powershell -NoProfile -Command '$env:DUBGUARD_VISUAL_DIR="../reports/local/visual-redesign"; $env:DUBGUARD_E2E_API_PORT="18000"; $env:DUBGUARD_E2E_WEB_PORT="15173"; npm run test:e2e -- --reporter=line'
rtk proxy powershell -NoProfile -Command '$env:DUBGUARD_VISUAL_DIR="../reports/local/visual-redesign"; $env:DUBGUARD_E2E_API_PORT="18000"; $env:DUBGUARD_E2E_WEB_PORT="15173"; npm run test:e2e -- tests/public.spec.ts --reporter=line'
```

From the repository root: `rtk proxy .venv/Scripts/python.exe -m pytest -q --junitxml=reports/local/visual-redesign/backend.xml`. Alternate ports avoid touching existing local services. These checks validate fixture protocol/UI behavior, not real ASR or AMD inference quality, full WCAG conformance, or production deployment readiness.

---

## Previous evidence-first refinement (preserved)

Baseline: `3abb735db75261a4165d269a0d217054da7b4788`. Inspection and reference research: 18 October 2026. This is a refinement of the implemented Phase 6 interface.

## Audit and decisions recorded before implementation

Preserve scenario cards, original-byte audio preview/download, private session controls, fresh AMD consent and server quotas, exact source citations, human evidence revisions and server-checked sign-off. The existing light palette and component structure are appropriate.

Desktop/mobile browser captures show results below the entire setup form; approved and recognized narration are separated by coverage, timeline and metadata; empty finding comparisons consume space. Mobile scenario copy is very small. Queue rows show stage markers but no explicit next action. A later CSS rule cancels sticky playback. Processing and quota errors need a clearer recovery path.

| Reference inspected | Observable pattern / limitation | Planned DubGuard application |
| --- | --- | --- |
| [Mobbin public pattern example](https://mobbin.com/mcp) | Its public KYC example describes step indicators, expectations before device access and inline data-handling guidance. The [app library](https://mobbin.com/discover/apps/web) exposes sign-in, not review queues, to this session. No gated screens were inspected. | Mark the current recording step; explain microphone state before capture; keep limits and consent beside the action. Apply disclosure to technical evidence, never blockers. |
| [Page Flows](https://pageflows.com/) | Direct access returned HTTP 403. Search-indexed [progress-bar taxonomy](https://pageflows.com/web/elements/progress-bar/?page=24) is visible, but no recording flow could be played. | No product-specific flow claims. Use DubGuard's actual state transitions for progress and retry; no invented percentages or duration estimates. |
| [Saaspo's landing guidance](https://saaspo.com/blog/saas-landing-page-best-practices-how-to-design-pages-that-actually-convert) | Search-indexed article recommends a concise hero, primary CTA and early product UI; cites Linear and Figma. Direct fetch returned 403; the screenshot gallery was not inspected. | Preserve the off/on example, frame it as an illustrative evidence review, explain the required listening step, and distinguish temporary Quick Test from authenticated review. |
| [Dark.design](https://www.dark.design/) | Public gallery exposes software categories and entries including Linear and Railway; individual example visuals could not be inspected. | No claimed borrowing of a site's typography. Use an original restrained navy/neutral system with clear type sizes and amber only for uncertainty, keeping the requested light-first theme. |

Implementation priorities: state and uncertainty → original audio → side-by-side text comparison → next human action → local findings → optional AMD findings → source/audit disclosure. Queue guidance is derived only from stored workflow state and evidence records. No external assets or source code are copied.

## Validation

Implemented:

- Results now precede repeat-recording setup. Verification state and uncertainty lead into original playback, approved/recognized comparison, a next human action, local checks, optional AMD findings and source disclosures. Coverage gaps and ASR limitations stay visible.
- Word-level comparison highlights additions, omissions and separate changed words on both sides, preserves source text, and bounds work for long transcripts. Unresolved findings precede satisfied findings without changing API decision indices. No confidence values are generated.
- Current-step navigation, a real microphone-level meter with cleanup/fallback, a stable recording announcement, clearer preview/download and upload controls, quota guidance, and session/audio retry. Original-byte download behavior is preserved.
- Reviewer comparison uses the saved human transcript when present; raw ASR remains accessible. Human correction comes before mapping. State-derived next actions, desktop sticky audio, queue search/filter scope and explicit retry/empty states improve review navigation. Sign-off conditions, revisions and mutation payloads are unchanged.
- The landing example remains illustrative and explains listening before confirmation. Typography, controls, focus, mobile scenario disclosure and restrained warning colors are consistent. No new dependency, backend/API change or external design asset.

| Check | Result |
| --- | --- |
| Baseline private browser suite, before UI edits | 9 passed; public-mode test intentionally skipped |
| `rtk npm run typecheck` | Passed; final production build also runs `tsc -b` |
| `rtk npm test` | 26 passed across 3 files |
| `rtk npm run build` | Passed; JS 336.45 kB / 102.28 kB gzip, CSS 27.72 kB / 6.69 kB gzip |
| Private Playwright suite | 10 passed; public-mode test intentionally skipped and run separately |
| Public Playwright suite | 1 passed, with public admission enabled only in the isolated fixture server |
| Axe WCAG 2 A/AA + 2.1 AA rules | Zero violations in the audited desktop/mobile screens, including expanded source evidence |
| Keyboard/responsiveness | Skip link, scenario selection, anchor focus and native disclosure tested; no horizontal overflow at 320, 390, 768 and 1440 px; reduced-motion mode checked |
| `rtk proxy .venv/Scripts/python.exe -m pytest -q --junitxml=reports/local/ux-refinement/backend.xml` | 333 passed; one pre-existing Starlette/AnyIO deprecation warning |
| `rtk git diff --check` | Passed |

Browser coverage includes fake-device recording and level meter, cancellation and permission failure, original-byte download, refresh, isolated session deletion, AMD consent/invalid citations/quotas, saved human evidence, critical approval blocking, explicit sign-off, acoustic conflict resolution, stale-run rejection, unsaved edits, connection recovery and queue filtering. A unit test verifies that sorting findings preserves their original decision indices; another verifies microphone context cleanup.

Generated screenshots stay outside Git in [the local comparison gallery](../reports/local/ux-refinement/index.html). It pairs landing, scenario selection, recording, preview, results, mocked AMD, queue, critical evidence review, finalized review and policy editing at 1440×1000 and 390×844 viewports. Full pages and focused views are available. Visual review prompted compact mobile scenario options and fewer repeated warning containers; source warnings remain visible. Isolated runs naturally have different timestamps, queue IDs and fake recording durations.

Reproduce on PowerShell (from `frontend`; use a fresh process for each mode):

```powershell
rtk proxy powershell -NoProfile -Command '$env:DUBGUARD_E2E_API_PORT="18000"; $env:DUBGUARD_E2E_WEB_PORT="15173"; npm run test:e2e -- --reporter=line'
rtk proxy powershell -NoProfile -Command '$env:DUBGUARD_E2E_API_PORT="18000"; $env:DUBGUARD_E2E_WEB_PORT="15173"; npm run test:e2e -- tests/public.spec.ts --reporter=line'
```

The default development ports were already occupied, so tests used separate ports and temporary data directories rather than reusing or stopping existing services. Tests retain the existing backend quota/security behavior. No production audio/history was deleted and no live AMD request was made. Fixture screenshots are not evidence of real ASR/AMD accuracy. Automated accessibility checks do not establish complete WCAG conformance; physical microphone, screen-reader speech output and non-Chromium browsers were not manually validated. Local Node was v22.19.0, below the package's declared engine floor; checks passed, but the pinned production Node 22.22.2 Docker build was not executed here.

Safe deployment and rollback commands are in [Deployment — frontend-only refinement release](../DEPLOYMENT.md#frontend-only-refinement-release). Server-specific project/env/revision values must be verified by the operator. No deployment, commit or push has been performed. Suggested commit after approval: `feat(frontend): refine evidence-first UX using SaaS design patterns`.
