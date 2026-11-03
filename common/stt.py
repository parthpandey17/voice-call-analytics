"""Speech-to-text with Whisper (local).

Returns the transcript in the ORIGINAL language plus the detected language code.
The Whisper model is loaded once and cached per process.
"""
from __future__ import annotations

import functools

from config.settings import settings


@functools.lru_cache(maxsize=1)
def _model():
    import whisper  # imported lazily so the dashboard/RAG don't need it
    print(f"[stt] loading Whisper model '{settings.whisper_model}' ...")
    return whisper.load_model(settings.whisper_model)


def transcribe(audio_path: str) -> dict:
    """Transcribe one audio file.

    Returns {"transcript_src": str, "language": str}.
    """
    result = _model().transcribe(audio_path)  # auto-detects language
    return {
        "transcript_src": result.get("text", "").strip(),
        "language": result.get("language", "unknown"),
    }


def transcribe_to_english(audio_path: str) -> str:
    """Whisper's built-in translate task (fallback when no Sarvam key)."""
    result = _model().transcribe(audio_path, task="translate")
    return result.get("text", "").strip()
