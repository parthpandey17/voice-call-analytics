"""Central configuration. Reads from .env (via python-dotenv).

Import `settings` anywhere:  from config.settings import settings
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(ROOT, ".env"))


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _path(key: str, default: str) -> str:
    value = _get(key, default)
    return value if os.path.isabs(value) else os.path.normpath(os.path.join(ROOT, value))


@dataclass
class Settings:
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

    # paths
    local_db_path: str = field(default_factory=lambda: _path("LOCAL_DB_PATH", "voc_local.db"))
    chroma_dir: str = field(default_factory=lambda: _path("CHROMA_DIR", "./chroma"))
    audio_dir: str = field(default_factory=lambda: _path("AUDIO_DIR", "sample_data/calls"))

    seed_csv: str = field(default_factory=lambda: _path("SEED_CSV", "sample_data/seed_calls.csv"))


settings = Settings()
