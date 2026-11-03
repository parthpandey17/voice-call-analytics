"""LOCAL end-to-end pipeline (no cloud).

For each audio file in AUDIO_DIR:
  transcribe -> detect language -> translate to English -> LLM extraction
  -> write one row to the local SQLite warehouse.

Run:  python -m local.pipeline
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import os

from config.settings import settings
from common import stt, translate, llm
from local import db


def _call_id(path: str) -> str:
    base = os.path.splitext(os.path.basename(path))[0]
    short = hashlib.md5(path.encode()).hexdigest()[:6]
    return f"{base}-{short}"


def process_file(path: str) -> dict:
    print(f"\n=== {os.path.basename(path)} ===")

    # 1. transcribe (original language)
    stt_out = stt.transcribe(path)
    lang = stt_out["language"]
    print(f"[1/4] transcribed · language={lang}")

    # 2. English fallback from Whisper (only computed if we'll need it)
    whisper_en = ""
    if lang != "en" and not settings.sarvam_api_key:
        whisper_en = stt.transcribe_to_english(path)

    # 3. translate to English (Sarvam, or Whisper fallback)
    transcript_en = translate.translate_to_english(
        stt_out["transcript_src"], lang, whisper_fallback=whisper_en
    )
    print(f"[2/4] translated to English ({len(transcript_en)} chars)")

    # 4. LLM structured extraction
    analysis = llm.extract(transcript_en)
    print(f"[3/4] extracted · sentiment={analysis.get('sentiment')} "
          f"category={analysis.get('issue_category')}")

    row = {
        "call_id": _call_id(path),
        "call_date": dt.date.today().isoformat(),
        "language": lang,
        "transcript_src": stt_out["transcript_src"],
        "transcript_en": transcript_en,
        "sentiment": analysis.get("sentiment"),
        "issue_category": analysis.get("issue_category"),
        "product_mentioned": analysis.get("product_mentioned"),
        "resolved": analysis.get("resolved"),
        "upsell_opportunity": analysis.get("upsell_opportunity"),
        "summary": analysis.get("summary"),
    }
    db.upsert_call(row)
    print("[4/4] written to warehouse")
    return row


def main() -> None:
    db.init_db()
    patterns = ("*.mp3", "*.wav", "*.m4a", "*.flac")
    files: list[str] = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(settings.audio_dir, p)))

    if not files:
        print(f"No audio found in '{settings.audio_dir}'. Drop some .mp3/.wav files there.")
        return

    print(f"Found {len(files)} file(s). LLM provider: {settings.llm_provider}")
    for f in sorted(files):
        try:
            process_file(f)
        except Exception as exc:  # noqa: BLE001
            print(f"!! failed on {f}: {exc}")

    print(f"\nDone. Rows are in '{settings.local_db_path}'. "
          f"Next: python -m rag.vector_store --build")


if __name__ == "__main__":
    main()
