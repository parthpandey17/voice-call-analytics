"""LLM access: structured extraction + free-form answering.

One provider switch (gemini | groq) used by both the pipeline and the RAG agent.
"""
from __future__ import annotations

import json
import re

from config.settings import settings

EXTRACT_PROMPT = """You are analyzing a customer-support call transcript for a consumer brand.
Return STRICT JSON ONLY (no markdown fences, no commentary) with exactly these keys:
- sentiment: one of "positive", "neutral", "negative"
- issue_category: short label, e.g. "delivery delay", "product quality", "refund", "billing"
- product_mentioned: the product the customer talked about, else "none"
- resolved: one of "yes", "no", "partial"
- upsell_opportunity: one of "yes", "no"
- summary: ONE sentence describing the call

Transcript:
\"\"\"{transcript}\"\"\"
"""


def _clean_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response, tolerate fences."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    raw = match.group(0) if match else text
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "sentiment": "neutral", "issue_category": "unknown",
            "product_mentioned": "none", "resolved": "no",
            "upsell_opportunity": "no", "summary": text[:200],
        }


def _gemini(model: str, prompt: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=settings.google_api_key)
    return genai.GenerativeModel(model).generate_content(prompt).text


def _groq(prompt: str) -> str:
    from groq import Groq
    client = Groq(api_key=settings.groq_api_key)
    resp = client.chat.completions.create(
        model=settings.groq_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return resp.choices[0].message.content


def complete(prompt: str, *, for_answer: bool = False) -> str:
    """Raw completion. `for_answer` picks the higher-quality answer model for Gemini."""
    if settings.llm_provider == "gemini":
        model = settings.gemini_answer_model if for_answer else settings.gemini_extract_model
        return _gemini(model, prompt)
    return _groq(prompt)


def extract(transcript_en: str) -> dict:
    """Structured call analysis as a dict (keys match the database schema)."""
    out = complete(EXTRACT_PROMPT.format(transcript=transcript_en[:12000]))
    return _clean_json(out)
