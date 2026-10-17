"""Phase 4 protocol/security checks. Synthetic PCM, stub ASR, mocked HTTP only."""
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from dubguard.api import app
from dubguard.audio import ASRHypothesis, transcribe_artifact
from dubguard.providers import AMDTokenFactoryProvider
from dubguard.quick import database, _AMD_SLOT, _DEMO_SLOTS
from test_phase3 import quick, wav_bytes
from test_phase2c import workflow, attest, run, sign


def submit(client, token, **query):
    return client.post('/quick/analyze', params={'scenario_id': 'correct', **query},
        headers={'Authorization': 'Bearer '+token}, files={'file': ('a.wav', wav_bytes(), 'audio/wav')})


@pytest.fixture
def amd(quick, monkeypatch):
    client, s, root = quick
    monkeypatch.setenv('AMD_TOKEN_FACTORY_MODEL', 'DeepSeek-V4-Flash')
    monkeypatch.setenv('AMD_TOKEN_FACTORY_ENDPOINT', 'https://unit.test/v1')
    monkeypatch.setenv('AMD_TOKEN_FACTORY_API_KEY', 'phase4-private-test-secret')
    # Deliberately high environment retry limit must be overridden per Quick Test call.
    monkeypatch.setenv('AMD_TOKEN_FACTORY_MAX_RETRIES', '3')
    class ASR:
        name, model_id = 'stub', 'not-real'
        def transcribe(self, path):
            return [ASRHypothesis(text='Switch the power off.', start_seconds=0, end_seconds=.3)]
    monkeypatch.setattr('dubguard.quick.transcribe_artifact', lambda store, artifact: transcribe_artifact(store, artifact, ASR()))
    calls = []
    def handler(req):
        calls.append(req)
        finding = {'requirement_id': 'protected-1', 'kind': 'POLARITY', 'verdict': 'UNRESOLVED',
            'instruction_id': 'step-1', 'approved_evidence': [{'instruction_id': 'step-1', 'quote': 'Switch the power off.'}],
            'observed_evidence': [{'instruction_id': 'step-1', 'segment_id': 'asr-1', 'quote': 'Switch the power off.'}],
            'explanation': 'Mocked source comparison.'}
        content = {'verdict': 'UNRESOLVED', 'explanation': 'Mocked HTTP response only.', 'findings': [finding]}
        return httpx.Response(200, json={'id': 'mock-call', 'model': 'self-dploy/DeepSeek-V4-Flash',
            'choices': [{'message': {'content': json.dumps(content)}, 'finish_reason': 'stop'}]})
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr('dubguard.quick.AMDTokenFactoryProvider', lambda **kw: AMDTokenFactoryProvider(client=httpx.Client(transport=transport), **kw))
    return client, s, calls, transport


def report(client, s):
    return client.get('/quick/session', headers={'Authorization': 'Bearer '+s['token']}).json()


def test_local_default_and_consent_fail_closed(amd):
    c, s, calls, _ = amd
    assert submit(c, s['token']).status_code == 200
    assert not calls
    assert report(c, s)['mode'] == 'local'
    assert report(c, s)['verification']['semantic'] is None
    for mode, consent in [('amd', False), ('unknown', True)]:
        assert submit(c, s['token'], mode=mode, consent=consent).status_code == 422
    assert submit(c, 'invalid', mode='amd', consent=True).status_code == 401
    assert not calls and report(c, s)['runs'] == 1


def test_amd_real_pipeline_mocked_http_provenance_and_text_boundary(amd):
    c, s, calls, _ = amd
    assert submit(c, s['token'], mode='amd', consent=True).status_code == 200
    r = report(c, s)
    assert r['state'] == 'COMPLETE' and r['amd_runs'] == 1 and r['consented_at'] <= time.time()
    assert r['semantic_status'] == 'completed'
    a = r['semantic_verification']['semantic']
    assert a['attempts'] == 1 and a['latency_ms'] >= 0 and a['call_id'] == 'mock-call'
    assert a['findings'][0]['observed'][0]['end_seconds'] == .3
    assert a['findings'][0]['verdict'] == 'UNRESOLVED'  # source ASR remains provisional
    assert r['verification']['mode'] == 'deterministic' and r['verification']['semantic'] is None
    assert r['semantic_verification']['decision'] == 'REVIEW_REQUIRED'
    body = json.loads(calls[0].content)
    assert body['model'] == 'DeepSeek-V4-Flash' and body['max_tokens'] == 1024
    source = json.loads(body['messages'][1]['content'].split('\n', 1)[1])
    assert set(source) == {'script', 'policy', 'transcript', 'citation_templates'}
    assert source['transcript']['source'] == 'asr'
    assert source['transcript']['segments'][0]['uncertain'] is True
    assert 'phase4-private-test-secret' not in json.dumps(r) + json.dumps(body)
    assert 'audio' not in source and 'artifact' not in source


