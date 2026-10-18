"""Actual codec/transport tests plus explicitly stubbed recognition; no paid calls."""
import io
import json
import subprocess
import time
import wave
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from dubguard.api import app
from dubguard.audio import AudioError, AudioStore, ASRHypothesis, _ffmpeg, _format, transcribe_artifact
from dubguard.quick import cleanup, database, recover_interrupted
from dubguard.review import ReviewStore
from dubguard.acoustic import TargetedRecheckResult, AcousticAssessment, AcousticDisagreement
from dubguard.schemas import Transcript


def wav_bytes(seconds=.4):
    data=io.BytesIO()
    with wave.open(data,'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(b'\0\0'*int(seconds*16000))
    return data.getvalue()


@pytest.mark.parametrize('fmt,codec,mime',[('webm','libopus','audio/webm;codecs=opus'),('mp4','aac','audio/mp4')])
def test_real_browser_container_decode_preserves_original(tmp_path,fmt,codec,mime):
    source=tmp_path/'source.wav';source.write_bytes(wav_bytes())
    target=tmp_path/('capture.'+fmt)
    subprocess.run([_ffmpeg(),'-loglevel','error','-i',str(source),'-c:a',codec,str(target)],check=True)
    data=target.read_bytes();store=AudioStore(tmp_path/'artifacts');artifact=store.ingest(data,content_type=mime)
    assert artifact.format==fmt and artifact.sha256==sha256(data).hexdigest()
    assert store.path_for(artifact.sha256,fmt).read_bytes()==data
    assert 0<artifact.duration_seconds<1
    with pytest.raises(AudioError,match='MIME'):
        store.ingest(data,content_type='audio/wav')


@pytest.mark.parametrize('data',[b'not audio',b'\x1aE\xdf\xa3webmgarbage',b'1234ftypgarbage',b'RIFF1234WAVEbad'])
def test_invalid_browser_audio_rejected(tmp_path,data):
    with pytest.raises(AudioError):AudioStore(tmp_path).ingest(data)
    assert not [p for p in tmp_path.iterdir() if p.suffix in {'.wav','.mp4','.webm'}]


def test_browser_format_limits(tmp_path):
    store=AudioStore(tmp_path)
    with pytest.raises(AudioError):store.ingest(wav_bytes(),max_bytes=10)
    with pytest.raises(AudioError):store.ingest(wav_bytes(1),max_seconds=.1)


@pytest.fixture
def quick(tmp_path,monkeypatch):
    monkeypatch.setenv('DUBGUARD_DATA_DIR',str(tmp_path))
    monkeypatch.setenv('DUBGUARD_DEMO_ACCESS_CODE','test-only-demo-access-code-long')
    monkeypatch.setenv('DUBGUARD_PUBLIC_LOCAL_DEMO','false')
    # These tests isolate session/global quotas; Phase 6 exercises client defaults.
    monkeypatch.setenv('DUBGUARD_CLIENT_SESSIONS_PER_HOUR','30')
    monkeypatch.setenv('DUBGUARD_CLIENT_UPLOADS_PER_HOUR','90')
    class Stub:
        name,model_id='stub','not-real-asr'
        def transcribe(self,path):return [ASRHypothesis(text='Switch the power on.',start_seconds=0,end_seconds=.3)]
    monkeypatch.setattr('dubguard.quick.transcribe_artifact',lambda store,artifact:transcribe_artifact(store,artifact,Stub()))
    client=TestClient(app)
    created=client.post('/quick/sessions',headers={'X-Demo-Code':'test-only-demo-access-code-long'})
    assert created.status_code==200
    return client,created.json(),tmp_path


def test_quick_actual_api_pipeline_is_advisory(quick):
    client,session,root=quick;headers={'Authorization':'Bearer '+session['token']}
    assert client.get('/quick/session').status_code==401
    response=client.post('/quick/analyze?scenario_id=on-off',headers=headers,files={'file':('capture.wav',wav_bytes(),'audio/wav')})
    assert response.status_code==200
    report=client.get('/quick/session',headers=headers).json()
    assert report['state']=='COMPLETE' and report['verification']['decision']=='REVIEW_REQUIRED'
    assert any(f['rule_id']=='ASR.SUSPECTED.POLARITY.REVERSED' for f in report['verification']['findings'])
    assert report['transcription']['transcript']['segments'][0]['end_seconds']==.3
    assert client.get('/quick/audio',headers=headers).content==wav_bytes()
    assert client.get('/quick/audio').status_code==401
    assert client.post('/review/workflows',headers=headers,json={}).status_code in {401,503}
    assert client.delete('/quick/session',headers=headers).status_code==200
    assert client.get('/quick/session',headers=headers).status_code==401
    assert not (root/'quick'/session['id']).exists()


def test_quick_quota_expiry_and_disabled(quick,monkeypatch):
    client,s,root=quick;h={'Authorization':'Bearer '+s['token']}
    for _ in range(3):
        assert client.post('/quick/analyze?scenario_id=correct',headers=h,files={'file':('a.wav',wav_bytes(),'audio/wav')}).status_code==200
    assert client.post('/quick/analyze?scenario_id=correct',headers=h,files={'file':('a.wav',wav_bytes(),'audio/wav')}).status_code==429
    with database() as db:db.execute('UPDATE sessions SET expires=? WHERE id=?',(time.time()-1,s['id']))
    cleanup();assert not (root/'quick'/s['id']).exists()
    assert client.get('/quick/session',headers=h).status_code==401
    monkeypatch.setenv('DUBGUARD_DEMO_ACCESS_CODE','')
    assert client.post('/quick/sessions').status_code==503


def test_quick_failure_and_server_restart(quick,monkeypatch):
    client,s,_=quick;h={'Authorization':'Bearer '+s['token']}
    def unavailable(*args):raise RuntimeError('private error')
    monkeypatch.setattr('dubguard.quick.transcribe_artifact',unavailable)
    client.post('/quick/analyze?scenario_id=correct',headers=h,files={'file':('a.wav',wav_bytes(),'audio/wav')})
    report=client.get('/quick/session',headers=h).json()
    assert report['state']=='FAILED' and report['verification'] is None
    assert 'private error' not in json.dumps(report)
    with database() as db:db.execute("UPDATE sessions SET state='PROCESSING' WHERE id=?",(s['id'],))
    recover_interrupted()
    assert client.get('/quick/session',headers=h).json()['state']=='FAILED'


def test_quick_unknown_scenario_and_size(quick):
    client,s,_=quick;h={'Authorization':'Bearer '+s['token']}
    assert client.post('/quick/analyze?scenario_id=unknown',headers=h,files={'file':('a.wav',wav_bytes(),'audio/wav')}).status_code==422
    assert client.post('/quick/analyze?scenario_id=correct',headers=h,files={'file':('a.wav',b'x'*10_000_001,'audio/wav')}).status_code==413


def test_legacy_remote_endpoint_requires_auth(case_request,monkeypatch):
    monkeypatch.setenv('DUBGUARD_REVIEW_TOKENS_JSON',json.dumps({'human':'test-only-reviewer-token-long'}))
    assert TestClient(app).post('/verify?mode=hybrid',json=case_request('A01').model_dump()).status_code==401


# Reuse the Phase2C fixture to exercise the real workflow endpoints.
from test_phase2c import workflow,attest,run,accept,sign


def test_authenticated_dashboard_and_export(workflow):
    client,store,wid=workflow
    assert client.get('/review/workflows').json()[0]['workflow']['id']==wid
    assert client.get('/review/workflows/'+wid+'/export').json()['workflow']['id']==wid
    assert client.get('/review/policy-records').json()
    assert client.get('/review/workflows',headers={'Authorization':'Bearer invalid'}).status_code==401


def test_acoustic_resolution_bound_to_human_evidence(workflow):
    client,store,wid=workflow
    attest(client,store,wid)
    acoustic=TargetedRecheckResult(secondary_provider='stub',secondary_model='second',secondary_transcript=Transcript(source='asr'),checked_spans=[(0,.8)],assessment=AcousticAssessment(disagreements=[AcousticDisagreement(requirement_id='power-state',instruction_id='power',primary_segment_id='asr-1',primary_text='Switch the power on.',secondary_text='Switch the power off.')]))
    rid=store.add_record('acoustic',acoustic.model_dump(mode='json'))
    store.set_record(wid,'acoustic_record_id',rid,'IN_REVIEW','human')
    assert run(client,wid)['result']['decision']=='REVIEW_REQUIRED'
    wf=store.workflow(wid)
    payload={'expected_revision':wf['revision'],'evidence_record_id':wf['evidence_record_id'],'acoustic_record_id':rid,'requirement_ids':['power-state'],'listened_to_original':True,'reason':'Test listener verified actual source words in saved human evidence'}
    assert client.post('/review/workflows/'+wid+'/acoustic-resolution',json=payload).status_code==200
    result=run(client,wid)
    assert result['result']['decision']=='PASS_CANDIDATE'
    assert any(f['rule_id']=='ACOUSTIC.HUMAN_RESOLVED' for f in result['result']['findings'])
    attest(client,store,wid,'Switch the power on.')
    assert store.workflow(wid)['acoustic_resolution_record_id'] is None
    assert client.post('/review/workflows/'+wid+'/acoustic-resolution',json=payload).status_code==409
    assert run(client,wid)['result']['decision']=='CRITICAL_DEVIATION'
