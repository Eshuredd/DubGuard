"""Bounded local audio intake and provisional Whisper transcription."""

from dataclasses import dataclass
from array import array
from hashlib import sha256
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Protocol
import wave

from pydantic import Field, model_validator

from .schemas import Model, Transcript, TranscriptSegment

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2


class AudioError(ValueError):
    pass


class AudioArtifact(Model):
    id: str
    sha256: str
    format: str
    byte_size: int = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    sample_rate: int = Field(gt=0)


class AudioWindow(Model):
    index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    core_start_seconds: float = Field(ge=0)
    core_end_seconds: float = Field(gt=0)

    @model_validator(mode="after")
    def bounded_core(self):
        if not (self.start_seconds <= self.core_start_seconds < self.core_end_seconds <= self.end_seconds):
            raise ValueError("invalid chunk core")
        return self


class CoverageGap(Model):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    classification: str


class AudioCoverage(Model):
    duration_seconds: float = Field(gt=0)
    processed_seconds: float = Field(ge=0)
    complete_processing: bool
    windows: list[AudioWindow]
    gaps: list[CoverageGap] = Field(default_factory=list)
    note: str = "Processing coverage does not prove all spoken words were recognized."


class TranscriptionResult(Model):
    artifact: AudioArtifact
    transcript: Transcript
    provider: str
    model: str
    processing_seconds: float = Field(ge=0)
    coverage: AudioCoverage
    uncertainty: list[str] = Field(default_factory=list)


class ASRHypothesis(Model):
    text: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)


class ASRProvider(Protocol):
    name: str
    model_id: str

    def transcribe(self, wav_path: Path) -> list[ASRHypothesis]: ...


class FasterWhisperProvider:
    name = "faster-whisper"

    def __init__(self, model_id: str | None = None, *, local_files_only: bool = True):
        self.model_id = model_id or os.getenv("DUBGUARD_WHISPER_MODEL", "tiny.en")
        self.local_files_only = local_files_only
        self._model = None

    def transcribe(self, wav_path: Path) -> list[ASRHypothesis]:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise AudioError("Install requirements-audio.txt to enable local ASR") from exc
        if self._model is None:
            self._model = WhisperModel(self.model_id, device="cpu", compute_type="int8",
                                       cpu_threads=_max_int("DUBGUARD_ASR_CPU_THREADS", 2, 8), num_workers=1,
                                       local_files_only=self.local_files_only)
        segments, _ = self._model.transcribe(str(wav_path), language="en", beam_size=5,
                                               vad_filter=False, condition_on_previous_text=False)
        return [ASRHypothesis(text=s.text.strip(), start_seconds=s.start,
                              end_seconds=s.end) for s in segments if s.text.strip()]


def _max_int(name: str, default: int, upper: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise AudioError(f"{name} must be an integer") from exc
    if not 1 <= value <= upper:
        raise AudioError(f"{name} is outside its allowed range")
    return value


def _ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, FileNotFoundError) as exc:
        raise AudioError("FFmpeg is unavailable; install requirements-audio.txt or FFmpeg") from exc


def _format(data: bytes) -> str:
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:3] == b"ID3" or (len(data) >= 2 and data[0] == 0xff and data[1] & 0xe0 == 0xe0):
        return "mp3"
    if data[:4] == b"\x1a\x45\xdf\xa3" and b"webm" in data[:4096]:
        return "webm"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "mp4"
    raise AudioError("Supported audio containers: WAV, MP3, WebM/Opus and MP4/AAC")


AUDIO_MIME = {"wav": "audio/wav", "mp3": "audio/mpeg", "webm": "audio/webm", "mp4": "audio/mp4"}


def _probe(path: Path, fmt: str) -> None:
    """Inspect actual streams, not browser filenames or MIME claims."""
    try:
        import av
        with av.open(str(path), options={"protocol_whitelist": "file,pipe"}) as container:
            audio = list(container.streams.audio)
            if len(audio) != 1 or len(container.streams.video):
                raise AudioError("Exactly one audio stream and no video are required")
            codec = audio[0].codec_context.name
            if fmt == "webm" and codec != "opus":
                raise AudioError("WebM recording must contain Opus audio")
            if fmt == "mp4" and codec != "aac":
                raise AudioError("MP4 recording must contain AAC audio")
    except AudioError:
        raise
    except Exception as exc:
        raise AudioError("Audio stream probing failed; check format and local audio dependencies") from exc


