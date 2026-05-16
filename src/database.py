import os
import pandas as pd
from sqlalchemy import create_engine, text, Column, Integer, String, Float, DateTime, Date, JSON, Numeric
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Base path for SQLite fallback
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "data", "sinac_fallback.db")

DB_URI = os.getenv("DB_URI", f"sqlite:///{DEFAULT_DB_PATH}")

engine = create_engine(DB_URI)
Base = declarative_base()

def get_engine():
    return engine

def init_db():
    """Initializes the database schema (Bronze and Silver) in an idempotent manner."""
    is_sqlite = "sqlite" in DB_URI
    pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "SERIAL PRIMARY KEY"
    json_type = "JSON" if is_sqlite else "JSONB"
    
    with engine.connect() as conn:
        # Bronze Layer: Raw Ingestion
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS bronze_raw_ingestion (
                id {pk_type},
                source VARCHAR(50),
                variable_id VARCHAR(50),
                ingestion_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                raw_payload {json_type},
                http_status INTEGER,
                queried_url TEXT,
                schema_version VARCHAR(20),
                ingestion_metadata {json_type}
            );
        """))
        
        # Silver Layer: Ingestion Audit
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS silver_ingestion_audit (
                id {pk_type},
                bronze_id INTEGER,
                source VARCHAR(50),
                variable_id VARCHAR(50),
                ingestion_date TIMESTAMP,
                processed_records INTEGER,
                inserted_records INTEGER,
                trust_score NUMERIC(5,2),
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # Silver Layer: Observations (Time Series)
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS silver_series_observations (
                id {pk_type},
                variable_id VARCHAR(50) NOT NULL,
                date DATE NOT NULL,
                value NUMERIC(18,6),
                quality_flag VARCHAR(20) DEFAULT 'valid',
                ingestion_batch_id INTEGER,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(variable_id, date)
            );
        """))
        
        # Historical Events Table (Forensic Layer)
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS historical_events (
                id {pk_type},
                date DATE NOT NULL,
                event TEXT NOT NULL,
                description TEXT,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        conn.commit()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized at: {DB_URI}")
