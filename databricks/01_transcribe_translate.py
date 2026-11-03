# Databricks notebook — Step 1: transcribe + detect language + translate to English
# Runs as a Spark batch over all audio in the GCS bucket, parallelized across workers.
# Cluster: a small GPU cluster speeds Whisper up a lot. Set env vars on the cluster:
#   SARVAM_API_KEY, GCP_PROJECT, (and mount/auth for GCS).
#
# Writes an intermediate Delta table: voc.calls_transcribed

import os
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import pandas_udf
from pyspark.sql.types import StructType, StructField, StringType

spark = SparkSession.builder.getOrCreate()

AUDIO_GLOB = "gs://your-audio-bucket/calls/*.mp3"

# 1. One row per audio file (binaryFile gives us the path)
audio_df = (
    spark.read.format("binaryFile")
    .option("pathGlobFilter", "*.mp3")
    .load("gs://your-audio-bucket/calls/")
    .select("path")
)

# 2. Transcribe with Whisper (model loads once per worker via a global cache)
stt_schema = StructType([
    StructField("transcript_src", StringType()),
    StructField("language", StringType()),
    StructField("whisper_en", StringType()),
])


@pandas_udf(stt_schema)
def transcribe_udf(paths: pd.Series) -> pd.DataFrame:
    import whisper
    global _MODEL
    try:
        _MODEL
    except NameError:
        _MODEL = whisper.load_model("large-v3")

    rows = []
    for p in paths:
        local = p.replace("gs://", "/dbfs/mnt/")  # adjust to your mount
        r = _MODEL.transcribe(local)
        lang = r.get("language", "unknown")
        whisper_en = ""
        if lang != "en":
            whisper_en = _MODEL.transcribe(local, task="translate").get("text", "")
        rows.append((r.get("text", ""), lang, whisper_en))
    return pd.DataFrame(rows, columns=["transcript_src", "language", "whisper_en"])


transcribed = audio_df.withColumn("stt", transcribe_udf("path")).select("path", "stt.*")

# 3. Translate to English with Sarvam (fallback to Whisper's own translation)
import requests

LANG_MAP = {"hi": "hi-IN", "ta": "ta-IN", "te": "te-IN", "kn": "kn-IN",
            "ml": "ml-IN", "mr": "mr-IN", "bn": "bn-IN", "gu": "gu-IN", "en": "en-IN"}


@pandas_udf(StringType())
def translate_udf(src: pd.Series, lang: pd.Series, wen: pd.Series) -> pd.Series:
    key = os.environ.get("SARVAM_API_KEY", "")
    out = []
    for text, lg, fallback in zip(src, lang, wen):
        if lg == "en" or not text:
            out.append(text)
        elif not key:
            out.append(fallback or text)
        else:
            try:
                resp = requests.post(
                    "https://api.sarvam.ai/translate",
                    headers={"api-subscription-key": key},
                    json={"input": text[:1000],
                          "source_language_code": LANG_MAP.get(lg, "hi-IN"),
                          "target_language_code": "en-IN"},
                    timeout=30,
                )
                out.append(resp.json().get("translated_text", fallback or text))
            except Exception:
                out.append(fallback or text)
    return pd.Series(out)


final = transcribed.withColumn(
    "transcript_en", translate_udf("transcript_src", "language", "whisper_en")
).drop("whisper_en")

final.write.format("delta").mode("overwrite").saveAsTable("voc.calls_transcribed")
print("Step 1 complete -> voc.calls_transcribed")
