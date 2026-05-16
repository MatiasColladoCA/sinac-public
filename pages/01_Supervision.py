import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.database import get_engine
from datetime import datetime

st.set_page_config(page_title="SINAC: Supervision Dashboard", layout="wide")

st.title("🛡️ SINAC: Supervision Dashboard")
st.markdown("""
This is the supervision interface of the **National Intelligence System**. 
Here you can audit data quality and monitor pipeline execution.
""")

engine = get_engine()
try:
    with engine.connect() as conn:
        from sqlalchemy import text
        obs_count = conn.execute(text("SELECT COUNT(*) FROM silver_series_observations")).scalar()
        audit_count = conn.execute(text("SELECT COUNT(*) FROM silver_ingestion_audit")).scalar()
        events_count = conn.execute(text("SELECT COUNT(*) FROM historical_events")).scalar()

    col1, col2, col3 = st.columns(3)
    col1.metric("Silver Observations", obs_count)
    col2.metric("Audits Performed", audit_count)
    col3.metric("Historical Events", events_count)
except Exception as e:
    st.warning(f"Database not initialized or empty. Please run the pipeline first. Error: {e}")

st.sidebar.success("Explore the SINAC platform pages.")
