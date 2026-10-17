"""Local tooling checks with generated silence/report fixtures, never speech labels."""
import importlib.util
from pathlib import Path
import pytest
from test_phase3 import wav_bytes
from dubguard.audio import AudioError


def tool(name):
    path = Path(__file__).resolve().parents[1] / 'scripts' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recording_format_check_decodes_without_asr(tmp_path):
    source = tmp_path / 'fixture.wav'
    source.write_bytes(wav_bytes())
    result = tool('inspect_audio').inspect(source)
    assert result['artifact']['format'] == 'wav'
    assert result['artifact']['duration_seconds'] == .4
    assert result['decode_validated'] and not result['asr_performed'] and result['remote_calls'] == 0
    source.write_bytes(b'not actual wav')
    with pytest.raises(AudioError):
        tool('inspect_audio').inspect(source)


def test_report_keeps_unmeasured_acoustic_and_corrected_results_separate():
    report = {'primary_provider': 'test-only-stub', 'primary_model': 'fixture', 'secondary_model': None,
        'splits': {'held_out': {'count': 0, 'primary_asr_word_error_rate': None}},
        'cases': [{'id': 'synthetic|fixture', 'decision': 'REVIEW_REQUIRED', 'secondary': None,
                   'human_evidence_verification': None, 'final_verification_decision': 'REVIEW_REQUIRED'}]}
    text = tool('render_audio_report').render(report)
    for title in ('ASR word errors', 'Protected-token errors', 'Acoustic disagreement', 'End-to-end verification'):
        assert title in text
    assert '| held_out | 0 | Not measured |' in text
    assert 'synthetic\\|fixture' in text
    assert 'Not measured' in text and 'release sign-off' in text
