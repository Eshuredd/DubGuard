# DubGuard Phase 1 synthetic evaluation

Cases: **60**. Profiles: **13**.

Dataset SHA-256: `ed0a2f2b7879718e308e99a158fec0c502c541e8fb476b7f769cf87d739a0da3`

These are reproducible local development results, not safety certification or AMD performance measurements.

| Path | Count | Recall | Precision | Acceptable false-alert rate | Unresolved rate | Errors | Unsafe passes |
|---|---:|---:|---:|---:|---:|---:|---:|
| A_normalized_diff | 60 | 100.00% | 53.33% | 66.67% | 11.67% | 21 | 0 |
| B_policy_engine | 60 | 91.67% | 100.00% | 0.00% | 23.33% | 2 | 0 |
| C_hybrid (skipped) | — | — | — | — | — | — | — |

## Definitions and scope

- **critical_deviation_recall**: critical predicted critical / all critical; critical sent to review counts as a miss.
- **critical_deviation_precision**: critical predicted critical / all predicted critical; unresolved labels predicted critical count as false positives.
- **false_alert_rate_on_acceptable**: acceptable predicted critical / all acceptable.
- **acceptable_escalation_rate**: acceptable predicted critical or review / all acceptable.
- **unresolved_rate**: REVIEW_REQUIRED decisions / all cases; critical results may also contain unresolved findings.
- **decision_errors**: decision differs from label mapping ACCEPTABLE->PASS_CANDIDATE, CRITICAL->CRITICAL_DEVIATION, UNRESOLVED->REVIEW_REQUIRED.
- **undefined_ratios**: null when denominator is zero.

Label counts: {"ACCEPTABLE": 24, "CRITICAL": 24, "UNRESOLVED": 12}.

## A_normalized_diff

| Category | Cases | Errors | Critical misses | False critical alerts | Unsafe passes |
|---|---:|---:|---:|---:|---:|
| alignment | 2 | 2 | 0 | 2 | 0 |
| asr | 5 | 0 | 0 | 0 | 0 |
| changed-unit | 5 | 0 | 0 | 0 | 0 |
| hard-negative | 6 | 3 | 0 | 3 | 0 |
| missing-evidence | 3 | 0 | 0 | 0 | 0 |
| negation | 3 | 1 | 0 | 1 | 0 |
| numeric-ambiguity | 1 | 1 | 0 | 1 | 0 |
| numeric-range | 3 | 1 | 0 | 1 | 0 |
| paraphrase | 4 | 3 | 0 | 3 | 0 |
| polarity | 3 | 0 | 0 | 0 | 0 |
| quantity | 1 | 0 | 0 | 0 | 0 |
| semantic-challenge | 2 | 0 | 0 | 0 | 0 |
| sequence | 3 | 0 | 0 | 0 | 0 |
| temperature | 5 | 1 | 0 | 1 | 0 |
| time | 3 | 1 | 0 | 1 | 0 |
| unit-conversion | 6 | 6 | 0 | 6 | 0 |
| warning | 5 | 2 | 0 | 2 | 0 |

### Failure examples (all decision mismatches)

- **A02** (paraphrase): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Switch the power off."].
  Observed: ["Turn the power off."].
  Label rationale: Reviewer explicitly approved turn instead of switch.
- **A03** (paraphrase): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Keep the valve closed."].
  Observed: ["Leave the valve closed."].
  Label rationale: Reviewer explicitly approved leave closed.
- **A04** (negation): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Do not bypass the interlock."].
  Observed: ["Never bypass the interlock."].
  Label rationale: Never is an explicitly approved prohibition, not a reversal.
- **A05** (warning): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Warning: isolate the supply before maintenance."].
  Observed: ["Before maintenance, isolate the supply."].
  Label rationale: Approved warning paraphrase preserves the required isolation step.
- **A06** (time): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Wait at least 60 seconds."].
  Observed: ["Allow at least 1 minute."].
  Label rationale: One minute is exactly 60 seconds and this phrasing is approved.
- **A07** (unit-conversion): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Wait at least 60 seconds."].
  Observed: ["Wait at least 1 minute."].
  Label rationale: Same template and exact 60-second to 1-minute conversion.
- **A08** (unit-conversion): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Keep temperature at or below 80 °C."].
  Observed: ["Keep temperature at or below 176 °F."].
  Label rationale: 176 Fahrenheit is exactly 80 Celsius with unchanged inclusive upper bound.
- **A09** (unit-conversion): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Keep temperature at or below 80 °C."].
  Observed: ["Keep temperature at or below 353.15 K."].
  Label rationale: 353.15 kelvin is exactly 80 Celsius.
- **A10** (unit-conversion): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Maintain pressure from 2 to 4 bar."].
  Observed: ["Maintain pressure from 200 to 400 kPa."].
  Label rationale: Both pressure endpoints convert exactly from bar to kPa.
- **A11** (unit-conversion): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Set clearance to 10 mm."].
  Observed: ["Set clearance to 1 cm."].
  Label rationale: One centimeter equals ten millimeters.
