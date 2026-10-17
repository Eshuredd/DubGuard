"""Local readiness only; no provider requests or model downloads."""
import importlib.util
import os
from pathlib import Path
from .audio import _ffmpeg, AudioError
from .providers import _load_project_env


def readiness():
    _load_project_env()
    dependencies = bool(importlib.util.find_spec('faster_whisper'))
    try:
        ffmpeg = Path(_ffmpeg()).is_file()
    except AudioError:
        ffmpeg = False
    configured = os.getenv('DUBGUARD_WHISPER_MODEL', 'tiny.en')
    model = Path(configured)
    # Resolve a pre-existing HF snapshot without contacting the hub.
    if not model.is_dir() and dependencies:
        try:
            from faster_whisper.utils import download_model
            model = Path(download_model(configured, local_files_only=True))
        except Exception:
            model = Path('/__dubguard_missing_model__')
    cached = all((model / name).is_file() for name in ('model.bin', 'config.json', 'tokenizer.json'))
    return {'ready': dependencies and ffmpeg and cached, 'audio_dependencies': dependencies,
            'ffmpeg': ffmpeg, 'whisper_cached': cached,
            'note': 'Local dependency/cache check only; no speech or remote inference was performed.'}