@pytest.mark.parametrize('failure', ['timeout', 'rate_limit', 'invalid_response', 'invalid_citations'])
def test_amd_failures_keep_local_evidence_and_use_one_attempt(amd, failure):
    c, s, calls, transport = amd
    def fail(req):
        calls.append(req)
        if failure == 'timeout':
            raise httpx.ReadTimeout('private transport detail')
        if failure == 'rate_limit':
            return httpx.Response(429, text='private error body')
        content = {'verdict': 'DEVIATION', 'explanation': 'Mock only', 'findings': [
            {'requirement_id': 'invented', 'kind': 'POLARITY', 'verdict': 'DEVIATION',
             'instruction_id': 'invented', 'approved_evidence': [], 'observed_evidence': [], 'explanation': 'fabricated'}]}
        return httpx.Response(200, json={'id': 'mock', 'model': 'mock', 'choices': [{'message': {
            'content': 'bad json' if failure == 'invalid_response' else json.dumps(content)}}]})
    transport.handler = fail
    assert submit(c, s['token'], mode='amd', consent=True).status_code == 200
    r = report(c, s)
    assert len(calls) == 1 and r['verification'] and r['state'] == 'COMPLETE'
    assert r['semantic_verification']['decision'] == 'REVIEW_REQUIRED'
    a = r['semantic_verification']['semantic']
    assert a['error_class'] == ('read_timeout' if failure == 'timeout' else failure)
    assert a['findings'] == []
    assert 'private' not in json.dumps(r)


def test_amd_quotas_survive_new_client_and_bound_global_jobs(amd):
    c, s, calls, _ = amd
    for _ in range(2):
        assert submit(c, s['token'], mode='amd', consent=True).status_code == 200
    assert submit(TestClient(app), s['token'], mode='amd', consent=True).status_code == 429
    assert len(calls) == 2
    assert submit(c, s['token']).status_code == 200  # local third run retained
    assert len(calls) == 2
    other = c.post('/quick/sessions', headers={'X-Demo-Code': 'test-only-demo-access-code-long'}).json()
    with database() as db:
        db.execute("UPDATE sessions SET state='PROCESSING',payload=? WHERE id=?", (json.dumps({'mode': 'amd'}), s['id']))
    assert submit(c, other['token'], mode='amd', consent=True).status_code == 429
    with database() as db:
        db.execute("UPDATE sessions SET state='COMPLETE' WHERE id=?", (s['id'],))
    assert _AMD_SLOT.acquire(blocking=False)
    try:
        assert submit(c, other['token'], mode='amd', consent=True).status_code == 200
        assert len(calls) == 2  # slot still held even if original session was deleted
        assert report(c, other)['semantic_status'] == 'unavailable'
    finally:
        _AMD_SLOT.release()


def test_quick_wrong_semantic_model_never_calls_audio_model(amd, monkeypatch):
    c, s, calls, _ = amd
    monkeypatch.setenv('AMD_TOKEN_FACTORY_MODEL', 'MiMo-V2.6-Flash')
    assert submit(c, s['token'], mode='amd', consent=True).status_code == 200
    assert not calls and report(c, s)['semantic_status'] == 'unavailable'


def test_demo_runtime_slots_cannot_be_bypassed_by_deleted_sessions(quick):
    c, s, _ = quick
    assert _DEMO_SLOTS.acquire(blocking=False) and _DEMO_SLOTS.acquire(blocking=False)
    try:
        assert submit(c, s['token']).status_code == 429
        assert report(c, s)['runs'] == 0
    finally:
        _DEMO_SLOTS.release()
        _DEMO_SLOTS.release()
    assert submit(c, s['token']).status_code == 200


def test_failed_local_asr_never_sends_text_to_amd(amd, monkeypatch):
    c, s, calls, _ = amd
    def fail(*args):
        raise RuntimeError('private detail')
    monkeypatch.setattr('dubguard.quick.transcribe_artifact', fail)
    assert submit(c, s['token'], mode='amd', consent=True).status_code == 200
    assert not calls
    r = report(c, s)
    assert r['state'] == 'FAILED' and r['amd_runs'] == 1
    assert r['semantic_status'] == 'not_completed'
    assert 'private detail' not in json.dumps(r)


@pytest.mark.parametrize('state', ['TRANSCRIBING', 'VERIFYING', 'ACOUSTIC_RECHECKING'])
def test_restart_invalidates_interrupted_review_and_never_replays(workflow, state):
    c, store, wid = workflow
    attest(c, store, wid)
    old = run(c, wid)
    store.mark_state(wid, {'IN_REVIEW'}, state, 'human')
    assert store.recover_interrupted() == 1
    assert store.workflow(wid)['verification_record_id'] is None
    assert store.workflow(wid)['state'].endswith('FAILED')
    assert sign(c, wid, old['record_id']).status_code == 409
    assert store.recover_interrupted() == 0
    assert any(e['event'] == 'INTERRUPTED_ON_RESTART' for e in store.audit(workflow_id=wid))


