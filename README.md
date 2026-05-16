# SINAC

**National Intelligence System**

Data pipeline for reproducible analysis of macroeconomic variables.

![Architecture](https://img.shields.io/badge/Architecture-Medallion-blue)
![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![Prefect](https://img.shields.io/badge/Orchestration-Prefect-white?logo=prefect)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%20%7C%20SQLite-blue?logo=postgresql)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Overview

SINAC automates the ingestion, curation, and auditing of economic time series (BCRA, INDEC, and others) using Prefect orchestration and a decision-making engine based on metafeatures.

It does not predict. It does not provide opinions. It structures data so that other models (or analysts) do not start with "garbage" data.

---

## Architecture

```
Bronze (raw_data.bronze_raw_ingestion)
    └── raw_payload: Immutable JSONB
    └── Prefect: extract_bronze_data → expand_json_payload → cast_data_types

Silver (refined_data.silver_macro_variables)
    └── Decision Engine (YAML): imputation, model, alert
    └── Validation: NaT, NaN, duplicates, temporal gaps
    └── Auditing: structlog → logs/pipeline_audit.jsonl

Gold (In Development)
    └── Feature engineering, statistical modeling
```

---

## Decision Engine

The pipeline includes a configurable decision tree (`config/pipeline_rules.yaml`) that automates:

- **Imputation:** Mean, interpolation, or alert based on the % of missing data.
- **Modeling:** Prophet, ARIMA, or rejection based on series quality.
- **Auditing:** Structured logs (structlog) for every decision to ensure gov-tech traceability.

---

## Environments: Production vs. Public

| Component | Production (Private) | Public Repository (Demo) |
| :--- | :--- | :--- |
| **Database** | PostgreSQL (Docker) | Embedded SQLite (`data/*_fallback.db`) |
| **Ingestion** | Real-time APIs | `data/sample_bronze.json` |
| **Orchestration** | Prefect OSS + cron | Local Prefect (serverless) |
| **Supervision UI** | Streamlit + Prefect UI | Local Streamlit |

---

## Quickstart (Local Demo)

```bash
# 1. Clone and prepare environment
git clone https://github.com/your-user/sinac.git
cd sinac
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Initialize database and load sample (Bootstrap)
# If you don't have an API TOKEN, it will automatically load data/sample_bronze.json
python src/pipeline/00_bootstrap_sample.py

# 3. Execute refining pipeline (Bronze -> Silver)
python src/main_pipeline.py

# 4. View Prefect UI (in another terminal)
prefect server start

# 5. View Analyst UI
streamlit run main_streamlit.py
```

---

## Repository Structure

```
sinac/
├── config/
│   └── pipeline_rules.yaml       # Decision engine rules
├── scripts/
│   ├── start.sh                  # Environment setup script
│   └── backup.sh                 # Database backup (Private Lab only)
├── src/
│   ├── pipeline/
│   │   └── main_pipeline.py      # Main Prefect Flow
│   ├── database.py               # SQLAlchemy Bronze/Silver
│   ├── decision_engine.py        # Metafeatures + decision tree
│   ├── audit_logger.py           # structlog JSONL
│   └── config_models.py          # Pydantic validation
├── data/
│   ├── sample_bronze.json        # Demo without API
│   └── sinac_fallback.db         # Initial SQLite DB
├── notebooks/                    # Research & Analysis (Private Lab only)
├── main_streamlit.py             # Supervision UI
├── docs/
│   └── ARCHITECTURE.md           # Engineering documentation
├── requirements.txt
└── .env.example                  # Environment variables (no secrets)
```

---

## Roadmap

| Phase | Status | Description |
| :--- | :--- | :--- |
| **1: Infrastructure** | ✅ Complete | Ingest, JSONB storage, Medallion schema. |
| **2: Curation & Orchestration** | ✅ Complete | Prefect pipeline, decision engine, validation, auditing. |
| **3: Analysis & Modeling** | 📋 Planned | Feature engineering, regime detection, forecasting. |

---

## Technical Documentation
For more details on engineering decisions and security, please refer to [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## License

MIT. Free to use for personal and commercial purposes with attribution.
