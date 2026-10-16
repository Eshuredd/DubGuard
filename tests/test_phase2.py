import io
import json
import wave

import httpx
import pytest
from fastapi.testclient import TestClient

from dubguard.acoustic import compare_hypotheses, targeted_recheck
from dubguard.alignment import apply_confirmed_alignment, propose_alignment
from dubguard.amd_audio import MiMoAudioProbe
from dubguard.api import app
from dubguard.audio import (ASRHypothesis, AudioError, AudioStore,
                            _windows, transcribe_artifact)
from dubguard.engine import verify
from dubguard.audio_evaluation import RecordedManifest, _word_errors
from dubguard.phase2_evaluation import phase2_report
from dubguard.review import ReviewStore
from dubguard.schemas import (ApprovedScript, Instruction, PolarityConstraint,
                              ReviewPolicy, Transcript, TranscriptSegment)
from dubguard.semantic_validation import parse_semantic_json


def wav_bytes(seconds=1, amplitude=0):
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(int(amplitude).to_bytes(2, "little", signed=True) * int(seconds * 16000))
    return output.getvalue()


def test_quote_only_citations_get_source_offsets(case_request):
    request = case_request("A01")
    payload = {"verdict": "EQUIVALENT", "explanation": "Same wording", "findings": [{
        "requirement_id": "power-state", "kind": "POLARITY", "verdict": "EQUIVALENT",
        "instruction_id": "power",
        "approved_evidence": [{"instruction_id": "power", "quote": "power off"}],
        "observed_evidence": [{"instruction_id": "power", "segment_id": "s1", "quote": "power off"}],
        "explanation": "The protected phrase is present."}]}
    verdict, _, findings, issues = parse_semantic_json(json.dumps(payload), request)
    assert verdict == "EQUIVALENT" and not issues
    assert findings[0].approved[0].start_char == 11
    assert findings[0].observed[0].start_char == 11


def test_repeated_quote_is_rejected(case_request):
    request = case_request("A01")
    request.script.instructions[0].text = "off off"
    payload = {"verdict": "DEVIATION", "explanation": "x", "findings": [{
        "requirement_id": "power-state", "kind": "POLARITY", "verdict": "DEVIATION",
        "instruction_id": "power", "approved_evidence": [{"instruction_id": "power", "quote": "off"}],
        "observed_evidence": [{"instruction_id": "power", "segment_id": "s1", "quote": "off"}],
        "explanation": "x"}]}
    verdict, _, findings, issues = parse_semantic_json(json.dumps(payload), request)
    assert verdict == "UNRESOLVED" and not findings and issues


def test_contradictory_model_verdict_is_unresolved(case_request):
    request = case_request("A01")
    payload = {"verdict": "DEVIATION", "explanation": "Contradiction", "findings": [{
        "requirement_id": "power-state", "kind": "POLARITY", "verdict": "EQUIVALENT",
        "instruction_id": "power",
        "approved_evidence": [{"instruction_id": "power", "quote": "Switch the power off."}],
        "observed_evidence": [{"instruction_id": "power", "segment_id": "s1",
                               "quote": "Switch the power off."}],
        "explanation": "Same words."}]}
    verdict, _, _, issues = parse_semantic_json(json.dumps(payload), request)
    assert verdict == "UNRESOLVED" and issues


def test_audio_intake_chunk_coverage_and_silence(tmp_path, monkeypatch):
    monkeypatch.setenv("DUBGUARD_ASR_CHUNK_SECONDS", "1")
    monkeypatch.setenv("DUBGUARD_ASR_OVERLAP_SECONDS", "0")
    store = AudioStore(tmp_path / "artifacts")
    artifact = store.ingest(wav_bytes(2.25))

    class StubASR:
        name = "test-asr"
        model_id = "test-model"
        def transcribe(self, path):
            return []

    result = transcribe_artifact(store, artifact, StubASR())
    assert result.coverage.complete_processing
    assert result.coverage.processed_seconds == pytest.approx(2.25)
    assert len(result.coverage.windows) == 3
    assert result.coverage.gaps[0].classification == "digital_silence"
    assert result.transcript.completeness == "unknown"
    assert not result.transcript.segments
    assert store.path_for(artifact.sha256, "wav").read_bytes() == wav_bytes(2.25)


