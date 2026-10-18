"""Temporary custom review: real codecs/rules, synthetic silence and stub ASR only."""
import json
import time
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from dubguard.api import app
from dubguard.audio import ASRHypothesis, transcribe_artifact
from dubguard.quick import database, cleanup, _DEMO_SLOTS
from test_phase3 import wav_bytes


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv('DUBGUARD_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('DUBGUARD_PUBLIC_AMD_ENABLED', 'false')
    monkeypatch.setenv('DUBGUARD_CLIENT_SESSIONS_PER_HOUR', '30')
    monkeypatch.setenv('DUBGUARD_CLIENT_UPLOADS_PER_HOUR', '90')
    monkeypatch.setenv('DUBGUARD_CLIENT_EDITS_PER_HOUR', '120')
    monkeypatch.setenv('DUBGUARD_TRUSTED_PROXIES', '')
    monkeypatch.setenv('DUBGUARD_REVIEW_TOKENS_JSON', json.dumps({'operator': 'independent-test-operator-token-long'}))
    class Stub:
        name, model_id = 'stub-synthetic-test-only', 'not-real-recognition'
        def transcribe(self, path):
            return [ASRHypothesis(text='Wait 50 minutes before restarting.', start_seconds=0, end_seconds=.3)]
    monkeypatch.setattr('dubguard.quick.transcribe_artifact', lambda s, a: transcribe_artifact(s, a, Stub()))
    def forbidden(*a, **kw):
        pytest.fail('Custom workspace must not construct an AMD provider')
    monkeypatch.setattr('dubguard.quick.AMDTokenFactoryProvider', forbidden)
    c = TestClient(app)
    created = c.post('/workspace/sessions')
    assert created.status_code == 200
    return c, created.json(), tmp_path


def headers(s):
    return {'Authorization': 'Bearer '+s['token']}


def view(c, s):
    r = c.get('/workspace/session', headers=headers(s))
    assert r.status_code == 200
    return r.json()


def reference(revision=0):
    return {'expected_revision': revision, 'title': 'Custom restart delay',
            'instructions': [{'text': 'Wait 15 minutes before restarting.', 'alternatives': []}],
            'requirements': [{'id': 'delay', 'kind': 'numeric', 'instruction_id': 'step-1'}]}


def save(c, s, payload=None):
    return c.put('/workspace/reference', headers=headers(s), json=payload or reference(view(c, s)['workspace']['revision']))


def analyze(c, s):
    return c.post('/workspace/analyze', params={'expected_revision': view(c, s)['workspace']['revision']},
                  headers=headers(s), files={'file': ('synthetic.wav', wav_bytes(), 'audio/wav')})


def correction(revision, text='Wait 50 minutes before restarting.'):
    return {'expected_revision': revision, 'listened_to_original': True, 'reason': 'Synthetic protocol test only; not human speech ground truth',
            'transcript': {'source': 'manual', 'completeness': 'complete', 'segments': [
                {'id': 'visitor-1', 'instruction_id': 'step-1', 'text': text, 'start_seconds': 0, 'end_seconds': .3, 'uncertain': False}]}}


@pytest.mark.parametrize('legacy', [None, 'false', 'true'])
def test_always_available_without_activation(ws, monkeypatch, legacy):
    c, s, _ = ws
    if legacy is None:
        monkeypatch.delenv('DUBGUARD_PUBLIC_WORKSPACE', raising=False)
    else:
        monkeypatch.setenv('DUBGUARD_PUBLIC_WORKSPACE', legacy)
    assert c.get('/workspace/config').json()['enabled'] is True
    assert c.post('/workspace/sessions').status_code == 200
    assert save(c, s).status_code == 200
    assert analyze(c, s).status_code == 200
    assert c.delete('/workspace/session', headers=headers(s)).status_code == 200


def test_custom_reference_real_audio_and_rules_keep_asr_provisional(ws):
    c, s, _ = ws
    assert len(s['token']) >= 43
    assert save(c, s).status_code == 200 and analyze(c, s).status_code == 200
    data = view(c, s)
    assert data['workspace']['reference']['policy']['approved_by'].startswith('visitor-demo-only')
    assert data['analysis']['state'] == 'COMPLETE'
    assert data['analysis']['reference_policy']['script']['instructions'][0]['text'] == 'Wait 15 minutes before restarting.'
    result = data['analysis']['verification']
    assert result['decision'] == 'REVIEW_REQUIRED'
    assert any(f['rule_id'].startswith('ASR.SUSPECTED.NUMERIC') for f in result['findings'])
    assert data['analysis']['amd_runs'] == 0
    assert data['analysis']['artifact']['sha256'] == sha256(wav_bytes()).hexdigest()
    assert c.get('/workspace/audio', headers=headers(s)).content == wav_bytes()


def test_corrections_run_real_rules_and_do_not_create_authenticated_approvals(ws):
    c, s, root = ws
    save(c, s); analyze(c, s)
    original = view(c, s)['analysis']['transcription']
    r = c.put('/workspace/evidence', headers=headers(s), json=correction(view(c, s)['workspace']['revision']))
    assert r.status_code == 200 and r.json()['organizational_approval'] is False
    data = view(c, s)
    assert data['analysis']['transcription'] == original
    assert data['workspace']['evidence']['result']['decision'] == 'CRITICAL_DEVIATION'
    assert 'not authenticated' in data['workspace']['evidence']['provenance']
    review = {'expected_revision': data['workspace']['revision'], 'notes': 'Needs a new take.', 'reviewed': [0], 'demo_decision': 'REQUEST_NEW_RECORDING'}
    assert c.put('/workspace/review', headers=headers(s), json=review).status_code == 200
    exported = c.get('/workspace/export', headers=headers(s)).json()
    assert exported['workspace']['demo_decision'] == 'REQUEST_NEW_RECORDING'
    assert 'release authorization' in exported['notice']
    assert not (root/'review.sqlite3').exists()
    review['expected_revision'] += 1
    review['demo_decision'] = 'APPROVED'
    assert c.put('/workspace/review', headers=headers(s), json=review).status_code == 422
    for path in ['/review/workflows', '/review/policy-records']:
        assert c.get(path, headers=headers(s)).status_code == 401
    for path in ['/review/policy-drafts/real/approve', '/review/workflows/real/signoff', '/review/workflows/real/transcript-evidence']:
        assert c.post(path, headers=headers(s), json={}).status_code in {401, 422}


def test_session_scopes_cannot_cross_custom_sample_or_operator_boundaries(ws):
    c, a, _ = ws
    b = c.post('/workspace/sessions').json()
    save(c, a); analyze(c, a)
    assert view(c, b)['workspace']['reference'] is None
    assert c.get('/workspace/audio', headers=headers(b)).status_code == 404
    assert c.get('/workspace/session', params={'id': a['id']}, headers=headers(b)).json()['analysis']['id'] == b['id']
    assert c.get('/quick/audio', headers=headers(a)).status_code == 401
    assert c.delete('/quick/session', headers=headers(a)).status_code == 401
    sample = c.post('/quick/sessions').json()
    assert c.get('/workspace/session', headers=headers(sample)).status_code == 401
    assert c.get('/workspace/session', headers={'Authorization': 'Bearer independent-test-operator-token-long'}).status_code == 401
    assert c.delete('/workspace/session', headers=headers(b)).status_code == 200
    assert c.get('/workspace/audio', headers=headers(a)).status_code == 200


@pytest.mark.parametrize('field,value', [('reviewer_id','operator'), ('approved_by','operator'), ('approval','APPROVED')])
def test_reference_cannot_impersonate_operator(ws, field, value):
    c, s, _ = ws
    body = reference(); body[field] = value
    assert save(c, s, body).status_code == 422


@pytest.mark.parametrize('kind', ['polarity', 'warning', 'sequence'])
def test_supported_custom_constraints_and_variants(ws, kind):
    c, s, _ = ws
    payload = reference()
    payload['instructions'] = [{'text': 'Switch the power off.', 'alternatives': ['Turn the power off.']}, {'text': 'Wear gloves.'}]
    payload['requirements'] = [{'id': 'protect', 'kind': kind, **(
        {'instruction_ids': ['step-1','step-2']} if kind == 'sequence' else
        {'instruction_id': 'step-1', 'approved_phrase': 'off', 'reversed_phrase': 'on'} if kind == 'polarity' else
        {'instruction_id': 'step-2', 'forbidden_wordings': ['Gloves are optional.']})}]
    assert save(c, s, payload).status_code == 200


def test_reference_schema_bounds_and_coherence(ws):
    c, s, _ = ws
    for change in [{'requirements': [{'kind': 'unsupported', 'id': 'bad'}]}, {'instructions': [{'text': 'No number here'}]}, {'instructions': [{'text': 'x'*2001}]}]:
        assert save(c, s, {**reference(), **change}).status_code == 422
    assert c.put('/workspace/reference', headers=headers(s), content=b'x'*32769).status_code == 413
    assert view(c, s)['workspace']['reference'] is None


def test_stale_reference_evidence_and_invalid_audio_spans_rejected(ws):
    c, s, _ = ws
    save(c,s); analyze(c,s)
    current = view(c,s)
    body = correction(current['workspace']['revision'])
    body['transcript']['segments'][0]['end_seconds'] = 20
    assert c.put('/workspace/evidence', headers=headers(s), json=body).status_code == 422
    body = reference(current['workspace']['revision']); body['instructions'][0]['text'] = 'Wait 20 minutes before restarting.'
    assert save(c,s,body).status_code == 200
    assert c.put('/workspace/evidence', headers=headers(s), json=correction(view(c,s)['workspace']['revision'])).status_code == 409
    assert save(c,s,body).status_code == 409
    assert c.post('/workspace/analyze?expected_revision=0', headers=headers(s), files={'file': ('a.wav', wav_bytes(), 'audio/wav')}).status_code == 409


def test_corrected_uncertainty_and_new_recording_invalidate_demo_decisions(ws):
    c, s, _ = ws
    save(c,s); analyze(c,s)
    body = correction(view(c,s)['workspace']['revision'])
    body['transcript']['segments'][0]['uncertain'] = True
    assert c.put('/workspace/evidence', headers=headers(s), json=body).status_code == 200
    data = view(c,s)['workspace']
    assert data['evidence']['result']['decision'] == 'REVIEW_REQUIRED'
    assert c.put('/workspace/review', headers=headers(s), json={'expected_revision': data['revision'], 'notes': 'Unclear', 'reviewed': [], 'demo_decision': 'NEEDS_REVIEW'}).status_code == 200
    assert analyze(c,s).status_code == 200
    data = view(c,s)['workspace']
    assert data['evidence'] is None and data['demo_decision'] is None and data['reviewed'] == []


def test_custom_unconfigured_amd_never_constructs_provider(ws):
    c, s, _ = ws
    save(c,s)
    assert c.post('/workspace/analyze?mode=amd&consent=true&expected_revision=1', headers=headers(s), content=b'not parsed').status_code == 503
    assert view(c,s)['analysis']['runs'] == 0


def test_global_runtime_and_per_session_analysis_quotas(ws):
    c,s,_ = ws
    save(c,s)
    assert _DEMO_SLOTS.acquire(False) and _DEMO_SLOTS.acquire(False)
    try:
        assert analyze(c,s).status_code == 429
    finally:
        _DEMO_SLOTS.release(); _DEMO_SLOTS.release()
    for _ in range(3):
        assert analyze(c,s).status_code == 200
    assert analyze(c,s).status_code == 429


def test_expiry_deletion_and_persistent_shared_admission(ws, monkeypatch):
    c,s,root = ws
    save(c,s); analyze(c,s)
    monkeypatch.setenv('DUBGUARD_CLIENT_SESSIONS_PER_HOUR', '2')
    sample = c.post('/quick/sessions').json()
    assert c.post('/workspace/sessions').status_code == 429
    assert c.delete('/workspace/session', headers=headers(s)).status_code == 200
    assert not (root/'quick'/s['id']).exists()
    assert c.post('/workspace/sessions').status_code == 429
    assert c.get('/workspace/audio', headers=headers(s)).status_code == 401
    with database() as db:
        db.execute('UPDATE sessions SET expires=0 WHERE id=?', (sample['id'],))
    cleanup()
    assert c.post('/workspace/sessions').status_code == 429


def test_original_hash_tampering_blocks_corrections(ws):
    c,s,root = ws
    save(c,s); analyze(c,s)
    artifact = view(c,s)['analysis']['artifact']
    path = next((root/'quick'/s['id']).rglob('*.wav'))
    path.write_bytes(b'tampered')
    assert c.get('/workspace/audio', headers=headers(s)).status_code == 404
    assert c.put('/workspace/evidence', headers=headers(s), json=correction(view(c,s)['workspace']['revision'])).status_code == 409


def test_custom_metadata_client_budget_is_persistent_across_sessions(ws, monkeypatch):
    c,s,_ = ws
    monkeypatch.setenv('DUBGUARD_CLIENT_EDITS_PER_HOUR','1')
    assert save(c,s).status_code == 200
    other=c.post('/workspace/sessions').json()
    assert save(c,other).status_code == 429


def test_custom_expiry_removes_audio_and_rejects_export(ws):
    c,s,root=ws
    save(c,s);analyze(c,s)
    with database() as db:
        db.execute('UPDATE sessions SET expires=0 WHERE id=?',(s['id'],))
    assert c.get('/workspace/export',headers=headers(s)).status_code==401
    assert c.get('/workspace/audio',headers=headers(s)).status_code==401
    assert not (root/'quick'/s['id']).exists()


def test_per_session_metadata_changes_are_bounded(ws):
    c,s,_=ws
    save(c,s);analyze(c,s)
    for i in range(29):
        data=view(c,s)['workspace']
        assert c.put('/workspace/review',headers=headers(s),json={'expected_revision':data['revision'],'notes':f'Demo note {i}','reviewed':[],'demo_decision':'NEEDS_REVIEW'}).status_code==200
    data=view(c,s)['workspace']
    assert c.put('/workspace/review',headers=headers(s),json={'expected_revision':data['revision'],'notes':'Limit must hold','reviewed':[],'demo_decision':'REVIEWED'}).status_code==429


def test_audio_returns_the_exact_verified_buffer_without_a_second_file_read(ws, monkeypatch):
    from pathlib import Path
    from dubguard.audio import AudioStore
    c,s,root=ws
    save(c,s);analyze(c,s)
    artifact=view(c,s)['analysis']['artifact']
    path=AudioStore(root/'quick'/s['id']).path_for(artifact['sha256'],artifact['format'])
    original=Path.read_bytes
    reads=[]
    def changing(source):
        if source==path:
            reads.append(True)
            return wav_bytes() if len(reads)==1 else b'changed after hash verification'
        return original(source)
    monkeypatch.setattr(Path,'read_bytes',changing)
    assert c.get('/workspace/audio',headers=headers(s)).content==wav_bytes()
    assert len(reads)==1
