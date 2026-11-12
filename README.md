# VoC Call Analytics — Multilingual Voice-of-Customer Pipeline

Turn raw multilingual customer-call recordings into **queryable business intelligence**.

Audio (Hindi / Tamil / Marathi / English / code-mixed) → transcription → translation →
LLM extraction (sentiment, issue, product, resolution, upsell) → **SQLite** database →
**RAG** agent that answers natural-language questions with **cited call evidence**.

Stack: **Whisper (STT) · Sarvam (translate) · SQLite · embeddings + Chroma · LangChain (RAG) ·
Groq / Gemini (LLM) · Streamlit (dashboard)**.

There is one pipeline and one data store, used identically on your machine and on Render.

---

## How it fits together

| Layer | Tech | Why it's here |
|---|---|---|
| Processing | **Whisper + Sarvam + LLM** (`local/pipeline.py`) | Transcribe, translate and extract structured fields per call |
| Storage | **SQLite** (`voc_local.db`) | One small file, no server to run; the dashboard only reads it |
| Retrieval | **Chroma** (keyword fallback when not installed) | Pull actual transcript snippets as evidence |
| Reasoning | **LLM via LangChain** | Text-to-SQL for aggregates, cited answers from snippets |

---

## Project structure

```
voc-call-analytics/
├── README.md
├── requirements.txt             # dashboard / deploy dependencies
├── requirements-pipeline.txt    # + Whisper, embeddings, Chroma, LangChain
├── .env.example                 # copy to .env and fill in
├── config/settings.py           # central config (reads .env)
├── common/                      # stt, translate, llm helpers
├── local/
│   ├── pipeline.py              # audio -> SQLite
│   └── db.py                    # SQLite helper, auto-seed, CSV export
├── rag/
│   ├── vector_store.py          # build/query the embedding index
│   ├── sql_tool.py              # text-to-SQL aggregates tool
│   └── agent.py                 # retriever + SQL -> cited answer
├── dashboard/app.py             # Streamlit: trends + ask-a-question box
└── sample_data/
    ├── calls/                   # drop .mp3/.wav files here
    └── seed_calls.csv           # data the dashboard loads when the DB is empty
```

---

## Step-by-step

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
pip install -r requirements-pipeline.txt
```
`requirements.txt` is the light set the dashboard needs (and what Render installs);
`requirements-pipeline.txt` adds Whisper, embeddings, Chroma and LangChain for the pipeline.

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
Trend charts + a question box, all off the SQLite DB.

## Deploy the dashboard to Render

Local and Render run the exact same code and the same settings
(`LOCAL_DB_PATH=voc_local.db`). On startup the dashboard creates the SQLite DB if it is
missing and fills it from the committed seed file `sample_data/seed_calls.csv`, so a restart
or redeploy on Render's ephemeral disk always comes back with data.

1. Run the pipeline locally, then refresh the seed with your real results:
   ```bash
   python -m local.pipeline
   python -m local.db --export
   git add sample_data/seed_calls.csv && git commit -m "Update seed data" && git push
   ```
2. In Render, choose **New -> Blueprint** and select this repository.
3. Set `GROQ_API_KEY` in Render's environment-variable settings. Keep it secret.
4. Deploy. Render installs only `requirements.txt` and starts Streamlit on `$PORT`.

The seed file ships with 12 demo calls so the dashboard works out of the box; replace it
with your own export. The "Ask the calls" box uses vector search when Chroma and the
embedding model are installed (local), and falls back to keyword search over the same
transcripts when they are not (Render free tier).

Render's free disk is ephemeral, so the database is rebuilt from the seed CSV on every start.
For data that persists across restarts, the next step would be a managed Postgres database.

---

## Honest notes
- API shapes (Sarvam, Gemini) change — if a call 400s, check the provider's current docs; the
  structure here is what matters.
- Whisper `large-v3` wants a GPU for speed. On a laptop, the pipeline defaults to `small`.
- This is a portfolio/learning project. Don't put real customer audio in a public repo.

## License
MIT — do what you like, no warranty.
