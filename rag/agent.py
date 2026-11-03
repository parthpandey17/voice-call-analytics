"""The RAG answer layer.

Combines two retrieval paths and lets the LLM synthesize a cited answer:
  - aggregates: text-to-SQL over the warehouse (counts, %, trends)
  - evidence:   vector retrieval of actual transcript snippets

Kept as an explicit two-tool pattern (rather than a black-box agent) so it runs
with either Gemini or Groq and is easy to explain in an interview.

Usage:  python -m rag.agent "your question"
"""
from __future__ import annotations

import sys
import textwrap

from common import llm
from rag import bq_tool, vector_store

SYNTH_PROMPT = """You are a Voice-of-Customer analyst. Answer the user's question using
ONLY the data below. Cite call IDs in [brackets] when you quote or reference a call.
If the data is insufficient, say so plainly.

== AGGREGATE DATA (from SQL over the warehouse) ==
{aggregates}

== TRANSCRIPT EVIDENCE (retrieved snippets) ==
{evidence}

== QUESTION ==
{question}

Answer:"""


def answer(question: str) -> str:
    aggregates = bq_tool.ask_aggregates(question)
    evidence = vector_store.search(question, k=5)
    prompt = SYNTH_PROMPT.format(
        aggregates=aggregates, evidence=evidence, question=question
    )
    return llm.complete(prompt, for_answer=True)


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python -m rag.agent "your question"')
        return
    question = " ".join(sys.argv[1:])
    print(f"\nQ: {question}\n")
    print(textwrap.fill(answer(question), width=100))


if __name__ == "__main__":
    main()