def test_asr_segments_have_real_audio_offsets(tmp_path, monkeypatch):
    monkeypatch.setenv("DUBGUARD_ASR_CHUNK_SECONDS", "1")
    monkeypatch.setenv("DUBGUARD_ASR_OVERLAP_SECONDS", "0")
    store = AudioStore(tmp_path / "artifacts")
    artifact = store.ingest(wav_bytes(2.0))

    class StubASR:
        name = "test-asr"
        model_id = "test-model"
        calls = 0
        def transcribe(self, path):
            self.calls += 1
            return [ASRHypothesis(text=f"chunk {self.calls}", start_seconds=0.1, end_seconds=0.4)]

    result = transcribe_artifact(store, artifact, StubASR())
    assert [(s.start_seconds, s.end_seconds) for s in result.transcript.segments] == [
        (0.1, 0.4), (1.1, 1.4)]
    assert all(s.instruction_id is None and s.uncertain for s in result.transcript.segments)


def test_audio_rejects_corrupt_upload(tmp_path):
    with pytest.raises(AudioError):
        AudioStore(tmp_path).ingest(b"not audio")


def test_windows_cover_without_core_gaps():
    windows = _windows(65, 30, 2)
    assert [(w.core_start_seconds, w.core_end_seconds) for w in windows] == [
        (0, 30), (30, 60), (60, 65)]
    assert windows[0].end_seconds == 32


def test_alignment_remains_provisional(case_request):
    request = case_request("A01")
    segment = request.transcript.segments[0]
    segment.instruction_id = None
    run = propose_alignment(request.script, request.transcript)
    assert run.proposals[0].status == "PROPOSED"
    assert segment.instruction_id is None
    confirmed = apply_confirmed_alignment(request.transcript, {segment.id: "power"}, request.script)
    assert confirmed.segments[0].instruction_id == "power"
    assert segment.instruction_id is None


def test_alignment_exposes_split_and_merged_sentences_without_assigning_ids():
    script = ApprovedScript(id="s", revision="1", instructions=[
        Instruction(id="a", text="Close the valve."),
        Instruction(id="b", text="Turn the power off.")])
    split = Transcript(segments=[TranscriptSegment(id="x", text="Close the"),
                                 TranscriptSegment(id="y", text="valve.")])
    merged = Transcript(segments=[TranscriptSegment(id="z", text="Close the valve. Turn the power off.")])
    split_run = propose_alignment(script, split)
    merged_run = propose_alignment(script, merged)
    assert any(p.match_type == "POSSIBLE_SPLIT_INSTRUCTION" for p in split_run.proposals)
    assert any(p.match_type == "POSSIBLE_MERGED_INSTRUCTIONS" for p in merged_run.proposals)
    assert all(s.instruction_id is None for s in split.segments + merged.segments)


def test_acoustic_protected_disagreement_requires_review(case_request):
    request = case_request("A01")
    primary = Transcript(source="asr", completeness="unknown", segments=[TranscriptSegment(
        id="p1", text="Switch the power off.", start_seconds=1, end_seconds=2)])
    secondary = Transcript(source="asr", completeness="unknown", segments=[TranscriptSegment(
        id="s1", text="Switch the power on.", start_seconds=1, end_seconds=2)])
    assessment = compare_hypotheses(request.policy, primary, secondary, {"p1": "power"})
    assert assessment.disagreements[0].requirement_id == "power-state"
    assert assessment.disagreements[0].status == "REVIEW_REQUIRED"


def test_acoustic_nested_phrase_does_not_false_alert():
    policy = ReviewPolicy(id="p", revision="1", approved_by="reviewer",
                          constraints=[PolarityConstraint(id="must-rule", kind="polarity",
                              instruction_id="step", approved_phrase="must not",
                              reversed_phrase="must")])
    def transcript(text, segment_id):
        return Transcript(source="asr", segments=[TranscriptSegment(
            id=segment_id, text=text, start_seconds=0, end_seconds=1)])
    same = compare_hypotheses(policy, transcript("You must not open it.", "p"),
                              transcript("You must not open it.", "s"), {"p": "step"})
    changed = compare_hypotheses(policy, transcript("You must not open it.", "p"),
                                 transcript("You must open it.", "s"), {"p": "step"})
    assert not same.disagreements
    assert len(changed.disagreements) == 1


