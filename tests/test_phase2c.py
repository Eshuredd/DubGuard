"""Protocol tests use silent PCM and stub ASR, not human speech ground truth."""
from concurrent.futures import ThreadPoolExecutor
import io
import json
import wave

import httpx
import pytest
from fastapi.testclient import TestClient

from dubguard.api import app
from dubguard.audio import ASRHypothesis, transcribe_artifact
from dubguard.engine import verify
from dubguard.review import ReviewStore


@pytest.fixture
def workflow(tmp_path, monkeypatch, case_request):
    monkeypatch.setenv("DUBGUARD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DUBGUARD_REVIEW_TOKENS_JSON", json.dumps({"human": "test-reviewer-secret-long-enough"}))
    def stub(store, artifact):
        class ASR:
            name, model_id = "stub", "stub"
            def transcribe(self, path):
                return [ASRHypothesis(text="Switch the power on.", start_seconds=0, end_seconds=.8)]
        return transcribe_artifact(store, artifact, ASR())
    monkeypatch.setattr("dubguard.review.transcribe_artifact", stub)
    client = TestClient(app, headers={"Authorization": "Bearer test-reviewer-secret-long-enough"})
    policy = case_request("A01").model_dump(exclude={"transcript"})
    draft = client.post("/review/policy-drafts", json=policy).json()["record_id"]
    policy_id = client.post(f"/review/policy-drafts/{draft}/approve").json()["record_id"]
    data = io.BytesIO()
    with wave.open(data, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 16000)
    audio_id = client.post("/review/artifacts", files={"file": ("protocol.wav", data.getvalue())}).json()["record_id"]
    wid = client.post("/review/workflows", json={"policy_record_id": policy_id, "audio_record_id": audio_id}).json()["workflow_id"]
    assert client.post(f"/review/workflows/{wid}/transcribe").status_code == 200
    return client, ReviewStore(tmp_path / "review.sqlite3"), wid


def attest(client, store, wid, text="Switch the power off.", **changes):
    payload = {"expected_revision": store.workflow(wid)["revision"], "listened_to_original": True,
        "reason": "Protocol test simulates a human listening; silent fixture is not recorded speech.",
        "transcript": {"source": "manual", "completeness": "complete", "segments": [
            {"id": "human-1", "text": text, "instruction_id": "power", "start_seconds": 0, "end_seconds": .8}]}}
    payload.update(changes)
    return client.post(f"/review/workflows/{wid}/transcript-evidence", json=payload)


def run(client, wid):
    response = client.post(f"/review/workflows/{wid}/verify")
    assert response.status_code == 200, response.text
    return response.json()


def accept(client, wid, result):
    for index in range(len(result["result"]["findings"])):
        response = client.post(f"/review/workflows/{wid}/findings/{index}/decision", json={
            "verification_record_id": result["record_id"], "decision": "ACCEPTED_AS_CORRECT", "reason": "Reviewed"})
        assert response.status_code == 200, response.text


def sign(client, wid, rid):
    return client.post(f"/review/workflows/{wid}/signoff", json={
        "verification_record_id": rid, "decision": "APPROVED", "reason": "Explicit human signoff"})


def test_asr_suspicion_then_human_confirmed_violation(workflow):
    client, store, wid = workflow
    initial = run(client, wid)
    assert initial["result"]["decision"] == "REVIEW_REQUIRED"
    suspects = [f for f in initial["result"]["findings"] if f["rule_id"].startswith("ASR.SUSPECTED.")]
    assert suspects[0]["constraint_id"] == "power-state"
    assert suspects[0]["observed"][0]["text"] == "Switch the power on."
    assert suspects[0]["observed"][0]["end_seconds"] == .8
    assert not any(f["status"] == "VIOLATION" for f in initial["result"]["findings"])
    assert client.post(f"/review/workflows/{wid}/alignments/confirm", json={
        "confirmations": {"asr-1": "power"}, "reason": "Mapping only"}).status_code == 200
    assert run(client, wid)["result"]["decision"] == "REVIEW_REQUIRED"
    assert attest(client, store, wid, "Switch the power on.").status_code == 200
    final = run(client, wid)
    assert final["result"]["decision"] == "CRITICAL_DEVIATION"
    assert sign(client, wid, final["record_id"]).status_code == 409
    assert client.post(f"/review/workflows/{wid}/findings/0/decision", json={
        "verification_record_id": final["record_id"], "decision": "ACCEPTED_AS_CORRECT", "reason": "Override"}).status_code == 409


