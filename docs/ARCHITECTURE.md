# 🏗️ SINAC: System Architecture & Engineering Decisions

This document outlines the architectural patterns and DevOps strategies implemented in the SINAC project to ensure scalability, security, and reproducibility.

## 1. Data Architecture (Medallion Pattern)
The project follows a refined **Medallion Architecture** to manage the data lifecycle:

*   **Bronze Layer**: Raw ingestion from the BCRA API. Data is stored as-is in `JSONB` format (PostgreSQL) or `TEXT` (SQLite) to preserve the original source of truth.
*   **Silver Layer**: 
    *   **series_observations**: Cleaned, typed, and deduplicated time-series data in Long Form.
    *   **ingestion_audit**: Metadata and traceability logs for every API call, linked to observations via Foreign Keys.
*   **Gold Layer**: Dynamic pivoting and aggregations performed in-memory via Streamlit/Pandas for high-performance visualization.

## 2. CI/CD & Security: Selective Synchronization
To balance private experimentation with a professional public portfolio, SINAC uses a **Dual-Repository Strategy**:

*   **Private Lab**: Contains sensitive notebooks, experimental scripts, and full data history.
*   **Public Portfolio**: A curated, clean version of the codebase.
*   **Secure Sync**: Synchronization is automated via GitHub Actions using the `cpina/github-action-push-to-another-repository` action.
    *   **Security Measure**: The action is pinned to a specific **Commit SHA** (`55306fa`) rather than a branch tag to prevent Supply Chain Attacks and ensure code immutability during execution.

## 3. Reproducibility: The Bootstrap Process
To ensure the project is "clonable and executable" by third parties without requiring immediate API credentials:

*   **Idempotent Schema**: The database initialization logic (`src/database.py`) uses `IF NOT EXISTS` clauses to handle both PostgreSQL and SQLite environments automatically.
*   **Dual-Mode Bootstrap**: The `00_bootstrap_sample.py` script detects the presence of a `BCRA_API_TOKEN`. 
    *   If present: Fetches live data.
    *   If absent: Rehydrates the local database using `data/sample_bronze.json`.

## 4. Technology Stack
*   **Orchestration**: Prefect (for resilient data pipelines).
*   **Visualization**: Streamlit & Plotly (interactive dashboard).
*   **Database**: SQLAlchemy (ORM for DB engine agnosticism).