def test_targeted_recheck_runs_even_when_primary_matches_approved(tmp_path, case_request):
    request = case_request("A01")
    store = AudioStore(tmp_path)
    artifact = store.ingest(wav_bytes(1))
    primary = Transcript(source="asr", segments=[TranscriptSegment(
        id="p", text="Switch the power off.", start_seconds=.1, end_seconds=.8)])
    class Independent:
        name, model_id = "independent", "different-model"
        def transcribe(self, path):
            return [ASRHypothesis(text="Switch the power on.", start_seconds=.1, end_seconds=.8)]
    result = targeted_recheck(store, artifact, request.policy, primary, {"p": "power"},
                              Independent(), primary_provider="primary", primary_model="first-model")
    assert result.checked_spans
    assert result.assessment.disagreements[0].status == "REVIEW_REQUIRED"


def test_mimo_probe_payload_has_documented_audio_shape(monkeypatch):
    monkeypatch.setenv("AMD_TOKEN_FACTORY_ENDPOINT", "https://unit.test/v1")
    monkeypatch.setenv("AMD_TOKEN_FACTORY_AUDIO_MODEL", "unit-audio-model")
    monkeypatch.setenv("AMD_TOKEN_FACTORY_API_KEY", "test-only-secret-marker")
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "probe-1", "model": "unit-audio-model",
                                         "choices": [{"message": {"content": "hello"}}]})
    result = MiMoAudioProbe(client=httpx.Client(transport=httpx.MockTransport(handler))).probe(wav_bytes(.2))
    assert result.status == "real_response" and not result.timestamps_available
    assert seen[0]["messages"][0]["content"][0]["type"] == "input_audio"
    assert seen[0]["model"] == "unit-audio-model"
    assert "test-only-secret-marker" not in result.model_dump_json()


def test_review_api_auth_and_approval_boundary(tmp_path, monkeypatch, case_request):
    monkeypatch.setenv("DUBGUARD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DUBGUARD_REVIEW_TOKENS_JSON", json.dumps({"reviewer-1": "a-very-long-test-only-secret-token"}))
    client = TestClient(app)
    headers = {"Authorization": "Bearer a-very-long-test-only-secret-token"}
    assert client.post("/review/policy-drafts", headers=headers,
                       json=case_request("A01").model_dump()["script"]).status_code == 422
    policy = case_request("A01").model_dump(exclude={"transcript"})
    assert client.post("/review/policy-drafts", json=policy).status_code == 401
    draft = client.post("/review/policy-drafts", json=policy, headers=headers).json()["record_id"]
    revised = client.post(f"/review/policy-drafts/{draft}/revise", json=policy,
                          headers=headers).json()["record_id"]
    assert revised != draft
    approved = client.post(f"/review/policy-drafts/{draft}/approve", headers=headers).json()["record_id"]
    assert ReviewStore(tmp_path / "review.sqlite3").record(approved, "approved_policy")["policy"]["approved_by"] == "reviewer-1"
    uploaded = client.post("/review/artifacts", headers=headers,
                           files={"file": ("sample.wav", wav_bytes(.5), "audio/wav")})
    assert uploaded.status_code == 200
    artifact_id = uploaded.json()["record_id"]
    workflow_id = client.post("/review/workflows", headers=headers,
                              json={"policy_record_id": approved,
                                    "audio_record_id": artifact_id}).json()["workflow_id"]
    blocked = client.post(f"/review/workflows/{workflow_id}/signoff", headers=headers,
                          json={"decision": "APPROVED", "reason": "test", "verification_record_id": "missing"})
    assert blocked.status_code == 409
    details = client.get(f"/review/workflows/{workflow_id}", headers=headers).json()
    assert details["workflow"]["state"] == "DRAFT"
    assert details["audit_events"]

    from dubguard.audio import transcribe_artifact as actual_transcribe
    class StubASR:
        name, model_id = "test-asr", "test-model"
        def transcribe(self, path):
            return [ASRHypothesis(text="Switch the power off.", start_seconds=0, end_seconds=.3)]
    monkeypatch.setattr("dubguard.review.transcribe_artifact",
                        lambda store, artifact: actual_transcribe(store, artifact, StubASR()))
    assert client.post(f"/review/workflows/{workflow_id}/transcribe", headers=headers).status_code == 200
    details = client.get(f"/review/workflows/{workflow_id}", headers=headers).json()
    assert details["workflow"]["state"] == "ANALYZED"
    assert details["transcription"]["transcript"]["segments"][0]["instruction_id"] is None
    proposal = client.post(f"/review/workflows/{workflow_id}/alignments/propose", headers=headers)
    assert proposal.status_code == 200
    assert proposal.json()["alignment"]["proposals"][0]["status"] == "PROPOSED"
    confirmed = client.post(f"/review/workflows/{workflow_id}/alignments/confirm", headers=headers,
                            json={"confirmations": {"asr-1": "power"}, "reason": "Listened to the audio"})
    assert confirmed.status_code == 200
    verified = client.post(f"/review/workflows/{workflow_id}/verify", headers=headers)
    assert verified.status_code == 200
    result = verified.json()["result"]
    assert result["decision"] == "REVIEW_REQUIRED"
    for index in range(len(result["findings"])):
        response = client.post(f"/review/workflows/{workflow_id}/findings/{index}/decision",
                               headers=headers,
                               json={"decision": "ACCEPTED_AS_CORRECT", "reason": "Reviewed source audio", "verification_record_id": verified.json()["record_id"]})
        assert response.status_code == 409
    signed = client.post(f"/review/workflows/{workflow_id}/signoff", headers=headers,
                         json={"decision": "APPROVED", "reason": "Reviewed original recording", "verification_record_id": verified.json()["record_id"]})
    assert signed.status_code == 409


