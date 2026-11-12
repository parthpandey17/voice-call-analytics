"""Text-to-SQL aggregates tool.

The LLM writes the SQL; this module gives it the schema and executes it safely
(SELECT-only) against the SQLite database. Used by rag/agent.py as the
"aggregates" tool.
"""
from __future__ import annotations

import re

from common import llm

SCHEMA_HINT = """Table: calls_enriched
Columns:
  call_id (str), call_date (TEXT, ISO yyyy-mm-dd), language (str),
  sentiment (positive|neutral|negative),
  issue_category (str), product_mentioned (str),
  resolved (yes|no|partial), upsell_opportunity (yes|no), summary (str)
"""

SQL_PROMPT = """You write a single read-only SQL query answering the question.
{schema}
Dialect: SQLite. Return ONLY the SQL, no markdown, no explanation.
Question: {q}
SQL:"""


def _generate_sql(question: str) -> str:
    raw = llm.complete(SQL_PROMPT.format(schema=SCHEMA_HINT, q=question))
    sql = re.sub(r"^```(?:sql)?|```$", "", raw.strip(), flags=re.IGNORECASE).strip()
    return sql


def _is_safe(sql: str) -> bool:
    low = sql.lower().strip()
    if not low.startswith("select"):
        return False
    banned = ("insert", "update", "delete", "drop", "alter", "create", "merge", ";--")
    return not any(b in low for b in banned)


def _run(sql: str) -> str:
    from local import db
    db.ensure_ready()
    with db.connect() as conn:
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    head = " | ".join(cols)
    body = "\n".join(" | ".join(str(r[c]) for c in cols) for r in rows[:50])
    return f"{head}\n{body}" if rows else "(no rows)"


def ask_aggregates(question: str) -> str:
    """Generate SQL for a counting/trend question, run it, return a small table."""
    sql = _generate_sql(question)
    if not _is_safe(sql):
        return f"Refused to run non-SELECT SQL: {sql}"
    try:
        result = _run(sql)
    except Exception as exc:  # noqa: BLE001
        return f"SQL error on `{sql}`: {exc}"
    return f"Query:\n{sql}\n\nResult:\n{result}"
