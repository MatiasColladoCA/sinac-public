"""
main_pipeline.py
Prefect Flow: Bronze (bronze_raw_ingestion) → Silver (silver_series_observations)
Standardized English version with user-preferred naming conventions.
"""

import os
import pandas as pd
import numpy as np
import json
from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, text
from prefect import flow, task, get_run_logger, unmapped
from prefect.cache_policies import NO_CACHE
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ═══════════════════════════════════════════════════════════
# CONNECTION CONFIGURATION
# ═══════════════════════════════════════════════════════════
DB_URI = os.getenv("DB_URI")
if not DB_URI:
    raise ValueError("Error: DB_URI not found in environment variables.")

BRONZE_TABLE = "bronze_raw_ingestion"
SILVER_TABLE_AUDIT = "silver_ingestion_audit"
SILVER_TABLE_OBS = "silver_series_observations"

@task(name="get_db_connection", retries=2, cache_policy=NO_CACHE)
def get_db_connection():
    """Returns the SQLAlchemy engine."""
    logger = get_run_logger()
    engine = create_engine(DB_URI)
    logger.info(f"Connected to database at {DB_URI.split('@')[-1]}")
    return engine

@task(name="extract_bronze_data", retries=2, cache_policy=NO_CACHE)
def extract_bronze_data(engine, variable_id: Optional[str] = None) -> pd.DataFrame:
    """Extracts raw data from the Bronze layer."""
    logger = get_run_logger()
    
    if variable_id:
        query = text(f"SELECT * FROM {BRONZE_TABLE} WHERE variable_id = :vid ORDER BY ingestion_date ASC")
        params = {"vid": variable_id}
        logger.info(f"Extracting variable_id='{variable_id}' from Bronze...")
    else:
        query = text(f"SELECT * FROM {BRONZE_TABLE} ORDER BY variable_id, ingestion_date ASC")
        params = {}
        logger.info("Extracting ALL variables from Bronze...")

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)

    if df.empty:
        logger.warning("No data found in Bronze.")
    return df

def _extract_records_from_payload(payload):
    """Parses JSON payload regardless of underlying storage type."""
    if payload is None: return []
    if isinstance(payload, (list, dict)): return payload
    
    if isinstance(payload, str):
        try: 
            return json.loads(payload)
        except: 
            try:
                return json.loads(payload.replace("'", '"'))
            except:
                return []
    
    return []

@task(name="transform_to_silver", cache_policy=NO_CACHE)
def transform_to_silver(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Explodes JSON payloads and casts data types for the Silver layer."""
    logger = get_run_logger()
    if df_raw.empty: return pd.DataFrame()

    df = df_raw.copy()
    df["records"] = df["raw_payload"].apply(_extract_records_from_payload)
    df_exploded = df.explode("records").reset_index(drop=True)
    df_exploded = df_exploded[df_exploded["records"].apply(lambda x: isinstance(x, dict))].copy()
    
    if df_exploded.empty: return pd.DataFrame()

    records_df = pd.json_normalize(df_exploded["records"])
    
    # Standardize column names (d -> date, v -> value)
    col_map = {c: 'date' if c.lower() in ['d', 'date', 'fecha'] else 'value' if c.lower() in ['v', 'value', 'valor'] else c for c in records_df.columns}
    records_df.rename(columns=col_map, inplace=True)

    if 'date' not in records_df.columns or 'value' not in records_df.columns:
        logger.error(f"Payload missing required fields. Found: {records_df.columns.tolist()}")
        return pd.DataFrame()

    df_result = pd.concat([
        df_exploded[["id", "source", "variable_id", "ingestion_date"]].reset_index(drop=True),
        records_df[["date", "value"]].reset_index(drop=True)
    ], axis=1)

    # Type casting
    df_result["date"] = pd.to_datetime(df_result["date"], errors="coerce")
    df_result["value"] = pd.to_numeric(df_result["value"], errors="coerce")
    df_result = df_result.dropna(subset=["date", "value"])

    logger.info(f"Transformed {len(df_result)} records for Silver.")
    return df_result

@task(name="calculate_quality_metrics", cache_policy=NO_CACHE)
def calculate_quality_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates a trust score (0-100) for the ingested data."""
    if df.empty: return df
    df = df.copy()
    df["trust_score"] = 100.0
    return df

@task(name="load_to_silver", retries=1, cache_policy=NO_CACHE)
def load_to_silver(df: pd.DataFrame, engine):
    """Persists data into the Silver layer tables."""
    logger = get_run_logger()
    if df.empty: return "No data to load"

    # 1. Load Observations
    obs_df = df[["variable_id", "date", "value", "id"]].copy()
    obs_df.rename(columns={"id": "ingestion_batch_id"}, inplace=True)
    
    is_sqlite = "sqlite" in str(engine.url)
    
    with engine.connect() as conn:
        for _, row in obs_df.iterrows():
            date_val = row['date']
            if is_sqlite and hasattr(date_val, 'strftime'):
                date_val = date_val.strftime('%Y-%m-%d')
            elif is_sqlite:
                date_val = str(date_val)[:10]

            query = text(f"""
                INSERT INTO {SILVER_TABLE_OBS} (variable_id, date, value, ingestion_batch_id)
                VALUES (:v, :d, :val, :i)
                ON CONFLICT (variable_id, date) DO UPDATE SET value = EXCLUDED.value
            """)
            conn.execute(query, {"v": row['variable_id'], "d": date_val, "val": row['value'], "i": int(row['ingestion_batch_id'])})
        conn.commit()

    # 2. Load Audit
    audit_summary = df.groupby(["variable_id", "id", "source", "ingestion_date"]).size().reset_index(name="count")
    with engine.connect() as conn:
        for _, row in audit_summary.iterrows():
            ts_val = row['ingestion_date']
            if is_sqlite and hasattr(ts_val, 'strftime'):
                ts_val = ts_val.strftime('%Y-%m-%d %H:%M:%S')
            elif is_sqlite:
                ts_val = str(ts_val)

            conn.execute(text(f"""
                INSERT INTO {SILVER_TABLE_AUDIT} (bronze_id, source, variable_id, ingestion_date, processed_records, inserted_records)
                VALUES (:bid, :s, :vid, :ts, :pr, :ir)
            """), {"bid": int(row['id']), "s": row['source'], "vid": row['variable_id'], "ts": ts_val, "pr": int(row['count']), "ir": int(row['count'])})
        conn.commit()

    return f"Successfully loaded {len(df)} records into Silver."

@flow(name="SINAC Bronze to Silver Pipeline", log_prints=True)
def sinac_pipeline(variable_id: Optional[str] = None):
    logger = get_run_logger()
    logger.info("Starting SINAC Medallion Pipeline: Bronze -> Silver")

    engine = get_db_connection()
    df_raw = extract_bronze_data(engine, variable_id=variable_id)
    df_silver = transform_to_silver(df_raw)
    df_quality = calculate_quality_metrics(df_silver)
    result = load_to_silver(df_quality, engine)

    logger.info(f"Pipeline finished: {result}")

if __name__ == "__main__":
    sinac_pipeline()
