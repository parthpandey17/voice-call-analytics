"""Build and query the transcript embedding index (local Chroma).

Build:  python -m rag.vector_store --build
Query is used by rag/agent.py via `search()`.

For the cloud backend you'd query BigQuery's VECTOR_SEARCH instead; the
`transcript_chunks` table and embeddings are produced by databricks/03.
"""
from __future__ import annotations

import argparse
import functools

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
    """(Re)build the index from the local warehouse."""
    from local import db
    rows = db.all_transcripts()
    if not rows:
        print("No transcripts in the warehouse. Run `python -m local.pipeline` first.")
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


def search(query: str, k: int = 5) -> str:
    """Return relevant transcript snippets as cited text for the agent."""
    docs = _store().as_retriever(search_kwargs={"k": k}).invoke(query)
    if not docs:
        return "No relevant transcript snippets found."
    return "\n---\n".join(
        f"[call {d.metadata.get('call_id')} · {d.metadata.get('product_mentioned')}] "
        f"{d.page_content}"
        for d in docs
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="build the index from the warehouse")
    args = ap.parse_args()
    if args.build:
        build()
    else:
        print("Nothing to do. Use --build. (Query happens through rag/agent.py)")
