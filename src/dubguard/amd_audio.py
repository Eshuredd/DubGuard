"""Opt-in AMD MiMo audio-input probe; no ASR quality or timestamps assumed."""

import base64
from dataclasses import dataclass, field
from io import BytesIO
import os
import time
import wave

import httpx
from pydantic import Field

from .providers import _load_project_env, _bounded_int, _bounded_float
from .schemas import Model


class AudioProbeResult(Model):
    status: str
    provider: str = "amd-token-factory"
    model: str | None = None
    call_id: str | None = None
    text: str | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    attempts: int = Field(default=0, ge=0)
    timestamps_available: bool = False
    note: str = "Audio understanding output is not validated ASR ground truth."


@dataclass
class MiMoAudioProbe:
    client: httpx.Client | None = field(default=None, repr=False)

    def probe(self, wav_bytes: bytes) -> AudioProbeResult:
        """One small explicit probe; never called by normal verification."""
        _load_project_env()
        endpoint = os.getenv("AMD_TOKEN_FACTORY_ENDPOINT", "")
        model = os.getenv("AMD_TOKEN_FACTORY_AUDIO_MODEL", "")
        key = os.getenv("AMD_TOKEN_FACTORY_API_KEY", "")
        if not endpoint or not model or not key:
            return AudioProbeResult(status="unavailable", note="Audio model configuration is incomplete.")
        try:
            url = httpx.URL(endpoint)
            if url.scheme != "https" or not url.host or url.userinfo or url.query or url.fragment:
                raise ValueError("invalid URL")
            target = str(url).rstrip("/")
            if not target.endswith("/chat/completions"):
                target += "/chat/completions"
        except (ValueError, httpx.InvalidURL):
            return AudioProbeResult(status="unavailable", note="Audio endpoint must be HTTPS.")
        if not wav_bytes.startswith(b"RIFF") or wav_bytes[8:12] != b"WAVE" or len(wav_bytes) > 5_000_000:
            return AudioProbeResult(status="invalid_audio", note="Only a small WAV probe is accepted.")
        try:
            with wave.open(BytesIO(wav_bytes), "rb") as clip:
                if not 0 < clip.getnframes() / clip.getframerate() <= 30:
                    raise ValueError("duration")
        except (wave.Error, EOFError, ValueError, ZeroDivisionError):
            return AudioProbeResult(status="invalid_audio", note="WAV probe must decode and be at most 30 seconds.")
        payload = {"model": model, "stream": False, "max_tokens": 256,
                   "reasoning_effort": "none", "messages": [{"role": "user", "content": [
            {"type": "input_audio", "input_audio": {"data": base64.b64encode(wav_bytes).decode("ascii"),
                                                     "format": "wav"}},
            {"type": "text", "text": "Transcribe the English speech verbatim. Return only the words heard. If unintelligible, say UNINTELLIGIBLE. Do not infer from a script."},
        ]}]}
        retries = _bounded_int("AMD_TOKEN_FACTORY_AUDIO_MAX_RETRIES", 0, 0, 1)
        timeout = _bounded_float("AMD_TOKEN_FACTORY_AUDIO_TIMEOUT_SECONDS", 45.0, 2.0, 120.0)
        timeout_config = httpx.Timeout(timeout, connect=5.0)
        began = time.perf_counter()
        own_client = self.client is None
        client = self.client or httpx.Client(timeout=timeout_config)
        try:
            for attempt in range(retries + 1):
                try:
                    response = client.post(target, headers={"Authorization": f"Bearer {key}"},
                                           json=payload, timeout=timeout_config)
                except (httpx.TimeoutException, httpx.TransportError):
                    if attempt < retries:
                        time.sleep(0.5)
                        continue
                    break
                if response.status_code in {429, 500, 502, 503, 504} and attempt < retries:
                    time.sleep(0.5)
                    continue
                if response.status_code != 200 or len(response.content) > 100_000:
                    break
                try:
                    body = response.json()
                    call_id = body["id"]
                    text = body["choices"][0]["message"]["content"]
                    if not isinstance(call_id, str) or not call_id or not isinstance(text, str) or not text.strip() or body["choices"][0].get("finish_reason") == "length":
                        break
                    return AudioProbeResult(status="real_response", model=body.get("model") or model,
                                            call_id=call_id, text=text.strip(),
                                            latency_ms=(time.perf_counter() - began) * 1000,
                                            attempts=attempt + 1)
                except (KeyError, IndexError, TypeError, ValueError):
                    break
            return AudioProbeResult(status="unavailable", model=model,
                                    latency_ms=(time.perf_counter() - began) * 1000,
                                    attempts=attempt + 1)
        finally:
            if own_client:
                client.close()
