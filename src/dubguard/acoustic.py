"""Protected-term disagreement is review evidence, never a confirmed violation."""

import re
from pathlib import Path
from hashlib import sha256
import tempfile
import wave

from pydantic import Field

from .schemas import Model, ReviewPolicy, Transcript
from .text import normalize
from .audio import (ASRProvider, AudioArtifact, AudioError, AudioStore,
                    SAMPLE_RATE, SAMPLE_WIDTH, _decode)

CONFUSIONS = (
    ("15", "50"), ("16", "60"), ("yes", "no"), ("on", "off"),
    ("open", "closed"), ("before", "after"), ("enable", "disable"),
    ("increase", "decrease"), ("can", "cannot"), ("must", "must not"),
)


class AcousticDisagreement(Model):
    requirement_id: str
    instruction_id: str
    primary_segment_id: str
    secondary_segment_id: str | None = None
    primary_text: str
    secondary_text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    status: str = "REVIEW_REQUIRED"
    explanation: str = "Independent ASR hypotheses disagree on protected wording; listen to source audio."


class AcousticAssessment(Model):
    checked_requirement_ids: list[str] = Field(default_factory=list)
    disagreements: list[AcousticDisagreement] = Field(default_factory=list)
    unresolved_requirement_ids: list[str] = Field(default_factory=list)
    note: str = "Recognizer agreement does not prove what was spoken."


class TargetedRecheckResult(Model):
    secondary_provider: str
    secondary_model: str
    secondary_transcript: Transcript
    assessment: AcousticAssessment
    checked_spans: list[tuple[float, float]]
    note: str = "Secondary recognition received audio only, not approved wording."


