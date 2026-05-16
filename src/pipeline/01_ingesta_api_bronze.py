#!/usr/bin/env python3
"""
Ingestion to Bronze Layer.
Standardized English version.
"""

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import text
from src.database import get_engine

load_dotenv()

TOKEN = os.getenv("BCRA_API_TOKEN")
BASE_URL = "https://api.estadisticasbcra.com"

engine = get_engine()

# Map for multi-source scalability
MACRO_ENDPOINTS = {
    "leliq_rate": "/tasa_leliq",
    "badlar_rate": "/tasa_badlar",
    "monthly_inflation": "/inflacion_mensual_oficial",
    "intl_reserves": "/reservas",
    "official_usd": "/usd",
}

def fetch_and_bronze():
    """Fetches raw data and stores it in the Bronze layer."""
    if not TOKEN:
        print("⚠️ BCRA_API_TOKEN not found. Skipping API ingestion.")
        return

    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    for var_id, endpoint in MACRO_ENDPOINTS.items():
        url = f"{BASE_URL}{endpoint}"
        print(f"⬇️ Fetching {var_id} ... ", end="", flush=True)
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            http_status = response.status_code
            
            try:
                payload = response.json()
            except Exception:
                payload = {"error": "non_json_response", "content": response.text[:500]}
            
            # Store in Bronze with standardized column names
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO bronze_raw_ingestion 
                            (source, variable_id, raw_payload, http_status, queried_url)
                        VALUES 
                            (:source, :vid, :payload, :status, :url)
                    """),
                    {
                        "source": "bcra_api",
                        "vid": var_id,
                        "payload": json.dumps(payload),
                        "status": http_status,
                        "url": url
                    }
                )
                conn.commit()
            
            print(f"Stored ({http_status})")
            
        except Exception as e:
            print(f"FAILED: {e}")

if __name__ == "__main__":
    fetch_and_bronze()
