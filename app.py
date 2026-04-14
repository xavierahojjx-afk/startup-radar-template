"""Startup Radar — Streamlit dashboard.

Browse startups and jobs from the SQLite store, mark status, upload
LinkedIn connections, and find warm intros.

Run: `streamlit run app.py`

Customize: this is your dashboard — edit freely. The layout is kept simple
so you can rearrange sections, add new tabs, or drop features you don't use.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import database
from config_loader import load_config

st.set_page_config(page_title="Startup Radar", page_icon=":satellite:", layout="wide")

try:
    cfg = load_config()
    sqlite_path = cfg.get("output", {}).get("sqlite", {}).get("path")
    if sqlite_path:
        database.set_db_path(sqlite_path)
except Exception as e:
    st.error(f"Config error: {e}")
    st.stop()

database.init_db()

st.title("Startup Radar")
st.caption(f"Welcome back, {cfg['user'].get('name', 'friend')}")

# ---------------- Sidebar ----------------

with st.sidebar:
    st.header("Actions")

    if st.button("Run pipeline now"):
        with st.spinner("Running..."):
            from main import run
            run()
        st.success("Done")
        st.rerun()

    st.markdown("---")
    st.subheader("LinkedIn connections")

    count = database.get_connections_count()
    last = database.get_connections_last_uploaded()
    if count:
        st.caption(f"{count} connections")
        if last:
            try:
                dt = datetime.fromisoformat(last)
                st.caption(f"Uploaded {dt.strftime('%b %d, %Y')}")
            except Exception:
                pass

    uploaded = st.file_uploader("Upload Connections.csv", type="csv")
    if uploaded is not None:
        import csv
        content = uploaded.read().decode("utf-8", errors="replace").splitlines()
        header_idx = 0
        for i, line in enumerate(content):
            if "First Name" in line and "Last Name" in line:
                header_idx = i
                break
        reader = csv.DictReader(content[header_idx:])
        rows = [r for r in reader if r.get("First Name") or r.get("Last Name")]
        imported = database.import_connections(rows)
        st.success(f"Imported {imported} connections")
        st.rerun()


# ---------------- Tabs ----------------

tab_startups, tab_jobs, tab_intros = st.tabs(["Startups", "Jobs", "Warm intros"])


def _add_connections_col(df: pd.DataFrame, company_col: str = "company_name") -> pd.DataFrame:
    if df.empty or database.get_connections_count() == 0:
        df["connections"] = ""
        return df
    conn_map = {}
    for name in df[company_col].unique():
        hits = database.search_connections_by_company(name)
        if not hits.empty:
            names = [f"{r['first_name']} {r['last_name']}".strip()
                     for _, r in hits.iterrows()]
            conn_map[name] = ", ".join(names[:3]) + ("..." if len(names) > 3 else "")
    df["connections"] = df[company_col].map(conn_map).fillna("")
    return df


with tab_startups:
    df = database.get_all_startups()
    st.caption(f"{len(df)} total")

    if not df.empty:
        status_filter = st.multiselect(
            "Filter by status",
            options=sorted(df["status"].fillna("").unique().tolist()),
            default=[],
        )
        if status_filter:
            df = df[df["status"].isin(status_filter)]

        df = _add_connections_col(df)

        display_cols = ["company_name", "funding_stage", "amount_raised",
                        "location", "source", "date_found", "status", "connections"]
        available = [c for c in display_cols if c in df.columns]
        edited = st.data_editor(
            df[available],
            hide_index=True,
            column_config={
                "status": st.column_config.SelectboxColumn(
                    "status",
                    options=["", "Interested", "Not Interested", "Applied", "Wishlist"],
                ),
            },
            disabled=[c for c in available if c != "status"],
            use_container_width=True,
            key="startups_editor",
        )
        if st.button("Save status changes"):
            original = df.set_index("company_name")["status"]
            changed = edited.set_index("company_name")["status"]
            for name in changed.index:
                if str(original.get(name, "")) != str(changed[name]):
                    row_id = int(df[df["company_name"] == name]["id"].iloc[0])
                    database.update_status("startups", row_id, changed[name])
            st.success("Saved")
            st.rerun()
    else:
        st.info("No startups yet. Run the pipeline from the sidebar.")


with tab_jobs:
    df = database.get_all_jobs()
    st.caption(f"{len(df)} total")
    if not df.empty:
        df = _add_connections_col(df)
        display_cols = ["company_name", "role_title", "location", "priority",
                        "url", "source", "date_found", "status", "connections"]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available], hide_index=True, use_container_width=True)
    else:
        st.info("No jobs yet.")


with tab_intros:
    st.subheader("Find a warm intro")
    company = st.text_input("Company name")
    if company:
        st.markdown("**Tier 1 — Direct connections at the company**")
        t1 = database.search_connections_by_company(company)
        if t1.empty:
            st.caption("No direct connections found.")
        else:
            st.dataframe(t1, hide_index=True, use_container_width=True)

        st.markdown("**Tier 2 — Connections at investors**")
        st.caption(
            "Generate a DeepDive report for this company first to unlock "
            "investor-based intros (run `claude` and invoke /deepdive)."
        )