def test_corrections_stale_decisions_and_preserved_history(workflow):
    client, store, wid = workflow
    first = attest(client, store, wid).json()["record_id"]
    prior = run(client, wid)
    accept(client, wid, prior)
    old_revision = store.workflow(wid)["revision"]
    second = attest(client, store, wid).json()["record_id"]
    assert first != second
    assert store.record(second, "verified_evidence")["previous_evidence_record_id"] == first
    assert store.record(first, "verified_evidence")["reviewer_id"] == "human"
    raw = store.record(store.workflow(wid)["transcription_record_id"], "transcription")
    assert raw["transcript"]["segments"][0]["text"] == "Switch the power on."
    assert attest(client, store, wid, expected_revision=old_revision).status_code == 409
    assert sign(client, wid, prior["record_id"]).status_code == 409
    current = run(client, wid)
    assert sign(client, wid, prior["record_id"]).status_code == 409
    assert sign(client, wid, current["record_id"]).status_code == 409  # old accepts cannot carry
    accept(client, wid, current)
    assert sign(client, wid, current["record_id"]).status_code == 200
    assert sign(client, wid, current["record_id"]).status_code == 409
    approval = store.details(wid)["approvals"][0]
    assert approval["evidence_record_id"] == second
    assert approval["verification_record_id"] == current["record_id"]
    assert json.loads(approval["input_snapshot"])["evidence_record_id"] == second
    assert attest(client, store, wid).status_code == 409
    wf = store.workflow(wid)
    changed = store.record(wf["policy_record_id"], "approved_policy")
    changed["policy"]["revision"] = "2"
    policy2 = store.add_record("approved_policy", changed)
    successor = store.create_workflow(policy2, wf["audio_record_id"], "human", supersedes=wid)
    assert store.details(wid)["approvals"][0]["status"] == "SUPERSEDED"
    assert store.workflow(successor)["verification_record_id"] is None


@pytest.mark.parametrize("field,kind,payload", [
    ("alignment_record_id", "alignment", {}),
    ("confirmed_alignment_record_id", "confirmed_alignment", {}),
    ("acoustic_record_id", "acoustic", {}),
])
def test_input_changes_invalidate_run(workflow, field, kind, payload):
    client, store, wid = workflow
    attest(client, store, wid)
    current = run(client, wid)
    accept(client, wid, current)
    record = store.add_record(kind, payload)
    store.set_record(wid, field, record, "IN_REVIEW", "human")
    assert store.workflow(wid)["verification_record_id"] is None
    assert sign(client, wid, current["record_id"]).status_code == 409


def test_retranscription_invalidates_human_evidence(workflow):
    client, store, wid = workflow
    attest(client, store, wid)
    current = run(client, wid)
    raw = store.record(store.workflow(wid)["transcription_record_id"], "transcription")
    record = store.add_record("transcription", raw)
    store.set_record(wid, "transcription_record_id", record, "ANALYZED", "human")
    assert store.workflow(wid)["evidence_record_id"] is None
    assert sign(client, wid, current["record_id"]).status_code == 409


def test_failed_processing_and_stale_job_cannot_restore_readiness(workflow):
    client, store, wid = workflow
    attest(client, store, wid)
    current = run(client, wid)
    accept(client, wid, current)
    revision = store.workflow(wid)["revision"]
    store.mark_state(wid, {"IN_REVIEW"}, "VERIFYING", "human")
    store.mark_state(wid, {"VERIFYING"}, "VERIFICATION_FAILED", "human")
    assert sign(client, wid, current["record_id"]).status_code == 409
    late = store.add_record("verification", current["result"])
    with pytest.raises(ValueError, match="stale"):
        store.set_record(wid, "verification_record_id", late, "IN_REVIEW", "human", expected_revision=revision)


def test_concurrent_signoff_only_one_wins(workflow):
    client, store, wid = workflow
    attest(client, store, wid)
    result = run(client, wid)
    accept(client, wid, result)
    def attempt(_):
        try:
            store.signoff(wid, "APPROVED", "human reviewed", "human", expected_run=result["record_id"])
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [False, True]
    assert len(store.details(wid)["approvals"]) == 1


def test_zero_findings_explicit_signoff_still_needs_evidence(workflow):
    client, store, wid = workflow
    result = run(client, wid)["result"]
    result.update(decision="PASS_CANDIDATE", findings=[])
    record = store.add_record("verification", result)
    store.set_record(wid, "verification_record_id", record, "IN_REVIEW", "human")
    assert sign(client, wid, record).status_code == 409
    attest(client, store, wid)
    record = store.add_record("verification", result)
    store.set_record(wid, "verification_record_id", record, "IN_REVIEW", "human")
    assert sign(client, wid, record).status_code == 200


