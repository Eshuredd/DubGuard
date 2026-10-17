"""Playwright-only ASR fixture. Never imported by the production application.
Audio decoding, storage, review APIs, SQLite and approval checks remain real.
"""
from dubguard.api import app
from dubguard.audio import ASRHypothesis, transcribe_artifact
import dubguard.review as review
import dubguard.quick as quick
import json
import os
import httpx
from dubguard.providers import AMDTokenFactoryProvider

# Hard override real .env values. This test server cannot send a paid request.
os.environ['AMD_TOKEN_FACTORY_ENDPOINT'] = 'https://playwright.invalid/v1'
os.environ['AMD_TOKEN_FACTORY_MODEL'] = 'DeepSeek-V4-Flash'
os.environ['AMD_TOKEN_FACTORY_API_KEY'] = 'playwright-test-only-not-a-credential'

def semantic_fixture(req):
    source = json.loads(json.loads(req.content)['messages'][1]['content'].split('\n', 1)[1])
    instruction = source['script']['instructions'][0]
    segment = source['transcript']['segments'][0]
    finding = {'requirement_id': source['policy']['constraints'][0]['id'], 'kind': 'POLARITY',
        'verdict': 'UNRESOLVED', 'instruction_id': instruction['id'],
        'approved_evidence': [{'instruction_id': instruction['id'], 'quote': instruction['text']}],
        'observed_evidence': [{'instruction_id': instruction['id'], 'segment_id': segment['id'],
                               'quote': segment['text']}], 'explanation': 'Playwright mocked evidence only.'}
    if source['script']['id'] == 'fifteen-fifty':
        finding['approved_evidence'][0]['quote'] = 'Fabricated citation for rejection test'
    return httpx.Response(200, json={'id': 'playwright-mock-call', 'model': 'playwright-mock-no-real-AMD',
        'choices': [{'message': {'content': json.dumps({'verdict': 'UNRESOLVED',
            'explanation': 'Mocked HTTP, not actual AMD inference.', 'findings': [finding]})}}]})

quick.AMDTokenFactoryProvider = lambda **kw: AMDTokenFactoryProvider(
    client=httpx.Client(transport=httpx.MockTransport(semantic_fixture)), **kw)

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