- **A13** (hard-negative): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Install 4 bolts."].
  Observed: ["Install 4.0 bolts."].
  Label rationale: Decimal formatting preserves the exact count.
- **A15** (hard-negative): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Read the label.", "Record the serial number."].
  Observed: ["Record the serial number.", "Read the label."].
  Label rationale: This reviewer imposed no ordering constraint on the two exact administrative steps.
- **A20** (hard-negative): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Wait at least 60 seconds."].
  Observed: ["Wait at least 60 sec."].
  Label rationale: Equivalent unit spelling within the same numeric template.
- **A21** (numeric-range): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Maintain pressure from 2 to 4 bar."].
  Observed: ["Maintain pressure from 2–4 bar."].
  Label rationale: En dash expresses the same two endpoints in the supported grammar.
- **A22** (temperature): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Keep temperature at or below 80 °C."].
  Observed: ["Maintain temperature at or below 80 °C."].
  Label rationale: Explicit approved maintain-temperature wording.
- **A24** (unit-conversion): expected PASS_CANDIDATE; observed CRITICAL_DEVIATION.
  Approved: ["Set clearance to 10 mm."].
  Observed: ["Set clearance to 0.01 m."].
  Label rationale: Hundredth of a meter is exactly ten millimeters.
- **U06** (alignment): expected REVIEW_REQUIRED; observed CRITICAL_DEVIATION.
  Approved: ["Switch the power off."].
  Observed: ["Switch the power on."].
  Label rationale: Changed text without reviewed instruction mapping cannot be aligned by similarity alone.
- **U07** (paraphrase): expected REVIEW_REQUIRED; observed CRITICAL_DEVIATION.
  Approved: ["Switch the power off."].
  Observed: ["Make sure the power is inactive."].
  Label rationale: Plausible off-state paraphrase is not explicitly approved and may be context-dependent.
- **U09** (alignment): expected REVIEW_REQUIRED; observed CRITICAL_DEVIATION.
  Approved: ["Switch the power off."].
  Observed: ["Switch the power off.", "Switch the power off."].
  Label rationale: Repeated instruction segments require manual segmentation/repetition review.
- **U10** (numeric-ambiguity): expected REVIEW_REQUIRED; observed CRITICAL_DEVIATION.
  Approved: ["Wait at least 60 seconds."].
  Observed: ["Wait at least sixty seconds."].
  Label rationale: A numeral spoken as words is outside this numeric grammar and is not an approved variant.
- **U11** (warning): expected REVIEW_REQUIRED; observed CRITICAL_DEVIATION.
  Approved: ["Warning: isolate the supply before maintenance."].
  Observed: ["Maintenance needs careful supply handling."].
  Label rationale: Changed warning language is not a known dangerous alternative and requires semantic review.

## B_policy_engine

| Category | Cases | Errors | Critical misses | False critical alerts | Unsafe passes |
|---|---:|---:|---:|---:|---:|
| alignment | 2 | 0 | 0 | 0 | 0 |
| asr | 5 | 0 | 0 | 0 | 0 |
| changed-unit | 5 | 0 | 0 | 0 | 0 |
| hard-negative | 6 | 0 | 0 | 0 | 0 |
| missing-evidence | 3 | 0 | 0 | 0 | 0 |
| negation | 3 | 0 | 0 | 0 | 0 |
| numeric-ambiguity | 1 | 0 | 0 | 0 | 0 |
| numeric-range | 3 | 0 | 0 | 0 | 0 |
| paraphrase | 4 | 0 | 0 | 0 | 0 |
| polarity | 3 | 0 | 0 | 0 | 0 |
| quantity | 1 | 0 | 0 | 0 | 0 |
| semantic-challenge | 2 | 2 | 2 | 0 | 0 |
| sequence | 3 | 0 | 0 | 0 | 0 |
| temperature | 5 | 0 | 0 | 0 | 0 |
| time | 3 | 0 | 0 | 0 | 0 |
| unit-conversion | 6 | 0 | 0 | 0 | 0 |
| warning | 5 | 0 | 0 | 0 | 0 |

### Failure examples (all decision mismatches)

- **C22** (semantic-challenge): expected CRITICAL_DEVIATION; observed REVIEW_REQUIRED.
  Approved: ["Switch the power off."].
  Observed: ["Go ahead and energize the power supply."].
  Label rationale: Manually labeled dangerous instruction to energize the power; outside the explicit reversal template, so conservative review is expected.
- **C23** (semantic-challenge): expected CRITICAL_DEVIATION; observed REVIEW_REQUIRED.
  Approved: ["Do not bypass the interlock."].
  Observed: ["Bypassing the interlock is permitted."].
  Label rationale: Manually labeled bypass permission despite a changed imperative template; engine must not clear it.

## C_hybrid

Real inference is unavailable or was not requested. No mock/LLM/AMD performance result is claimed.

## Limitations

- Small, curated synthetic development set, not a held-out industrial benchmark.
- Instruction mappings and transcript completeness are supplied review metadata.
- No audio transcription, industrial safety approval, latency benchmark, or AMD-backed inference has been demonstrated.
