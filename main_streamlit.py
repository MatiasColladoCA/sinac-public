import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import text
import sys
import os
from datetime import datetime

# Page Configuration
st.set_page_config(page_title="SINAC: Macro Intelligence Dashboard", layout="wide")

# 1. Database Connection
try:
    from src.database import get_engine
    engine = get_engine()
except Exception as e:
    st.error(f"Error connecting to database: {e}")
    st.stop()

# 2. Data Loading
@st.cache_data(ttl=60)
def load_macro_data():
    try:
        # Standardized English schema: silver_series_observations
        query = "SELECT variable_id, date, value FROM silver_series_observations"
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        
        if df.empty:
            return pd.DataFrame()
            
        df['date'] = pd.to_datetime(df['date'])
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna(subset=['date', 'value'])
        
        df_pivot = df.pivot_table(index='date', columns='variable_id', values='value', aggfunc='mean')
        df_pivot = df_pivot.sort_index()
        return df_pivot
    except Exception as e:
        # Fallback to Bronze (JSONB extraction) - Standardized names
        try:
            query = "SELECT variable_id, raw_payload FROM bronze_raw_ingestion"
            with engine.connect() as conn:
                df_base = pd.read_sql(query, conn)
            
            df_exploded = df_base.explode("raw_payload")
            df_norm = pd.json_normalize(df_exploded["raw_payload"])
            df_final = pd.concat([
                df_exploded[["variable_id"]].reset_index(drop=True),
                df_norm.reset_index(drop=True)
            ], axis=1)
            
            # Map d/v if present in JSON
            col_map = {c: 'date' if c.lower() in ['d', 'date', 'fecha'] else 'value' if c.lower() in ['v', 'value', 'valor'] else c for c in df_final.columns}
            df_final.rename(columns=col_map, inplace=True)
            
            df_final['date'] = pd.to_datetime(df_final['date'], errors='coerce')
            df_final['value'] = pd.to_numeric(df_final['value'], errors='coerce')
            df_final = df_final.dropna(subset=['date', 'value'])
            
            df_pivot = df_final.pivot_table(index='date', columns='variable_id', values='value', aggfunc='mean')
            df_pivot = df_pivot.sort_index()
            return df_pivot
        except:
            return pd.DataFrame()

# 3. Historical Events Management
def load_events():
    try:
        with engine.connect() as conn:
            df = pd.read_sql("SELECT id, date, event, description, category FROM historical_events ORDER BY date ASC", conn)
            df['date'] = pd.to_datetime(df['date']).dt.date
            return df
    except Exception as e:
        return pd.DataFrame(columns=['id', 'date', 'event', 'description', 'category'])

def save_event(date, event, description, category):
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO historical_events (date, event, description, category) VALUES (:f, :e, :d, :c)"),
            {"f": date, "e": event, "d": description, "c": category}
        )
        conn.commit()

def delete_event(event_id):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM historical_events WHERE id = :id"), {"id": event_id})
        conn.commit()

def update_event(event_id, date, event, description, category):
    with engine.connect() as conn:
        conn.execute(
            text("""
                UPDATE historical_events 
                SET date = :f, event = :e, description = :d, category = :c 
                WHERE id = :id
            """),
            {"f": date, "e": event, "d": description, "c": category, "id": event_id}
        )
        conn.commit()

# Initialize
df_pivot = load_macro_data()
df_events = load_events()

# --- SIDEBAR: EVENTS LOG ---
st.sidebar.title("📖 Historical Log")

default_date = st.session_state.get("selected_date", datetime.now().date())

with st.sidebar.expander("➕ Add Important Event", expanded=True if "selected_date" in st.session_state else False):
    with st.form("new_event", clear_on_submit=True):
        min_date = df_pivot.index.min().date() if not df_pivot.empty else datetime(1989, 1, 1).date()
        max_date = datetime(2030, 12, 31).date()
        
        e_date = st.date_input("Event Date", value=default_date, min_value=min_date, max_value=max_date)
        e_name = st.text_input("Event Name")
        e_desc = st.text_area("Description")
        e_cat = st.selectbox("Category", ["Politics", "External Shock", "Monetary", "Social", "Other"])
        if st.form_submit_button("Save"):
            if e_name:
                save_event(e_date, e_name, e_desc, e_cat)
                if "selected_date" in st.session_state:
                    del st.session_state["selected_date"]
                st.success("Event saved!")
                st.rerun()
            else:
                st.error("Event name is required.")

st.sidebar.markdown("---")
show_events = st.sidebar.toggle("Show Events in Chart", value=True)

