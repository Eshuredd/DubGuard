# Phase 1 implementation plan

Initial inspection: the workspace was empty, with no Git metadata, application,
dependency files, or tests. Python 3.11 and local Python tooling are available.
No existing infrastructure needs replacement. No commit or push will be made.

1. Define strict Pydantic contracts for scripts, reviewer-approved variants,
   protected constraints, transcript segments, evidence, findings, decisions,
   and human-authored evaluation labels.
2. Build a conservative local engine with exact/approved matching, numeric
   normalization, explicit polarity and warning rules, protected sequence checks,
   and unresolved evidence handling. Preserve source spans and supplied times.
3. Add a semantic-provider protocol, a clearly marked local mock, and a disabled
   AMD scaffold configured only by environment variables. Semantic advice cannot
   silently clear uncertain evidence or override deterministic violations.
4. Author at least 40 explicit synthetic cases, run a normalized-difference
   baseline and the policy engine, and export deterministic JSON/Markdown metrics
   with category errors and failure examples. Skip hybrid measurement without
   real inference; never substitute mock output for AMD measurements.
5. Expose validation, verification, and evaluation through FastAPI and a CLI.
   Add tests, pinned dependencies, examples, CPU Docker packaging, and exact
   local commands. Run tests and smoke checks and document remaining limitations.

Safety boundary: pass candidates are review aids, never safety certification,
release approval, or a guarantee of semantic equivalence. Unknown wording,
unreliable ASR evidence, and unsupported constructions require human review.