def test_smoke_capture_is_opt_in_and_records_rejected_raw_citations(case_request, monkeypatch, tmp_path):
    from dubguard.smoke import main
    monkeypatch.setenv('AMD_TOKEN_FACTORY_MODEL', 'DeepSeek-V4-Flash')
    monkeypatch.setenv('AMD_TOKEN_FACTORY_ENDPOINT', 'https://unit.test/v1')
    monkeypatch.setenv('AMD_TOKEN_FACTORY_API_KEY', 'never-export-this')
    calls = []
    def handler(req):
        calls.append(req)
        return httpx.Response(200, json={'id': 'mock', 'model': 'mocked-model', 'choices': [
            {'message': {'content': '{"verdict":"DEVIATION","explanation":"mock","findings":[]}'}}]})
    monkeypatch.setattr('dubguard.smoke.AMDTokenFactoryProvider', lambda **kw: AMDTokenFactoryProvider(client=httpx.Client(transport=httpx.MockTransport(handler)), **kw))
    source = tmp_path / 'input.json'
    source.write_text(case_request('A01').model_dump_json())
    output = tmp_path / 'report.json'
    assert main(['semantic', str(source), '--output', str(output)]) == 0
    assert not output.exists() and not calls
    assert main(['semantic', str(source), '--execute', '--output', str(output)]) == 0
    r = json.loads(output.read_text(encoding='utf-8'))
    assert len(calls) == 1 and r['assessment']['attempts'] == 1
    assert r['citation_status'] == 'rejected_or_partial' and r['actual_response']['id'] == 'mock'
    assert r['assessment']['error_class'] == 'invalid_citations'
    assert 'never-export-this' not in output.read_text()


def test_readiness_is_honest_and_never_calls_remote(tmp_path, monkeypatch):
    import dubguard.readiness as checks
    monkeypatch.setenv('DUBGUARD_WHISPER_MODEL', str(tmp_path))
    monkeypatch.setattr(checks, '_ffmpeg', lambda: __file__)
    monkeypatch.setattr(checks.importlib.util, 'find_spec', lambda name: object())
    c = TestClient(app)
    missing = c.get('/ready')
    assert missing.status_code == 503 and not missing.json()['whisper_cached']
    for name in ('model.bin', 'config.json', 'tokenizer.json'):
        (tmp_path / name).touch()
    present = c.get('/ready')
    assert present.status_code == 200 and present.json()['ready']
    assert str(tmp_path) not in present.text  # readiness reveals no private filesystem path


def test_single_attempt_override_does_not_mutate_process_configuration(case_request, monkeypatch):
    import os
    monkeypatch.setenv('AMD_TOKEN_FACTORY_MODEL', 'DeepSeek-V4-Flash')
    monkeypatch.setenv('AMD_TOKEN_FACTORY_ENDPOINT', 'https://unit.test/v1')
    monkeypatch.setenv('AMD_TOKEN_FACTORY_API_KEY', 'private-test-only')
    monkeypatch.setenv('AMD_TOKEN_FACTORY_MAX_RETRIES', '3')
    calls = []
    def fail(req):
        calls.append(req)
        return httpx.Response(503)
    provider = AMDTokenFactoryProvider(client=httpx.Client(transport=httpx.MockTransport(fail)), max_retries=0)
    result = provider.verify(case_request('A01'))
    assert result.attempts == len(calls) == 1
    assert os.environ['AMD_TOKEN_FACTORY_MAX_RETRIES'] == '3'


def test_real_faster_whisper_audio_decoder_accepts_installed_pyav(tmp_path):
    # No model, network, stub decoder, or speech labels. Catches PyAV 19 incompatibility.
    decoder = pytest.importorskip('faster_whisper.audio')
    source = tmp_path / 'silence.wav'
    source.write_bytes(wav_bytes())
    decoded = decoder.decode_audio(str(source), sampling_rate=16000)
    assert len(decoded) == 6400 and not decoded.any()


def test_quick_restart_retains_consent_quota_and_completed_local_evidence(amd):
    from dubguard.quick import recover_interrupted
    c, s, calls, _ = amd
    assert submit(c, s['token'], mode='amd', consent=True).status_code == 200
    before = report(c, s)
    with database() as db:
        db.execute("UPDATE sessions SET state='PROCESSING' WHERE id=?", (s['id'],))
    recover_interrupted()
    after = report(c, s)
    assert len(calls) == 1 and after['amd_runs'] == 1
    assert after['consented_at'] == before['consented_at']
    assert after['mode'] == 'amd' and after['semantic_status'] == 'interrupted'
    assert after['verification'] == before['verification']
