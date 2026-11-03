"""Text-to-SQL aggregates tool.

Backend-aware:
  - local    -> runs SQL against the SQLite warehouse
  - bigquery -> runs SQL against BigQuery

The LLM writes the SQL; this module gives it the schema and executes safely
(SELECT-only). Used by rag/agent.py as the "aggregates" tool.
"""
from __future__ import annotations

import re

from config.settings import settings
from common import llm

SCHEMA_HINT = """Table: calls_enriched
Columns:
  call_id (str), call_date (DATE), language (str),
  sentiment (positive|neutral|negative),
  issue_category (str), product_mentioned (str),
  resolved (yes|no|partial), upsell_opportunity (yes|no), summary (str)
"""

SQL_PROMPT = """You write a single read-only SQL query answering the question.
{schema}
Dialect: {dialect}. Return ONLY the SQL, no markdown, no explanation.
Question: {q}
SQL:"""


def _dialect() -> str:
    return "GoogleSQL (BigQuery)" if settings.is_cloud else "SQLite"


def _generate_sql(question: str) -> str:
    raw = llm.complete(SQL_PROMPT.format(schema=SCHEMA_HINT, dialect=_dialect(), q=question))
    sql = re.sub(r"^```(?:sql)?|```$", "", raw.strip(), flags=re.IGNORECASE).strip()
    return sql


def _is_safe(sql: str) -> bool:
    low = sql.lower().strip()
    if not low.startswith("select"):
        return False
    banned = ("insert", "update", "delete", "drop", "alter", "create", "merge", ";--")
    return not any(b in low for b in banned)


def _run_local(sql: str) -> str:
    from local import db
    with db.connect() as conn:
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    head = " | ".join(cols)
    body = "\n".join(" | ".join(str(r[c]) for c in cols) for r in rows[:50])
    return f"{head}\n{body}" if rows else "(no rows)"


def _run_bigquery(sql: str) -> str:
    from google.cloud import bigquery
    sql = sql.replace("calls_enriched", f"`{settings.bq_table}`")
    client = bigquery.Client(project=settings.gcp_project)
    rows = list(client.query(sql).result())
    if not rows:
        return "(no rows)"
    cols = list(rows[0].keys())
    head = " | ".join(cols)
    body = "\n".join(" | ".join(str(r[c]) for c in cols) for r in rows[:50])
    return f"{head}\n{body}"


def ask_aggregates(question: str) -> str:
    """Generate SQL for a counting/trend question, run it, return a small table."""
    sql = _generate_sql(question)
    if not _is_safe(sql):
        return f"Refused to run non-SELECT SQL: {sql}"
    try:
        result = _run_bigquery(sql) if settings.is_cloud else _run_local(sql)
    except Exception as exc:  # noqa: BLE001
        return f"SQL error on `{sql}`: {exc}"
    return f"Query:\n{sql}\n\nResult:\n{result}"
