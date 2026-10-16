"""Playwright-only ASR fixture. Never imported by the production application.
Audio decoding, storage, review APIs, SQLite and approval checks remain real.
"""
from dubguard.api import app
from dubguard.audio import ASRHypothesis, transcribe_artifact
import dubguard.review as review
import dubguard.quick as quick

class StubASR:
    name = "playwright-stub-not-real-recognition"
    model_id = "fixture-only"
    def transcribe(self, path):
        return [ASRHypothesis(text="Switch the power off.", start_seconds=0, end_seconds=.2)]

def fixture_transcribe(store, artifact):
    return transcribe_artifact(store, artifact, StubASR())

review.transcribe_artifact = fixture_transcribe
quick.transcribe_artifact = fixture_transcribe


class StubSecondary:
    name = "playwright-secondary-stub"
    model_id = "second-fixture-only"
    def __init__(self, *args, **kwargs):
        pass
    def transcribe(self, path):
        return [ASRHypothesis(text="Switch the power on.", start_seconds=0, end_seconds=.2)]

review.FasterWhisperProvider = StubSecondary