def test_review_store_supersedes_prior_approval(tmp_path, case_request):
    store = ReviewStore(tmp_path / "review.sqlite3")
    policy = store.add_record("approved_policy", case_request("A01").model_dump(exclude={"transcript"}))
    artifact = store.add_record("audio_artifact", {"id": "a" * 64, "sha256": "a" * 64,
                                                   "format": "wav", "byte_size": 100,
                                                   "duration_seconds": 1, "sample_rate": 16000})
    first = store.create_workflow(policy, artifact, "reviewer-1")
    second = store.create_workflow(policy, artifact, "reviewer-1", supersedes=first)
    assert store.workflow(first)["state"] == "SUPERSEDED"
    assert store.workflow(second)["supersedes"] == first


def test_explicit_human_signoff_and_supersession(tmp_path, monkeypatch, case_request):
    monkeypatch.setenv("DUBGUARD_DATA_DIR", str(tmp_path))
    audio = AudioStore(tmp_path / "artifacts")
    artifact = audio.ingest(wav_bytes(1))

    class StubASR:
        name, model_id = "stub", "stub"
        def transcribe(self, path):
            return [ASRHypothesis(text="Switch the power off.", start_seconds=0, end_seconds=.5)]

    transcription = transcribe_artifact(audio, artifact, StubASR())
    store = ReviewStore(tmp_path / "review.sqlite3")
    policy_id = store.add_record("approved_policy", case_request("A01").model_dump(exclude={"transcript"}))
    audio_id = store.add_record("audio_artifact", artifact.model_dump())
    workflow = store.create_workflow(policy_id, audio_id, "reviewer-1")
    transcription_id = store.add_record("transcription", transcription.model_dump())
    store.set_record(workflow, "transcription_record_id", transcription_id, "ANALYZED", "reviewer-1")
    request = case_request("A01")
    request.transcript = transcription.transcript
    result = verify(request)
    verification_id = store.add_record("verification", result.model_dump())
    store.set_record(workflow, "verification_record_id", verification_id, "IN_REVIEW", "reviewer-1")
    with pytest.raises(ValueError):
        store.signoff(workflow, "APPROVED", "I heard the source audio", "reviewer-1")
    for index in range(len(result.findings)):
        with pytest.raises(ValueError, match="ordinary acceptance"):
            store.decide_finding(workflow, index, "ACCEPTED_AS_CORRECT", "Listened to audio", "reviewer-1")
    replacement = store.create_workflow(policy_id, audio_id, "reviewer-1", supersedes=workflow)
    assert store.workflow(workflow)["state"] == "SUPERSEDED"
    assert store.workflow(replacement)["state"] == "DRAFT"


def test_phase2_report_never_invents_audio_metrics():
    report = phase2_report()
    assert report["sets"]["semantic_comparison"]["count"] == 12
    assert report["sets"]["acoustic_confusion"]["metrics"] is None
    assert report["sets"]["human_review_workload"]["count"] == 0
    assert report["remote_paths"]["hybrid_amd"] == "not_run"


def test_recorded_audio_evaluation_requires_human_cases():
    with pytest.raises(ValueError):
        RecordedManifest.model_validate({"cases": []})
    assert _word_errors(["wait", "50", "minutes"], ["wait", "15", "minutes"]) == 1
