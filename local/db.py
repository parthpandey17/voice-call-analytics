"""Tiny SQLite helper for the local backend.

Mirrors the BigQuery `calls_enriched` table so the RAG/dashboard code can treat
local and cloud the same way.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from config.settings import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls_enriched (
    call_id            TEXT PRIMARY KEY,
    call_date          TEXT,
    language           TEXT,
    transcript_src     TEXT,
    transcript_en      TEXT,
    sentiment          TEXT,
    issue_category     TEXT,
    product_mentioned  TEXT,
    resolved           TEXT,
    upsell_opportunity TEXT,
    summary            TEXT
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.local_db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def upsert_call(row: dict) -> None:
    cols = [
        "call_id", "call_date", "language", "transcript_src", "transcript_en",
        "sentiment", "issue_category", "product_mentioned", "resolved",
        "upsell_opportunity", "summary",
    ]
    placeholders = ", ".join(["?"] * len(cols))
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "call_id")
    sql = (
        f"INSERT INTO calls_enriched ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(call_id) DO UPDATE SET {updates}"
    )
    with connect() as conn:
        conn.execute(sql, [row.get(c) for c in cols])


def all_transcripts() -> list[dict]:
    with connect() as conn:
        cur = conn.execute(
            "SELECT call_id, call_date, product_mentioned, transcript_en "
            "FROM calls_enriched WHERE transcript_en IS NOT NULL AND transcript_en != ''"
        )
        return [dict(r) for r in cur.fetchall()]
