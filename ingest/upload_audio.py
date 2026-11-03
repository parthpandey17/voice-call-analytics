"""Upload local audio files to a GCS bucket (cloud path, step 3).

Usage:  python ingest/upload_audio.py
Requires: google-cloud-storage, GOOGLE_APPLICATION_CREDENTIALS, GCS_AUDIO_BUCKET.
"""
from __future__ import annotations

import glob
import os

from config.settings import settings


def main() -> None:
    if not settings.gcs_audio_bucket:
        raise SystemExit("Set GCS_AUDIO_BUCKET in .env first.")

    from google.cloud import storage  # imported lazily

    client = storage.Client(project=settings.gcp_project or None)
    bucket = client.bucket(settings.gcs_audio_bucket)

    files: list[str] = []
    for pat in ("*.mp3", "*.wav", "*.m4a", "*.flac"):
        files.extend(glob.glob(os.path.join(settings.audio_dir, pat)))

    if not files:
        print(f"No audio in {settings.audio_dir}")
        return

    for path in files:
        blob_name = f"calls/{os.path.basename(path)}"
        bucket.blob(blob_name).upload_from_filename(path)
        print(f"uploaded gs://{settings.gcs_audio_bucket}/{blob_name}")

    print(f"Done. {len(files)} file(s) uploaded.")


if __name__ == "__main__":
    main()
