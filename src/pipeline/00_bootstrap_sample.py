import os
import sys
import pandas as pd
import json
import requests
from datetime import datetime, timedelta
from sqlalchemy import text
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database import get_engine, init_db

load_dotenv()

def bootstrap_sample_data():
    """
    DUAL MODE:
    1. If Token present: Downloads fresh data from BCRA (last 6 months).
    2. If NO Token: Loads static data from data/sample_bronze.json.
    """
    token = os.getenv("BCRA_API_TOKEN")
    engine = get_engine()
    init_db() # Ensure tables exist

    if token and token != "your_token_here" and token != "":
        print("🚀 [TOKEN DETECTED] Attempting to download fresh data from BCRA...")
        success = load_from_api(token, engine)
        if not success:
            print("⚠️ API request returned empty or failed. Falling back to DEMO MODE...")
            load_from_json(engine)
    else:
        print("💡 [DEMO MODE] Loading static data from sample_bronze.json...")
        load_from_json(engine)

def check_existing_data(engine, var_id):
    """Returns True if the variable already has data in the Bronze layer."""
    query = text("SELECT 1 FROM bronze_raw_ingestion WHERE variable_id = :v LIMIT 1")
    with engine.connect() as conn:
        result = conn.execute(query, {"v": var_id}).scalar()
        return result is not None

def load_from_json(engine):
    sample_path = os.path.join("data", "sample_bronze.json")
    if not os.path.exists(sample_path):
        print("❌ Error: data/sample_bronze.json not found")
        return

    with open(sample_path, "r") as f:
        data = json.load(f)
    
    # Group by variable_id to simulate Bronze structure
    df = pd.DataFrame(data)
    for var, group in df.groupby("variable_id"):
        if check_existing_data(engine, var):
            print(f"⏭️  Skipping {var}: Data already exists in Bronze.")
            continue
            
        payload = group[["d", "v"]].to_dict(orient="records")
        insert_to_bronze(engine, var, payload, "static_sample")

def load_from_api(token, engine):
    # BCRA Endpoints
    variables = ["usd", "reservas", "tasa_badlar"]
    headers = {"Authorization": f"Bearer {token}"}
    any_success = False
    
    for var in variables:
        if check_existing_data(engine, var):
            print(f"⏭️  Skipping {var}: Data already exists in Bronze.")
            any_success = True
            continue

        url = f"https://api.estadisticasbcra.com/{var}"
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if not data:
                    print(f"⚠️ {var}: API returned empty list.")
                    continue
                df = pd.DataFrame(data)
                col_map = {c: 'd' if c.lower() in ['d', 'fecha'] else 'v' if c.lower() in ['v', 'valor'] else c for c in df.columns}
                df.rename(columns=col_map, inplace=True)
                
                df['d'] = pd.to_datetime(df['d'])
                limit_date = datetime.now() - timedelta(days=180)
                df_sample = df[df['d'] >= limit_date]
                payload = df_sample.to_dict(orient='records')
                if payload:
                    insert_to_bronze(engine, var, payload, f"api_fresh_{datetime.now().date()}")
                    any_success = True
            else:
                print(f"❌ Error querying {var}: {response.status_code}")
        except Exception as e:
            print(f"❌ Critical API failure for {var}: {e}")
    return any_success

def insert_to_bronze(engine, var, payload, source):
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO bronze_raw_ingestion (source, variable_id, raw_payload, http_status, queried_url)
            VALUES (:s, :v, :p, :st, :u)
        """), {
            "s": source,
            "v": var,
            "p": json.dumps(payload),
            "st": 200,
            "u": "bootstrap_script"
        })
        conn.commit()
    print(f"✅ Data loaded into Bronze for: {var} (Source: {source})")

if __name__ == "__main__":
    bootstrap_sample_data()