def _contains(text: str, phrase: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", normalize(text)))


def _side(text: str, pair: tuple[str, str]) -> int | None:
    a, b = pair
    has_a, has_b = _contains(text, a), _contains(text, b)
    # "must" is contained in "must not". A longer protected phrase wins when
    # its shorter component is not independently present elsewhere.
    if has_b and a in b and b != a:
        residual = re.sub(r"(?<!\w)" + re.escape(b) + r"(?!\w)", "", normalize(text))
        has_a = _contains(residual, a)
    elif has_a and b in a and a != b:
        residual = re.sub(r"(?<!\w)" + re.escape(a) + r"(?!\w)", "", normalize(text))
        has_b = _contains(residual, b)
    if has_a and has_b:
        return None
    return 0 if has_a else 1 if has_b else None


def compare_hypotheses(policy: ReviewPolicy, primary: Transcript,
                       secondary: Transcript, confirmed: dict[str, str]) -> AcousticAssessment:
    """Compare independent, unprompted ASR outputs over reviewer-mapped regions.

    Both transcripts must contain source-audio-relative timestamps. A caller must
    arrange the independent secondary recognition; this function never treats a
    match as proof of transcription accuracy.
    """
    checked: list[str] = []
    unresolved: list[str] = []
    disagreements: list[AcousticDisagreement] = []
    secondary_timed = [s for s in secondary.segments if s.start_seconds is not None]
    for constraint in policy.constraints:
        if constraint.kind == "sequence":
            continue
        instruction_id = constraint.instruction_id
        mapped = [s for s in primary.segments if confirmed.get(s.id) == instruction_id]
        if len(mapped) != 1 or mapped[0].start_seconds is None:
            unresolved.append(constraint.id)
            continue
        source = mapped[0]
        overlaps = [s for s in secondary_timed if s.start_seconds < source.end_seconds and
                    s.end_seconds > source.start_seconds]
        if not overlaps:
            unresolved.append(constraint.id)
            continue
        other_text = " ".join(s.text for s in overlaps)
        if constraint.kind == "polarity":
            pairs = [(constraint.approved_phrase, constraint.reversed_phrase)]
        elif constraint.kind == "numeric":
            pairs = [(a, b) for a, b in CONFUSIONS if a.isdigit() or b.isdigit()]
        else:  # A reviewer-protected warning can contain other consequential words.
            pairs = list(CONFUSIONS)
        consequential = any(_side(source.text, pair) is not None and
                            _side(other_text, pair) is not None and
                            _side(source.text, pair) != _side(other_text, pair)
                            for pair in pairs)
        checked.append(constraint.id)
        if consequential:
            disagreements.append(AcousticDisagreement(requirement_id=constraint.id,
                instruction_id=instruction_id, primary_segment_id=source.id,
                secondary_segment_id=overlaps[0].id if len(overlaps) == 1 else None,
                primary_text=source.text, secondary_text=other_text,
                start_seconds=source.start_seconds, end_seconds=source.end_seconds))
    return AcousticAssessment(checked_requirement_ids=checked, disagreements=disagreements,
                              unresolved_requirement_ids=unresolved)


def targeted_recheck(store: AudioStore, artifact: AudioArtifact, policy: ReviewPolicy,
                     primary: Transcript, confirmed: dict[str, str], secondary: ASRProvider,
                     *, primary_provider: str, primary_model: str) -> TargetedRecheckResult:
    """Recheck every mapped protected region, including apparent exact matches."""
    if (secondary.name, secondary.model_id) == (primary_provider, primary_model):
        raise AudioError("Secondary recognition must use a different provider or model")
    protected = {c.instruction_id for c in policy.constraints if c.kind != "sequence"}
    protected.update(i for c in policy.constraints if c.kind == "sequence" for i in c.instruction_ids)
    selected = [s for s in primary.segments if confirmed.get(s.id) in protected and
                s.start_seconds is not None]
    secondary_segments = []
    checked_spans = []
    source = store.path_for(artifact.sha256, artifact.format)
    if not source.exists() or sha256(source.read_bytes()).hexdigest() != artifact.sha256:
        raise AudioError("Original audio is missing or changed")
    with tempfile.TemporaryDirectory(prefix="dubguard-recheck-") as directory:
        decoded = Path(directory) / "decoded.wav"
        _decode(source, decoded)
        with wave.open(str(decoded), "rb") as reader:
            for index, segment in enumerate(selected):
                start = max(0.0, segment.start_seconds - 0.25)
                end = min(artifact.duration_seconds, segment.end_seconds + 0.25)
                if end <= start:
                    continue
                first, last = round(start * SAMPLE_RATE), round(end * SAMPLE_RATE)
                reader.setpos(first)
                frames = reader.readframes(last - first)
                clip = Path(directory) / f"recheck-{index}.wav"
                with wave.open(str(clip), "wb") as writer:
                    writer.setnchannels(1)
                    writer.setsampwidth(SAMPLE_WIDTH)
                    writer.setframerate(SAMPLE_RATE)
                    writer.writeframes(frames)
                checked_spans.append((start, end))
                for hypothesis in secondary.transcribe(clip):
                    if hypothesis.start_seconds >= end - start:
                        continue
                    observed_start = max(segment.start_seconds, start + hypothesis.start_seconds)
                    observed_end = min(segment.end_seconds, end, start + hypothesis.end_seconds)
                    if observed_end <= observed_start:
                        continue
                    from .schemas import TranscriptSegment
                    secondary_segments.append(TranscriptSegment(
                        id=f"secondary-{len(secondary_segments) + 1}", text=hypothesis.text,
                        start_seconds=observed_start, end_seconds=observed_end,
                        uncertain=True, uncertainty_reason="Independent ASR hypothesis; human audio review required"))
                clip.unlink(missing_ok=True)
    secondary_transcript = Transcript(source="asr", completeness="unknown",
                                      segments=secondary_segments)
    return TargetedRecheckResult(secondary_provider=secondary.name, secondary_model=secondary.model_id,
                                 secondary_transcript=secondary_transcript,
                                 assessment=compare_hypotheses(policy, primary, secondary_transcript, confirmed),
                                 checked_spans=checked_spans)
