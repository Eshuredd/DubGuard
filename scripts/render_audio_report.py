"""Render an existing private recorded-audio JSON report; never run inference."""
import argparse
import json
from pathlib import Path


def cell(value):
    if value is None:
        return 'Not measured'
    return str(value).replace('|', '\\|').replace('\n', ' ')


def render(report):
    lines = ['# Recorded-speech evaluation', '',
        'Rendered from supplied evaluation JSON. Human labels are manifest metadata; no release approval is performed.', '',
        '## ASR word errors', '',
        f'Primary provider/model: {cell(report.get("primary_provider"))} / {cell(report.get("primary_model"))}', '',
        '| Split | Cases | Word error rate |', '|---|---:|---:|']
    for split, metrics in report.get('splits', {}).items():
        wer = metrics.get('primary_asr_word_error_rate')
        lines.append(f'| {cell(split)} | {cell(metrics.get("count"))} | {cell(f"{wer:.4f}" if wer is not None else None)} |')
    lines += ['', '## Protected-token errors', '',
        'These count declared term-presence mismatches, not independently measured semantic accuracy. Numeric word/digit forms may differ.', '',
        '| Case | Terms checked | Error terms |', '|---|---|---|']
    for case in report.get('cases', []):
        lines.append(f'| {cell(case["id"])} | {cell(", ".join(case.get("protected_terms", [])))} | {cell(", ".join(case["protected_term_errors"]) if "protected_term_errors" in case else None)} |')
    lines += ['', '## Acoustic disagreement', '',
        f'Secondary model: {cell(report.get("secondary_model"))}. Agreement does not verify spoken content.', '',
        '| Case | Disagreements | Unresolved requirements |', '|---|---|---|']
    for case in report.get('cases', []):
        secondary = case.get('secondary')
        assessment = secondary.get('assessment', {}) if secondary else {}
        count = len(assessment['disagreements']) if 'disagreements' in assessment else None
        unresolved = ', '.join(assessment['unresolved_requirement_ids']) if 'unresolved_requirement_ids' in assessment else None
        lines.append(f'| {cell(case["id"])} | {cell(count)} | {cell(unresolved)} |')
    lines += ['', '## End-to-end verification', '',
        'Raw ASR is provisional. Corrected decisions require supplied human-reviewed evidence. Neither is a release sign-off.', '',
        '| Case | Human label | Raw-ASR decision | Human-corrected decision | Final decision |', '|---|---|---|---|---|']
    for case in report.get('cases', []):
        corrected = case.get('human_evidence_verification')
        lines.append(f'| {cell(case["id"])} | {cell(case.get("label"))} | {cell(case.get("decision"))} | {cell(corrected.get("decision") if corrected else None)} | {cell(case.get("final_verification_decision"))} |')
    lines += ['', '## Processing and timestamps', '',
        '| Case | Duration (s) | ASR processing (s) | Coverage | Timestamp validity |', '|---|---:|---:|---:|---|']
    for case in report.get('cases', []):
        lines.append('| ' + ' | '.join(cell(case.get(key)) for key in ('id', 'duration_seconds', 'processing_seconds', 'coverage_ratio', 'timestamp_validity')) + ' |')
    lines += ['', '## Limitations', '']
    lines += ['- ' + cell(note) for note in report.get('limitations', [])]
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = render(json.loads(args.report.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding='utf-8')
    print('Human-readable report written. No ASR or remote inference executed.')
