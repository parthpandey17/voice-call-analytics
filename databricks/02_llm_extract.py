# Databricks notebook — Step 2: LLM structured extraction
# Reads voc.calls_transcribed, runs the LLM per call, writes voc.calls_enriched.
# Cluster env var needed: GOOGLE_API_KEY (Gemini) or GROQ_API_KEY.

import os
import json
import re
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import pandas_udf, col, current_date, md5, concat_ws
from pyspark.sql.types import StringType

spark = SparkSession.builder.getOrCreate()

EXTRACT_PROMPT = """You are analyzing a customer-support call transcript.
Return STRICT JSON ONLY with keys: sentiment (positive/neutral/negative),
issue_category, product_mentioned, resolved (yes/no/partial),
upsell_opportunity (yes/no), summary (one sentence).
Transcript:
\"\"\"{t}\"\"\""""


def _clean(text: str) -> str:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return m.group(0) if m else "{}"


@pandas_udf(StringType())
def extract_udf(transcripts: pd.Series) -> pd.Series:
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel("gemini-1.5-flash")
    out = []
    for t in transcripts:
        try:
            resp = model.generate_content(EXTRACT_PROMPT.format(t=(t or "")[:12000]))
            out.append(_clean(resp.text))
        except Exception as exc:
            out.append(json.dumps({"summary": f"error: {exc}"}))
    return pd.Series(out)


df = spark.table("voc.calls_transcribed")
df = df.withColumn("analysis_json", extract_udf(col("transcript_en")))

# Flatten JSON into typed columns
from pyspark.sql.functions import get_json_object

enriched = (
    df.withColumn("call_id", md5(col("path")))
      .withColumn("call_date", current_date())
      .withColumn("sentiment", get_json_object("analysis_json", "$.sentiment"))
      .withColumn("issue_category", get_json_object("analysis_json", "$.issue_category"))
      .withColumn("product_mentioned", get_json_object("analysis_json", "$.product_mentioned"))
      .withColumn("resolved", get_json_object("analysis_json", "$.resolved"))
      .withColumn("upsell_opportunity", get_json_object("analysis_json", "$.upsell_opportunity"))
      .withColumn("summary", get_json_object("analysis_json", "$.summary"))
      .select("call_id", "call_date", "language", "transcript_src", "transcript_en",
              "sentiment", "issue_category", "product_mentioned", "resolved",
              "upsell_opportunity", "summary")
)

enriched.write.format("delta").mode("overwrite").saveAsTable("voc.calls_enriched_delta")
print("Step 2 complete -> voc.calls_enriched_delta")