st.sidebar.subheader("Registered Events")
if not df_events.empty:
    for _, row in df_events.iterrows():
        col1, col2, col3 = st.sidebar.columns([3, 1, 1])
        col1.info(f"**{row['date']}**: {row['event']}")
        
        with col2.popover("✏️"):
            with st.form(f"edit_{row['id']}"):
                u_date = st.date_input("Date", value=row['date'], key=f"u_f_{row['id']}")
                u_name = st.text_input("Name", value=row['event'], key=f"u_n_{row['id']}")
                u_desc = st.text_area("Description", value=row['description'], key=f"u_d_{row['id']}")
                u_cat = st.selectbox("Category", ["Politics", "External Shock", "Monetary", "Social", "Other"], 
                                     index=["Politics", "External Shock", "Monetary", "Social", "Other"].index(row['category']) if row['category'] in ["Politics", "External Shock", "Monetary", "Social", "Other"] else 0,
                                     key=f"u_c_{row['id']}")
                if st.form_submit_button("Update"):
                    update_event(row['id'], u_date, u_name, u_desc, u_cat)
                    st.success("Updated!")
                    st.rerun()

        with col3.popover("🗑️"):
            st.warning("Delete event?")
            if st.button("Confirm", key=f"del_{row['id']}"):
                delete_event(row['id'])
                st.rerun()
else:
    st.sidebar.write("No events registered yet.")

# --- MAIN: DASHBOARD ---
st.title("National Intelligence System (SINAC)")

if df_pivot.empty:
    st.warning("No data found in Silver layer. Please run the pipeline first.")
    st.info("Run: `python src/pipeline/00_bootstrap_sample.py && python src/main_pipeline.py`")
else:
    all_vars = df_pivot.columns.tolist()
    if "selected_vars" not in st.session_state:
        st.session_state["selected_vars"] = all_vars[:2]

    selected_vars = st.multiselect("Select Variables to Visualize", options=all_vars, default=st.session_state["selected_vars"])
    st.session_state["selected_vars"] = selected_vars

    col_ctrl1, col_ctrl2 = st.columns([1, 1])
    with col_ctrl1:
        scale_type = st.radio("Scale", ["Linear", "Logarithmic"], horizontal=True)
    with col_ctrl2:
        if st.button("Reset zoom / Clear date"):
            if "selected_date" in st.session_state:
                del st.session_state["selected_date"]
            st.rerun()

    if not selected_vars:
        st.info("Select at least one variable to see the chart.")
    else:
        fig = go.Figure()

        for var in selected_vars:
            fig.add_trace(go.Scatter(
                x=df_pivot.index, y=df_pivot[var],
                name=var, mode='lines+markers' if len(df_pivot) < 10 else 'lines',
                connectgaps=True,
                hovertemplate='<b>%{fullData.name}</b>: %{y:.2f}<extra></extra>'
            ))

        governments = [
            ("Menem", "1989-07-08", "1999-12-10", "lightblue"),
            ("De la Rúa", "1999-12-10", "2001-12-21", "pink"),
            ("Duhalde", "2002-01-02", "2003-05-25", "lightgray"),
            ("N. Kirchner", "2003-05-25", "2007-12-10", "lightgreen"),
            ("CFK I", "2007-12-10", "2011-12-10", "khaki"),
            ("CFK II", "2011-12-10", "2015-12-10", "navajowhite"),
            ("Macri", "2015-12-10", "2019-12-10", "yellow"),
            ("A. Fernández", "2019-12-10", "2023-12-10", "skyblue"),
            ("Milei", "2023-12-10", datetime.now().strftime('%Y-%m-%d'), "plum")
        ]
        for name, start, end, color in governments:
            if pd.to_datetime(start) < df_pivot.index.max() and pd.to_datetime(end) > df_pivot.index.min():
                fig.add_vrect(x0=start, x1=end, fillcolor=color, opacity=0.2, layer="below", line_width=0,
                              annotation_text=name, annotation_position="top left", annotation_textangle=-90)

        if show_events and not df_events.empty:
            for _, row in df_events.iterrows():
                fig.add_vline(x=row['date'], line_dash="dash", line_color="red", opacity=0.7)
                fig.add_annotation(
                    x=row['date'], y=1, yref="paper", 
                    text=row['event'], 
                    showarrow=False, 
                    textangle=-90, 
                    xshift=12, 
                    font=dict(color="red", size=14)
                )

        fig.update_layout(
            height=700,
            template="plotly_white",
            hovermode="x unified",
            uirevision="true", 
            xaxis=dict(title="Date", rangeslider=dict(visible=True), type="date"),
            yaxis=dict(title="Value", type="log" if scale_type == "Logarithmic" else "linear", autorange=True),
            clickmode='event+select'
        )

        evt = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode=["points"], key="main_chart")
        
        if evt and "selection" in evt and "points" in evt["selection"] and len(evt["selection"]["points"]) == 1:
            clicked_date = pd.to_datetime(evt["selection"]["points"][0]["x"]).date()
            if st.session_state.get("selected_date") != clicked_date:
                st.session_state["selected_date"] = clicked_date
                st.rerun()

st.markdown("---")
st.caption("SINAC Dashboard | Data Source: Standardized Medallion Pipeline")
