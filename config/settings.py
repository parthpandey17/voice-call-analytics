"""Central configuration. Reads from .env (via python-dotenv).

Import `settings` anywhere:  from config.settings import settings
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


@dataclass
class Settings:
    # backend
    backend: str = field(default_factory=lambda: _get("BACKEND", "local"))

    # llm
    llm_provider: str = field(default_factory=lambda: _get("LLM_PROVIDER", "groq"))
    google_api_key: str = field(default_factory=lambda: _get("GOOGLE_API_KEY"))
    groq_api_key: str = field(default_factory=lambda: _get("GROQ_API_KEY"))
    gemini_extract_model: str = field(default_factory=lambda: _get("GEMINI_EXTRACT_MODEL", "gemini-1.5-flash"))
    gemini_answer_model: str = field(default_factory=lambda: _get("GEMINI_ANSWER_MODEL", "gemini-1.5-pro"))
    groq_model: str = field(default_factory=lambda: _get("GROQ_MODEL", "llama-3.3-70b-versatile"))

    # stt / translate
    whisper_model: str = field(default_factory=lambda: _get("WHISPER_MODEL", "small"))
    sarvam_api_key: str = field(default_factory=lambda: _get("SARVAM_API_KEY"))

    # embeddings
    embedding_model: str = field(default_factory=lambda: _get("EMBEDDING_MODEL", "BAAI/bge-m3"))

    # local paths
    local_db_path: str = field(default_factory=lambda: _get("LOCAL_DB_PATH", "voc_local.db"))
    chroma_dir: str = field(default_factory=lambda: _get("CHROMA_DIR", "./chroma"))
    audio_dir: str = field(default_factory=lambda: _get("AUDIO_DIR", "sample_data/calls"))

    # cloud
    gcp_project: str = field(default_factory=lambda: _get("GCP_PROJECT"))
    bq_dataset: str = field(default_factory=lambda: _get("BQ_DATASET", "voc"))
    gcs_audio_bucket: str = field(default_factory=lambda: _get("GCS_AUDIO_BUCKET"))
    gcs_temp_bucket: str = field(default_factory=lambda: _get("GCS_TEMP_BUCKET"))

    @property
    def is_cloud(self) -> bool:
        return self.backend.lower() == "bigquery"

    @property
    def bq_table(self) -> str:
        return f"{self.gcp_project}.{self.bq_dataset}.calls_enriched"


settings = Settings()
