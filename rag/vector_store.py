"""Build and query the transcript embedding index (local Chroma).

Build:  python -m rag.vector_store --build
Query is used by rag/agent.py via `search()`.

"""
from __future__ import annotations

import argparse
import functools
import re

from config.settings import settings


def _chunks(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    text = text or ""
    if not text:
        return []
    return [text[i:i + size] for i in range(0, len(text), size - overlap)]


@functools.lru_cache(maxsize=1)
def _store():
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    emb = HuggingFaceEmbeddings(model_name=settings.embedding_model)
    return Chroma(persist_directory=settings.chroma_dir, embedding_function=emb)


def build() -> None:
    """(Re)build the index from the database."""
    from local import db
    rows = db.all_transcripts()
    if not rows:
        print("No transcripts in the database. Run `python -m local.pipeline` first.")
        return

    texts, metadatas, ids = [], [], []
    for r in rows:
        for j, ch in enumerate(_chunks(r["transcript_en"])):
            texts.append(ch)
            metadatas.append({
                "call_id": r["call_id"],
                "call_date": r["call_date"],
                "product_mentioned": r.get("product_mentioned") or "none",
            })
            ids.append(f"{r['call_id']}-{j}")

    store = _store()
    store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    print(f"Indexed {len(texts)} chunks from {len(rows)} calls into {settings.chroma_dir}")


def _format(call_id, product, text) -> str:
    return f"[call {call_id} · {product}] {text}"


def _dense_search(query: str, k: int) -> list[str]:
    docs = _store().as_retriever(search_kwargs={"k": k}).invoke(query)
    return [
        _format(d.metadata.get("call_id"), d.metadata.get("product_mentioned"), d.page_content)
        for d in docs
    ]


def _keyword_search(query: str, k: int) -> list[str]:
    from local import db
    db.ensure_ready()
    terms = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}
    scored = []
    for r in db.all_transcripts():
        haystack = f"{r['transcript_en']} {r.get('product_mentioned') or ''}".lower()
        score = sum(haystack.count(t) for t in terms)
        if score:
            scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        _format(r["call_id"], r.get("product_mentioned") or "none", r["transcript_en"][:800])
        for _, r in scored[:k]
    ]


def search(query: str, k: int = 5) -> str:
    """Return relevant transcript snippets as cited text for the agent."""
    try:
        hits = _dense_search(query, k)
    except Exception:  # noqa: BLE001
        hits = []
    if not hits:
        hits = _keyword_search(query, k)
    if not hits:
        return "No relevant transcript snippets found."
    return "\n---\n".join(hits)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="build the index from the database")
    args = ap.parse_args()
    if args.build:
        build()
    else:
        print("Nothing to do. Use --build. (Query happens through rag/agent.py)")
