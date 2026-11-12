"""Tiny SQLite helper: the single data store for the pipeline, RAG and dashboard."""
from __future__ import annotations

import csv
import os
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from typing import Iterator

from config.settings import settings

COLUMNS = [
    "call_id", "call_date", "language", "transcript_src", "transcript_en",
    "sentiment", "issue_category", "product_mentioned", "resolved",
    "upsell_opportunity", "summary",
]

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
    cols = COLUMNS
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


def _row_count() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM calls_enriched").fetchone()[0]


def _prepare() -> None:
    parent = os.path.dirname(settings.local_db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    init_db()


def seed_from_csv(path: str | None = None) -> int:
    path = path or settings.seed_csv
    if not os.path.exists(path):
        return 0
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        upsert_call({c: (row.get(c) or None) for c in COLUMNS})
    return len(rows)


def ensure_ready() -> None:
    try:
        _prepare()
    except (OSError, sqlite3.Error):
        settings.local_db_path = os.path.join(
            tempfile.gettempdir(), os.path.basename(settings.local_db_path)
        )
        _prepare()
    if _row_count() == 0:
        seed_from_csv()


def export_to_csv(path: str | None = None) -> int:
    path = path or settings.seed_csv
    init_db()
    with connect() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM calls_enriched ORDER BY call_date, call_id"
        ).fetchall()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        writer.writerows([[r[c] for c in COLUMNS] for r in rows])
    return len(rows)


if __name__ == "__main__":
    if "--export" in sys.argv:
        print(f"Exported {export_to_csv()} rows to {settings.seed_csv}")
    else:
        print("Usage: python -m local.db --export")