def test_auth_and_invalid_timing(workflow):
    client, store, wid = workflow
    assert client.post(f"/review/workflows/{wid}/transcript-evidence", headers={"Authorization": "Bearer invalid"}, json={}).status_code == 401
    assert attest(client, store, wid, listened_to_original=False).status_code == 422
    transcript = {"source": "manual", "completeness": "complete", "segments": [
        {"id": "s", "text": "word", "start_seconds": 0, "end_seconds": 99}]}
    assert attest(client, store, wid, transcript=transcript).status_code == 422


def test_asr_confidence_and_agreement_cannot_clear(case_request):
    request = case_request("A01")
    request.transcript.source = "asr"
    for segment in request.transcript.segments:
        segment.confidence = 1
    assert verify(request).decision == "REVIEW_REQUIRED"


@pytest.mark.parametrize("exception,diagnostic", [(httpx.ReadTimeout, "read_timeout"), (httpx.ConnectTimeout, "connect_timeout"), (httpx.ConnectError, "transport_error")])
def test_amd_timeout_diagnostics_and_token_bound(monkeypatch, case_request, exception, diagnostic):
    from dubguard.providers import AMDTokenFactoryProvider
    monkeypatch.setenv("AMD_TOKEN_FACTORY_ENDPOINT", "https://unit.test/v1")
    monkeypatch.setenv("AMD_TOKEN_FACTORY_MODEL", "test-model")
    monkeypatch.setenv("AMD_TOKEN_FACTORY_API_KEY", "test-key")
    monkeypatch.setenv("AMD_TOKEN_FACTORY_MAX_RETRIES", "0")
    monkeypatch.setenv("AMD_TOKEN_FACTORY_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("AMD_TOKEN_FACTORY_CONNECT_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("AMD_TOKEN_FACTORY_MAX_OUTPUT_TOKENS", "512")
    def handler(request):
        assert json.loads(request.content)["max_tokens"] == 512
        assert request.extensions["timeout"]["read"] == 60
        assert request.extensions["timeout"]["connect"] == 3
        raise exception("private transport detail must not leak")
    result = AMDTokenFactoryProvider(client=httpx.Client(transport=httpx.MockTransport(handler))).verify(case_request("A01"))
    assert diagnostic in result.explanation and result.attempts == 1
    assert "private transport" not in result.model_dump_json()


def test_failed_transcription_job_is_not_approvable(workflow, monkeypatch):
    client, store, wid = workflow
    wf = store.workflow(wid)
    replacement = store.create_workflow(wf["policy_record_id"], wf["audio_record_id"], "human")
    def fail(*args):
        raise RuntimeError("internal failure")
    monkeypatch.setattr("dubguard.review.transcribe_artifact", fail)
    assert client.post(f"/review/workflows/{replacement}/transcribe").status_code == 200
    assert store.workflow(replacement)["state"] == "TRANSCRIPTION_FAILED"
    assert sign(client, replacement, "none").status_code == 409


def test_changed_audio_blocks_signoff(workflow):
    from dubguard.audio import AudioStore
    client, store, wid = workflow
    attest(client, store, wid)
    result = run(client, wid)
    accept(client, wid, result)
    artifact = store.record(store.workflow(wid)["audio_record_id"], "audio_artifact")
    AudioStore(store.path.parent / "artifacts").path_for(artifact["sha256"], artifact["format"]).write_bytes(b"changed")
    assert sign(client, wid, result["record_id"]).status_code == 409
    assert not store.details(wid)["approvals"]


def test_unclear_human_evidence_does_not_pass(workflow):
    client, store, wid = workflow
    transcript = {"source": "manual", "completeness": "unknown", "segments": [
        {"id": "human-1", "text": "Switch the power [unclear].", "instruction_id": "power", "uncertain": True}]}
    assert attest(client, store, wid, transcript=transcript).status_code == 200
    result = run(client, wid)
    assert result["result"]["decision"] == "REVIEW_REQUIRED"
    assert sign(client, wid, result["record_id"]).status_code == 409


def test_stale_verification_computation_is_rejected(workflow, monkeypatch):
    import dubguard.review as review
    client, store, wid = workflow
    attest(client, store, wid)
    original = review.verify
    def mutate(request, **kwargs):
        result = original(request, **kwargs)
        rec = store.add_record("alignment", {})
        store.set_record(wid, "alignment_record_id", rec, "IN_REVIEW", "human")
        return result
    monkeypatch.setattr(review, "verify", mutate)
    assert client.post(f"/review/workflows/{wid}/verify").status_code == 409
    assert store.workflow(wid)["verification_record_id"] is None


def test_smoke_preparation_never_calls_remote(monkeypatch, capsys):
    from dubguard.smoke import main
    def fail(*args):
        pytest.fail("Preparation must not access remote inference")
    monkeypatch.setattr("dubguard.smoke.AMDTokenFactoryProvider", fail)
    monkeypatch.setattr("dubguard.smoke.MiMoAudioProbe", fail)
    assert main(["semantic", "examples/critical.json"]) == 0
    assert main(["audio", "/missing/not-yet-recorded.wav"]) == 0
    assert capsys.readouterr().out.count('"http_calls": 0') == 2


def test_recording_template_refuses_unadjudicated_data():
    from pathlib import Path
    from dubguard.audio_evaluation import RecordedManifest
    template = json.loads(Path("examples/phase2c-recordings.template.json").read_text())
    assert len(template["cases"]) == 6
    with pytest.raises(ValueError):
        RecordedManifest.model_validate(template)


def test_legacy_approval_history_is_preserved_but_not_current(tmp_path):
    import sqlite3
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE approvals (id TEXT PRIMARY KEY, workflow_id TEXT, decision TEXT, reviewer_id TEXT, reason TEXT, script_id TEXT, script_revision TEXT, policy_id TEXT, policy_revision TEXT, audio_sha256 TEXT, status TEXT, created_at TEXT)")
        db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
            "old", "workflow", "APPROVED", "human", "legacy", "s", "1", "p", "1", "a" * 64, "CURRENT", "old-time"))
    ReviewStore(path)
    ReviewStore(path)  # migrations are idempotent
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT status FROM approvals WHERE id='old'").fetchone()[0] == "LEGACY_UNVERIFIED"
        assert db.execute("SELECT count(*) FROM approvals").fetchone()[0] == 1