@dataclass
class AudioStore:
    root: Path

    def __post_init__(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)

    def ingest(self, data: bytes, *, content_type: str | None = None, max_bytes: int | None = None, max_seconds: int | None = None) -> AudioArtifact:
        maximum = _max_int("DUBGUARD_MAX_UPLOAD_BYTES", 25_000_000, 250_000_000)
        maximum = min(maximum, max_bytes) if max_bytes else maximum
        if not data or len(data) > maximum:
            raise AudioError("Audio is empty or exceeds the configured upload limit")
        fmt = _format(data)
        claimed = (content_type or "").split(";")[0].lower()
        aliases = {"audio/x-wav": "audio/wav", "audio/mp3": "audio/mpeg", "audio/x-m4a": "audio/mp4"}
        claimed = aliases.get(claimed, claimed)
        if claimed not in {"", "application/octet-stream", AUDIO_MIME[fmt]}:
            raise AudioError("Claimed MIME type does not match the actual audio container")
        digest = sha256(data).hexdigest()
        target = self.path_for(digest, fmt)
        created = not target.exists()
        if created:
            descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(data)
            except BaseException:
                target.unlink(missing_ok=True)
                raise
        if sha256(target.read_bytes()).hexdigest() != digest:
            raise AudioError("Stored original audio hash mismatch")
        try:
            _probe(target, fmt)
            with tempfile.TemporaryDirectory(prefix="dubguard-audio-") as directory:
                decoded = Path(directory) / "decoded.wav"
                _decode(target, decoded, max_seconds=max_seconds)
                with wave.open(str(decoded), "rb") as stream:
                    duration = stream.getnframes() / stream.getframerate()
                    rate = stream.getframerate()
            limit = _max_int("DUBGUARD_MAX_AUDIO_SECONDS", 1200, 86400)
            limit = min(limit, max_seconds) if max_seconds else limit
            if not 0 < duration <= limit:
                raise AudioError("Audio duration is empty or exceeds the configured limit")
        except Exception:
            # An invalid upload must not be retained as a usable artifact.
            if created and target.exists():
                target.unlink(missing_ok=True)
            raise
        return AudioArtifact(id=digest, sha256=digest, format=fmt, byte_size=len(data),
                             duration_seconds=duration, sample_rate=rate)

    def path_for(self, digest: str, fmt: str) -> Path:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) or fmt not in AUDIO_MIME:
            raise AudioError("Invalid audio artifact identity")
        return self.root / f"{digest}.{fmt}"


def _decode(source: Path, target: Path, *, max_seconds: int | None = None) -> None:
    command = [_ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
               "-protocol_whitelist", "file,pipe", "-i", str(source), "-t",
               str(min(_max_int("DUBGUARD_MAX_AUDIO_SECONDS", 1200, 86400), max_seconds or 86400) + 1), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
               "-c:a", "pcm_s16le", str(target)]
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=180, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AudioError("Audio decoding timed out") from exc
    if result.returncode or not target.is_file():
        raise AudioError("Audio could not be decoded")


def _windows(duration: float, chunk_seconds: int, overlap_seconds: int) -> list[AudioWindow]:
    if not 0 <= overlap_seconds < chunk_seconds:
        raise AudioError("Chunk overlap must be smaller than chunk duration")
    windows = []
    start = 0.0
    while start < duration:
        core_end = min(duration, start + chunk_seconds)
        end = min(duration, core_end + overlap_seconds)
        windows.append(AudioWindow(index=len(windows), start_seconds=start, end_seconds=end,
                                   core_start_seconds=start, core_end_seconds=core_end))
        start = core_end
    return windows


def _speech_gaps(decoded: Path, segments: list[TranscriptSegment], duration: float) -> list[CoverageGap]:
    intervals = [(s.start_seconds, s.end_seconds) for s in segments]
    boundaries = []
    cursor = 0.0
    for start, end in intervals:
        if start - cursor >= 0.5:
            boundaries.append((cursor, start))
        cursor = max(cursor, end)
    if duration - cursor >= 0.5:
        boundaries.append((cursor, duration))
    gaps = []
    with wave.open(str(decoded), "rb") as reader:
        for start, end in boundaries:
            reader.setpos(min(reader.getnframes(), round(start * SAMPLE_RATE)))
            count = max(0, min(reader.getnframes(), round(end * SAMPLE_RATE)) - reader.tell())
            samples = array("h")
            samples.frombytes(reader.readframes(count))
            # Zero PCM is genuine digital silence; other low-energy regions are
            # only candidates, never proof that speech was absent.
            peak = max((abs(value) for value in samples), default=0)
            if peak == 0:
                classification = "digital_silence"
            else:
                rms = math.sqrt(sum(value * value for value in samples) / max(1, len(samples)))
                classification = "possible_silence" if rms < 250 else "unexplained_untranscribed_audio"
            gaps.append(CoverageGap(start_seconds=start, end_seconds=end,
                                    classification=classification))
    return gaps


