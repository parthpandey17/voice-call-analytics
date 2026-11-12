# Databricks notebook — Step 3: embed transcripts + load into BigQuery
# Reads voc.calls_enriched_delta, chunks transcripts, embeds them, and writes:
#   - voc.calls_enriched      (structured rows) -> BigQuery
#   - voc.transcript_chunks   (chunk_text + embedding) -> BigQuery (for VECTOR_SEARCH)
#
# Needs the spark-bigquery connector on the cluster and a GCS temp bucket.

import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import pandas_udf, col, explode, posexplode, concat_ws, lit
from pyspark.sql.types import ArrayType, StringType, FloatType

spark = SparkSession.builder.getOrCreate()

GCP_PROJECT = "your_project"
BQ_DATASET = "voc"
TEMP_BUCKET = "your-temp-bucket"

enriched = spark.table("voc.calls_enriched_delta")

# 1. Load structured rows straight to BigQuery
(enriched.write.format("bigquery")
    .option("table", f"{GCP_PROJECT}.{BQ_DATASET}.calls_enriched")
    .option("temporaryGcsBucket", TEMP_BUCKET)
    .mode("overwrite")
    .save())
print("structured rows -> BigQuery")

# 2. Chunk transcripts (~800 chars) for retrieval
@pandas_udf(ArrayType(StringType()))
def chunk_udf(texts: pd.Series) -> pd.Series:
    def chunks(t, size=800, overlap=100):
        t = t or ""
        return [t[i:i + size] for i in range(0, len(t), size - overlap)] or [""]
    return texts.apply(chunks)

chunked = (enriched
    .withColumn("chunks", chunk_udf(col("transcript_en")))
    .select("call_id", "call_date", "product_mentioned", posexplode("chunks").alias("pos", "chunk_text"))
    .withColumn("chunk_id", concat_ws("-", col("call_id"), col("pos")))
)

# 3. Embed each chunk (model loads once per worker)
@pandas_udf(ArrayType(FloatType()))
def embed_udf(texts: pd.Series) -> pd.Series:
    from sentence_transformers import SentenceTransformer
    global _EMB
    try:
        _EMB
    except NameError:
        _EMB = SentenceTransformer("BAAI/bge-m3")
    vecs = _EMB.encode(texts.tolist(), normalize_embeddings=True)
    return pd.Series([v.tolist() for v in vecs])

embedded = chunked.withColumn("embedding", embed_udf(col("chunk_text")))

(embedded.select("chunk_id", "call_id", "call_date", "product_mentioned",
                 "chunk_text", "embedding")
    .write.format("bigquery")
    .option("table", f"{GCP_PROJECT}.{BQ_DATASET}.transcript_chunks")
    .option("temporaryGcsBucket", TEMP_BUCKET)
    .mode("overwrite")
    .save())
print("Step 3 complete -> embeddings in BigQuery")
