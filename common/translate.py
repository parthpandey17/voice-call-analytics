"""Translation to English.

Prefers Sarvam (best for Indian languages). Falls back to the English text that
Whisper's `translate` task already produced, which the pipeline passes in.
"""
from __future__ import annotations

import requests

from config.settings import settings

# Sarvam expects BCP-47-ish codes like "hi-IN". Map Whisper's short codes.
_LANG_MAP = {
    "hi": "hi-IN", "ta": "ta-IN", "te": "te-IN", "kn": "kn-IN", "ml": "ml-IN",
    "mr": "mr-IN", "bn": "bn-IN", "gu": "gu-IN", "pa": "pa-IN", "or": "od-IN",
    "en": "en-IN",
}


def translate_to_english(text: str, lang: str, whisper_fallback: str = "") -> str:
    """Translate `text` (in language `lang`) to English.

    If the language is already English, returns it unchanged.
    If no Sarvam key is set, returns `whisper_fallback` (Whisper's own translation).
    """
    if not text:
        return ""
    if lang == "en":
        return text
    if not settings.sarvam_api_key:
        return whisper_fallback or text

    src = _LANG_MAP.get(lang, "hi-IN")
    try:
        resp = requests.post(
            "https://api.sarvam.ai/translate",
            headers={"api-subscription-key": settings.sarvam_api_key},
            json={
                "input": text[:1000],  # Sarvam has a per-call char limit; chunk for longer
                "source_language_code": src,
                "target_language_code": "en-IN",
                "mode": "formal",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("translated_text", whisper_fallback or text)
    except Exception as exc:  # noqa: BLE001 - keep the pipeline resilient
        print(f"[translate] Sarvam failed ({exc}); using Whisper fallback.")
        return whisper_fallback or text
