# VoC Call Analytics — Multilingual Voice-of-Customer Pipeline

Turn raw multilingual customer-call recordings into **queryable business intelligence**.

Audio (Hindi / Tamil / Marathi / English / code-mixed) → transcription → translation →
LLM extraction (sentiment, issue, product, resolution, upsell) → **BigQuery** warehouse →
**RAG** agent that answers natural-language questions with **cited call evidence**.

Stack: **Whisper (STT) · Sarvam (translate) · Databricks/Spark (scale) · BigQuery (warehouse) ·
embeddings + vector search · LangChain (RAG) · Streamlit (dashboard)**.

> Maps directly to a "Voice of Consumer" style brief: analyse support/sales calls at scale to
> surface themes for R&D, packaging and e-commerce teams.

---

## Why this architecture (the 30-second version)

| Layer | Tech | Why it's here |
|---|---|---|
| Heavy batch processing | **Databricks / Spark** | Transcription + embeddings over thousands of files is parallel, compute-heavy work |
| Warehouse / serving | **BigQuery** | Analysts, dashboards, and text-to-SQL query the structured results |
| Retrieval | **Vector store** (Chroma, or BigQuery `VECTOR_SEARCH`) | Pull actual transcript snippets as evidence |
| Reasoning | **LLM via LangChain** | Extraction + answering questions, routing between SQL and retrieval |

Databricks and BigQuery overlap — the clean split is **Databricks = processing/ML engine,
BigQuery = warehouse/serving layer** (lakehouse feeds warehouse). You can defend that in an interview.

---

## Two ways to run it

1. **Local demo (`local/` folder)** — no cloud needed. Runs the whole pipeline on your laptop
   against the sample audio, writes results to a local SQLite file + local Chroma index. **Start here.**
2. **Cloud scale (`databricks/` + `warehouse/`)** — the same steps as a Spark batch job writing to
   real BigQuery. This is the version you describe on your resume.

---

## Project structure

```
voc-call-analytics/
├── README.md
├── requirements.txt
├── .env.example                 # copy to .env and fill in
├── .gitignore
├── config/
│   └── settings.py              # central config (reads .env)
├── ingest/
│   └── upload_audio.py          # push audio to GCS / DBFS (cloud path)
├── local/
│   ├── pipeline.py              # FULL pipeline on your laptop (no cloud) -> SQLite
│   └── db.py                    # tiny SQLite helper
├── databricks/
│   ├── 01_transcribe_translate.py
│   ├── 02_llm_extract.py
│   ├── 03_embed_and_load.py
│   └── job_config.json
├── warehouse/
│   ├── schema.sql               # BigQuery DDL
│   └── views.sql                # analytics views
├── rag/
│   ├── vector_store.py          # build/query the embedding index
│   ├── bq_tool.py               # text-to-SQL tool (BigQuery or local SQLite)
│   └── agent.py                 # LangChain agent: retriever + SQL -> cited answer
├── dashboard/
│   └── app.py                   # Streamlit: trends + ask-a-question box
└── sample_data/
    └── calls/                   # drop a few .mp3/.wav files here
```

---

## Step-by-step: run the LOCAL demo

### 0. Prereqs
- Python 3.10+
- `ffmpeg` installed (Whisper needs it): `sudo apt install ffmpeg` / `brew install ffmpeg`
- An LLM key: either `GOOGLE_API_KEY` (Gemini) **or** `GROQ_API_KEY`. Groq has a generous free tier.
- (Optional) `SARVAM_API_KEY` for best Indian-language translation. Without it, Whisper's own
  English translation is used as a fallback.

### 1. Install
```bash
cd voc-call-analytics
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# open .env, set LLM_PROVIDER and the matching key
```

### 3. Add audio
Drop 2–5 short recordings into `sample_data/calls/` (`.mp3` or `.wav`).
No recordings handy? Grab the sample call audio from the Sarvam cookbook repo
(`sarvamai/sarvam-ai-cookbook`, `sample_data/call_analytics_audios/`).

### 4. Run the pipeline
```bash
python -m local.pipeline
```
This transcribes → detects language → translates → runs LLM extraction, and writes rows to
`voc_local.db` (SQLite). You'll see one row per call with sentiment / category / product etc.

### 5. Build the retrieval index
```bash
python -m rag.vector_store --build
```
Chunks + embeds the English transcripts into a local Chroma index at `./chroma`.

### 6. Ask questions
```bash
python -m rag.agent "Top complaints about face wash this month, quote two customers"
```

### 7. Dashboard
```bash
streamlit run dashboard/app.py
```
Trend charts + a question box, all off the local DB.

---

## Step-by-step: the CLOUD / BigQuery + Databricks version

1. **GCP setup** — create a project, enable BigQuery, create a dataset `voc`, make a service
   account with BigQuery + Storage access, download its JSON key.
2. **Create tables** — run `warehouse/schema.sql` and `warehouse/views.sql` in the BigQuery console.
3. **Upload audio** — `python ingest/upload_audio.py` pushes `sample_data/calls/` to your GCS bucket.
4. **Databricks** — create a workspace + a small GPU cluster (for Whisper). Import the three
   `databricks/` notebooks, set cluster env vars (keys + GCP project), and run them in order:
   `01` (transcribe+translate) → `02` (LLM extract) → `03` (embed + load to BigQuery).
   `job_config.json` shows a job definition that chains all three.
5. **Point RAG at BigQuery** — set `BACKEND=bigquery` in `.env`. `rag/bq_tool.py` and
   `rag/vector_store.py` switch to BigQuery automatically.
6. **Dashboard** — same `streamlit run dashboard/app.py`, now reading BigQuery.

---

## Honest notes
- API shapes (Sarvam, Gemini) change — if a call 400s, check the provider's current docs; the
  structure here is what matters.
- Whisper `large-v3` wants a GPU for speed. On a laptop, the local pipeline defaults to `small`.
- This is a portfolio/learning project. Don't put real customer audio in a public repo.

## License
MIT — do what you like, no warranty.
