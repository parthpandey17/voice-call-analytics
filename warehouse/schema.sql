-- BigQuery DDL for the warehouse layer.
-- Run in the BigQuery console (replace `your_project` and dataset `voc` as needed).

CREATE SCHEMA IF NOT EXISTS `your_project.voc`
OPTIONS (location = 'US');

CREATE TABLE IF NOT EXISTS `your_project.voc.calls_enriched` (
  call_id            STRING NOT NULL,
  call_date          DATE,
  language           STRING,
  transcript_src     STRING,   -- original-language transcript
  transcript_en      STRING,   -- English translation
  sentiment          STRING,   -- positive | neutral | negative
  issue_category     STRING,
  product_mentioned  STRING,
  resolved           STRING,   -- yes | no | partial
  upsell_opportunity STRING,   -- yes | no
  summary            STRING
)
PARTITION BY call_date
CLUSTER BY issue_category, product_mentioned;

-- Optional: embeddings table for native BigQuery VECTOR_SEARCH
-- (skip if you use the local Chroma index instead).
CREATE TABLE IF NOT EXISTS `your_project.voc.transcript_chunks` (
  chunk_id   STRING NOT NULL,
  call_id    STRING,
  call_date  DATE,
  product_mentioned STRING,
  chunk_text STRING,
  embedding  ARRAY<FLOAT64>   -- dimension must match your embedding model
);
