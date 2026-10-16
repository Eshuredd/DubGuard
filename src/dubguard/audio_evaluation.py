"""Opt-in local evaluation requiring human-verified recorded-audio manifests."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from pydantic import Field, model_validator

from .acoustic import targeted_recheck
from .alignment import apply_confirmed_alignment, propose_alignment
from .audio import AudioStore, FasterWhisperProvider, transcribe_artifact
from .engine import verify
from .evaluation import calculate_metrics
from .schemas import (EvaluationLabel, Model, ScriptPolicy, VerificationRequest, Transcript)
from .text import normalize


class SpokenGroundTruth(Model):
    text: str = Field(min_length=1)
    instruction_id: str | None = None
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def paired_timing(self):
        if (self.start_seconds is None) != (self.end_seconds is None):
            raise ValueError("ground truth timing must be paired")
        if self.start_seconds is not None and self.end_seconds < self.start_seconds:
            raise ValueError("ground truth timing is reversed")
        return self


class RecordedCase(Model):
    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    split: str = Field(pattern="^(development|held_out)$")
    audio_path: Path
    audio_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    human_verified_by: str = Field(min_length=1)
    adjudication_note: str = Field(min_length=1)
    spoken_ground_truth: list[SpokenGroundTruth] = Field(min_length=1)
    protected_terms: list[str] = Field(default_factory=list)
    label: EvaluationLabel
    policy: ScriptPolicy
    confirmed_asr_alignment: dict[str, str] = Field(default_factory=dict)
    human_corrected_transcript: Transcript | None = None


class RecordedManifest(Model):
    schema_version: str = "1"
    cases: list[RecordedCase] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_case_ids(self):
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("audio evaluation case IDs must be unique")
        return self


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize(text).lower())


def _word_errors(expected: list[str], observed: list[str]) -> int:
    previous = list(range(len(observed) + 1))
    for index, token in enumerate(expected, 1):
        current = [index]
        for column, candidate in enumerate(observed, 1):
            current.append(min(previous[column] + 1, current[column - 1] + 1,
                               previous[column - 1] + (token != candidate)))
        previous = current
    return previous[-1]


def _contains(text: str, phrase: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(normalize(phrase)) + r"(?!\w)", normalize(text)))


def evaluate_recorded_audio(manifest_path: Path, *, model_path: str,
                            secondary_model_path: str | None = None) -> dict:
    manifest_bytes = manifest_path.read_bytes()
    manifest = RecordedManifest.model_validate_json(manifest_bytes)
    primary = FasterWhisperProvider(model_path, local_files_only=True)
    secondary = FasterWhisperProvider(secondary_model_path, local_files_only=True) if secondary_model_path else None
    rows = []
    with TemporaryDirectory(prefix="dubguard-audio-evaluation-") as directory:
        store = AudioStore(Path(directory))
        for case in manifest.cases:
            audio_bytes = case.audio_path.read_bytes()
            if sha256(audio_bytes).hexdigest() != case.audio_sha256:
                raise ValueError(f"Audio hash mismatch for {case.id}")
            artifact = store.ingest(audio_bytes)
            known = {i.id for i in case.policy.script.instructions}
            for span in case.spoken_ground_truth:
                if span.instruction_id is not None and span.instruction_id not in known:
                    raise ValueError(f"Unknown ground truth instruction in {case.id}")
                if span.end_seconds is not None and span.end_seconds > artifact.duration_seconds:
                    raise ValueError(f"Ground truth timestamp exceeds audio in {case.id}")
            corrected_result = None
            if case.human_corrected_transcript is not None:
                corrected = case.human_corrected_transcript
                if corrected.source != "manual":
                    raise ValueError("Corrected evidence must be manually reviewed")
                for span in corrected.segments:
                    if span.instruction_id is not None and span.instruction_id not in known:
                        raise ValueError("Unknown corrected instruction")
                    if span.end_seconds is not None and span.end_seconds > artifact.duration_seconds:
                        raise ValueError("Corrected timestamp exceeds original audio")
                corrected_result = verify(VerificationRequest(**case.policy.model_dump(mode="json"), transcript=corrected))
            result = transcribe_artifact(store, artifact, primary)
            transcript = (apply_confirmed_alignment(result.transcript, case.confirmed_asr_alignment,
                                                    case.policy.script) if case.confirmed_asr_alignment
                          else result.transcript)
            request = VerificationRequest(**case.policy.model_dump(mode="json"), transcript=transcript)
            decision = verify(request)
            proposed = propose_alignment(case.policy.script, result.transcript)
            proposed_by_segment = {p.segment_ids[0]: p.instruction_ids
                                   for p in proposed.proposals if len(p.segment_ids) == 1 and
                                   p.match_type not in {"POSSIBLE_MERGED_INSTRUCTIONS"}}
            alignment_hits = sum(expected in proposed_by_segment.get(segment_id, [])
                                 for segment_id, expected in case.confirmed_asr_alignment.items())
            truth_text = " ".join(s.text for s in case.spoken_ground_truth)
            observed_text = " ".join(s.text for s in result.transcript.segments)
            truth_tokens, observed_tokens = _tokens(truth_text), _tokens(observed_text)
            protected_errors = [term for term in case.protected_terms
                                if _contains(truth_text, term) != _contains(observed_text, term)]
            recheck = None
            if secondary:
                recheck = targeted_recheck(store, artifact, case.policy.policy,
                                           result.transcript, case.confirmed_asr_alignment,
                                           secondary, primary_provider=primary.name,
                                           primary_model=primary.model_id)
            rows.append({"id": case.id, "category": case.category, "split": case.split,
                         "label": case.label.value, "decision": decision.decision.value,
                         "audio_sha256": artifact.sha256, "human_verified_by": case.human_verified_by,
                         "adjudication_note": case.adjudication_note,
                         "ground_truth_text": truth_text, "asr_text": observed_text,
                         "raw_transcript": result.transcript.model_dump(mode="json"),
                         "timestamp_validity": all(s.start_seconds is not None and
                             0 <= s.start_seconds <= s.end_seconds <= artifact.duration_seconds
                             for s in result.transcript.segments) if result.transcript.segments else None,
                         "coverage": result.coverage.model_dump(mode="json"),
                         "suspected_violations": [f.model_dump(mode="json") for f in decision.findings
                                                  if f.rule_id.startswith("ASR.SUSPECTED.")],
                         "human_corrected_evidence": case.human_corrected_transcript.model_dump(mode="json")
                             if case.human_corrected_transcript else None,
                         "human_evidence_verification": corrected_result.model_dump(mode="json") if corrected_result else None,
                         "final_verification_decision": (corrected_result or decision).decision.value,
                         "release_approval": "not_performed_by_evaluation",
                         "reference_words": len(truth_tokens),
                         "word_errors": _word_errors(truth_tokens, observed_tokens),
                         "protected_terms": case.protected_terms,
                         "protected_term_errors": protected_errors,
                         "duration_seconds": artifact.duration_seconds,
                         "processing_seconds": result.processing_seconds,
                         "coverage_ratio": result.coverage.processed_seconds / artifact.duration_seconds,
                         "processing_complete": result.coverage.complete_processing,
                         "alignment_proposal": proposed.model_dump(mode="json"),
                         "confirmed_alignment_count": len(case.confirmed_asr_alignment),
                         "alignment_proposal_hits": alignment_hits,
                         "secondary": recheck.model_dump(mode="json") if recheck else None})
    def group(selected):
        reference = sum(row["reference_words"] for row in selected)
        alignment_count = sum(row["confirmed_alignment_count"] for row in selected)
        return {"count": len(selected), "primary_asr_word_error_rate":
                sum(row["word_errors"] for row in selected) / reference if reference else None,
                "protected_term_error_count": sum(len(row["protected_term_errors"]) for row in selected),
                "audio_processing_complete_count": sum(row["processing_complete"] for row in selected),
                "alignment_proposal_accuracy_on_confirmed_segments":
                sum(row["alignment_proposal_hits"] for row in selected) / alignment_count
                if alignment_count else None,
                "deterministic": calculate_metrics(selected)}
    return {"schema_version": "1", "manifest_sha256": sha256(manifest_bytes).hexdigest(),
            "primary_provider": primary.name, "primary_model": primary.model_id,
            "secondary_model": secondary.model_id if secondary else None,
            "splits": {split: group([row for row in rows if row["split"] == split])
                       for split in ("development", "held_out")},
            "cases": rows,
            "limitations": ["Human verification is asserted by manifest metadata; DubGuard does not authenticate adjudicators in this evaluation file.",
                            "ASR text and alignment proposals are not ground truth.",
                            "Recognizer agreement does not prove transcription correctness."]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Opt-in recorded-audio evaluation; never runs remote APIs")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--model-path", required=True, help="Local faster-whisper model path or cached ID")
    parser.add_argument("--secondary-model-path", help="Optional distinct local cached model")
    parser.add_argument("--output", type=Path, default=Path("reports/audio_evaluation.json"))
    args = parser.parse_args(argv)
    report = evaluate_recorded_audio(args.manifest, model_path=args.model_path,
                                     secondary_model_path=args.secondary_model_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