def test_recorded_report_keeps_raw_and_corrected_evidence_separate(tmp_path, monkeypatch, case_request):
    from hashlib import sha256
    from dubguard.audio_evaluation import evaluate_recorded_audio
    data = io.BytesIO()
    with wave.open(data, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 16000)
    audio = tmp_path / "protocol.wav"
    audio.write_bytes(data.getvalue())
    class ASR:
        name, model_id = "stub", "stub"
        def __init__(self, *args, **kwargs):
            pass
        def transcribe(self, path):
            return [ASRHypothesis(text="Switch the power on.", start_seconds=0, end_seconds=.8)]
    monkeypatch.setattr("dubguard.audio_evaluation.FasterWhisperProvider", ASR)
    request = case_request("A01")
    corrected = request.transcript.model_dump()
    corrected["segments"][0]["text"] = "Switch the power on."
    corrected["segments"][0]["instruction_id"] = "power"
    manifest = {"cases": [{"id": "stub-protocol", "category": "polarity", "split": "development",
        "audio_path": str(audio), "audio_sha256": sha256(data.getvalue()).hexdigest(),
        "human_verified_by": "test-fixture-only", "adjudication_note": "Not a real speech result",
        "spoken_ground_truth": [{"text": "Switch the power on.", "instruction_id": "power"}],
        "label": "CRITICAL", "policy": request.model_dump(exclude={"transcript"}),
        "human_corrected_transcript": corrected}]}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    result = evaluate_recorded_audio(manifest_path, model_path="stub")["cases"][0]
    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["final_verification_decision"] == "CRITICAL_DEVIATION"
    assert result["suspected_violations"] and result["timestamp_validity"]
    assert result["release_approval"] == "not_performed_by_evaluation"


def test_pending_acoustic_job_cannot_be_bypassed_by_correction(workflow):
    client, store, wid = workflow
    attest(client, store, wid)
    result = run(client, wid)
    accept(client, wid, result)
    store.mark_state(wid, {"IN_REVIEW"}, "ACOUSTIC_RECHECKING", "human")
    assert attest(client, store, wid).status_code == 409
    assert client.post(f"/review/workflows/{wid}/verify").status_code == 409
    assert sign(client, wid, result["record_id"]).status_code == 409


def test_zero_findings_cannot_hide_deterministic_violation(workflow):
    client, store, wid = workflow
    attest(client, store, wid, "Switch the power on.")
    result = run(client, wid)["result"]
    result.update(decision="PASS_CANDIDATE", findings=[])
    record = store.add_record("verification", result)
    store.set_record(wid, "verification_record_id", record, "IN_REVIEW", "human")
    assert sign(client, wid, record).status_code == 409
