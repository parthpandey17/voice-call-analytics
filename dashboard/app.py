"""Streamlit dashboard: trends from the warehouse + an ask-a-question box.

Run:  streamlit run dashboard/app.py
Reads the local SQLite warehouse (or BigQuery when BACKEND=bigquery).
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config.settings import settings

st.set_page_config(page_title="VoC Call Analytics", layout="wide")


def load_df() -> pd.DataFrame:
    if settings.is_cloud:
        from google.cloud import bigquery
        client = bigquery.Client(project=settings.gcp_project)
        return client.query(f"SELECT * FROM `{settings.bq_table}`").to_dataframe()
    import sqlite3
    conn = sqlite3.connect(settings.local_db_path)
    try:
        return pd.read_sql_query("SELECT * FROM calls_enriched", conn)
    finally:
        conn.close()


st.title("🎧 Voice-of-Customer Call Analytics")
st.caption(f"Backend: {settings.backend} · LLM: {settings.llm_provider}")

try:
    df = load_df()
except Exception as exc:  # noqa: BLE001
    st.error(f"Couldn't load data: {exc}")
    st.stop()

if df.empty:
    st.warning("No calls yet. Run `python -m local.pipeline` first.")
    st.stop()

# ---- KPIs ----
c1, c2, c3, c4 = st.columns(4)
c1.metric("Calls analysed", len(df))
c2.metric("% negative", f"{(df['sentiment'].eq('negative').mean() * 100):.0f}%")
c3.metric("Resolution rate", f"{(df['resolved'].eq('yes').mean() * 100):.0f}%")
c4.metric("Upsell signals", int(df['upsell_opportunity'].eq('yes').sum()))

# ---- Charts ----
left, right = st.columns(2)
with left:
    st.subheader("Sentiment mix")
    s = df['sentiment'].value_counts().reset_index()
    s.columns = ['sentiment', 'count']
    st.plotly_chart(px.bar(s, x='sentiment', y='count'), use_container_width=True)

    st.subheader("Language mix")
    lm = df['language'].value_counts().reset_index()
    lm.columns = ['language', 'count']
    st.plotly_chart(px.pie(lm, names='language', values='count'), use_container_width=True)

with right:
    st.subheader("Top issue categories")
    cc = df['issue_category'].value_counts().head(10).reset_index()
    cc.columns = ['issue_category', 'count']
    st.plotly_chart(px.bar(cc, x='count', y='issue_category', orientation='h'),
                    use_container_width=True)

    st.subheader("Calls by product")
    pc = df['product_mentioned'].value_counts().head(10).reset_index()
    pc.columns = ['product', 'count']
    st.plotly_chart(px.bar(pc, x='count', y='product', orientation='h'),
                    use_container_width=True)

# ---- Ask a question (RAG) ----
st.divider()
st.subheader("💬 Ask the calls")
q = st.text_input("e.g. Top complaints about face wash, quote two customers")
if q:
    with st.spinner("Querying warehouse + retrieving transcripts..."):
        from rag.agent import answer
        st.markdown(answer(q))

with st.expander("See raw call rows"):
    st.dataframe(df, use_container_width=True)