def transcribe_artifact(store: AudioStore, artifact: AudioArtifact,
                        provider: ASRProvider | None = None) -> TranscriptionResult:
    provider = provider or FasterWhisperProvider()
    began = time.perf_counter()
    chunk_seconds = _max_int("DUBGUARD_ASR_CHUNK_SECONDS", 30, 600)
    overlap_seconds = int(os.getenv("DUBGUARD_ASR_OVERLAP_SECONDS", "2"))
    source = store.path_for(artifact.sha256, artifact.format)
    if not source.is_file() or sha256(source.read_bytes()).hexdigest() != artifact.sha256:
        raise AudioError("Original audio is missing or has changed")
    windows = _windows(artifact.duration_seconds, chunk_seconds, overlap_seconds)
    segments: list[TranscriptSegment] = []
    processed: list[AudioWindow] = []
    gaps: list[CoverageGap] = []
    timing_issues: list[str] = []
    with tempfile.TemporaryDirectory(prefix="dubguard-asr-") as directory:
        decoded = Path(directory) / "decoded.wav"
        _decode(source, decoded)
        with wave.open(str(decoded), "rb") as reader:
            if reader.getframerate() != SAMPLE_RATE or reader.getnchannels() != 1 or reader.getsampwidth() != SAMPLE_WIDTH:
                raise AudioError("Normalized audio has an unexpected format")
            total_frames = reader.getnframes()
            if abs(total_frames / SAMPLE_RATE - artifact.duration_seconds) > 0.05:
                raise AudioError("Audio duration changed since intake")
            for window in windows:
                first = round(window.start_seconds * SAMPLE_RATE)
                last = min(total_frames, round(window.end_seconds * SAMPLE_RATE))
                reader.setpos(first)
                frames = reader.readframes(last - first)
                chunk = Path(directory) / f"chunk-{window.index}.wav"
                with wave.open(str(chunk), "wb") as writer:
                    writer.setnchannels(1)
                    writer.setsampwidth(SAMPLE_WIDTH)
                    writer.setframerate(SAMPLE_RATE)
                    writer.writeframes(frames)
                length = (last - first) / SAMPLE_RATE
                for hypothesis in provider.transcribe(chunk):
                    if hypothesis.start_seconds >= length or hypothesis.end_seconds < hypothesis.start_seconds:
                        timing_issues.append(f"ASR returned an unusable timestamp in chunk {window.index}.")
                        continue
                    local_end = min(hypothesis.end_seconds, length)
                    if hypothesis.end_seconds > length + 0.05:
                        timing_issues.append(f"ASR end time exceeded chunk {window.index}; evidence was clipped to audio bounds.")
                    midpoint = window.start_seconds + (hypothesis.start_seconds + local_end) / 2
                    # One core owns overlap material. Duplicate hypotheses from
                    # neighbouring chunks are not silently repeated.
                    if not window.core_start_seconds <= midpoint < window.core_end_seconds + 1e-6:
                        continue
                    start = max(0.0, window.start_seconds + hypothesis.start_seconds)
                    end = min(artifact.duration_seconds, window.start_seconds + local_end)
                    if segments and start < segments[-1].end_seconds:
                        # Timing conflicts are evidence problems, not values to fix by guessing.
                        raise AudioError("ASR segments overlap after chunk mapping")
                    segments.append(TranscriptSegment(id=f"asr-{len(segments) + 1}", text=hypothesis.text,
                                                      start_seconds=start, end_seconds=end,
                                                      uncertain=True,
                                                      uncertainty_reason="ASR hypothesis requires human audio review"))
                processed.append(window)
                chunk.unlink(missing_ok=True)
        gaps = _speech_gaps(decoded, segments, artifact.duration_seconds)
    coverage = AudioCoverage(duration_seconds=artifact.duration_seconds,
                             processed_seconds=sum(w.core_end_seconds - w.core_start_seconds for w in processed),
                             complete_processing=len(processed) == len(windows), windows=processed,
                             gaps=gaps)
    return TranscriptionResult(artifact=artifact,
                               transcript=Transcript(source="asr", completeness="unknown", segments=segments),
                               provider=provider.name, model=provider.model_id,
                               processing_seconds=time.perf_counter() - began, coverage=coverage,
                               uncertainty=["ASR is provisional; missed speech is not independently excluded."] +
                               timing_issues +
                               (["Some audio with measurable signal has no transcribed words."] if any(
                                   g.classification == "unexplained_untranscribed_audio" for g in gaps) else []))
