"""Startup Radar — Streamlit dashboard.

Five pages: Dashboard, Companies, Job Matches, Company DeepDive, Application Tracker.
Customize freely — this is your dashboard.

Run: `streamlit run app.py`
"""

import csv as _csv
import json
import re
import subprocess
import time
from datetime import datetime, timedelta
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

STATUS_OPTIONS = ["", "Interested", "Not Interested", "Applied", "Wishlist"]
ACTIVITY_TYPES = ["Emailed", "Applied", "Called", "Meeting", "Follow-up", "Interview", "Note"]
TRACKER_STATUS_OPTIONS = ["In Progress", "Applied", "Gone Cold"]
APPLIED_STATUS_OPTIONS = [
    "Applied", "Recruiter Screen", "Round 1 Interview", "Round 2 Interview",
    "Round 3 Interview", "Case Study", "Rejected",
]

TODAY = datetime.now().strftime("%Y-%m-%d")
PROJECT_DIR = Path(__file__).parent
REPORTS_DIR = PROJECT_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------


def load_data():
    return database.get_all_startups(), database.get_all_job_matches()


df_startups, df_jobs = load_data()

# ---------------------------------------------------------------------------
# Web lookup helper (DuckDuckGo)
# ---------------------------------------------------------------------------


def _lookup_company(name: str) -> dict:
    try:
        from duckduckgo_search import DDGS
        results = list(DDGS().text(f"{name} startup funding raised", max_results=5))
    except Exception:
        return {}
    if not results:
        return {}
    snippets = " ".join(r.get("body", "") for r in results)
    info = {}
    first_body = results[0].get("body", "")
    if first_body:
        info["description"] = first_body[:200].rstrip()
    amt = re.search(r"\$[\d,.]+\s*[BM]\b|\$[\d,.]+\s*(?:million|billion)", snippets, re.IGNORECASE)
    if amt:
        info["amount_raised"] = amt.group(0).strip()
    stage = re.search(r"Series\s+[A-F]\d?\+?|Pre-[Ss]eed|Seed", snippets)
    if stage:
        info["funding_stage"] = stage.group(0).strip()
    loc = re.search(r"(?:based in|headquartered in)\s+([^,.\n]+(?:,\s*[A-Za-z. ]+)?)", snippets, re.IGNORECASE)
    if loc:
        info["location"] = loc.group(1).strip()
    return info


# ---------------------------------------------------------------------------
# Connections helpers
# ---------------------------------------------------------------------------


def _get_connections_for_companies(company_names):
    result = {}
    for name in company_names:
        conns = database.search_connections_by_company(name)
        if not conns.empty:
            parts = []
            for _, c in conns.iterrows():
                full_name = f"{c['first_name']} {c['last_name']}".strip()
                pos = c.get("position", "")
                parts.append(f"{full_name} ({pos})" if pos else full_name)
            result[name] = ", ".join(parts)
        else:
            result[name] = ""
    return result


def _add_connections_col(frame, company_col="Company Name"):
    frame = frame.copy()
    if database.get_connections_count() == 0:
        frame["Connections"] = ""
        return frame
    conn_map = _get_connections_for_companies(frame[company_col].tolist())
    frame["Connections"] = frame[company_col].map(conn_map).fillna("")
    return frame


# ---------------------------------------------------------------------------
# DeepDive helpers
# ---------------------------------------------------------------------------


def _report_path(company_name: str) -> Path:
    safe = company_name.strip().replace(" ", "")
    return REPORTS_DIR / f"{safe}_Research_Brief.docx"


def _investors_path(company_name: str) -> Path:
    safe = company_name.strip().replace(" ", "")
    return REPORTS_DIR / f"{safe}_investors.json"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Companies", "Job Matches", "Company DeepDive", "Application Tracker"],
)

st.sidebar.divider()

# Pipeline run
if st.sidebar.button("Run pipeline now"):
    with st.spinner("Running..."):
        from main import run
        run()
    st.success("Done")
    st.rerun()

# LinkedIn upload
st.sidebar.markdown("**LinkedIn Connections**")
_li_last = database.get_connections_last_uploaded()
_li_count = database.get_connections_count()
if _li_last:
    try:
        _li_dt = datetime.fromisoformat(_li_last)
        _li_days_ago = (datetime.now() - _li_dt).days
        st.sidebar.caption(f"{_li_count} connections \u00b7 Updated {_li_dt.strftime('%b %d, %Y')}")
        if _li_days_ago > 30:
            st.sidebar.warning("Connections may be stale \u2014 consider re-exporting from LinkedIn")
    except Exception:
        st.sidebar.caption(f"{_li_count} connections")
else:
    st.sidebar.caption("Not yet uploaded")

_li_file = st.sidebar.file_uploader("Upload CSV", type="csv", key="li_csv_upload", label_visibility="collapsed")
if _li_file is not None:
    import io as _io
    _content = _li_file.getvalue().decode("utf-8", errors="replace")
    _lines = _content.splitlines()
    _data_start = 0
    for i, line in enumerate(_lines):
        if "First Name" in line and "Last Name" in line:
            _data_start = i
            break
    _reader = _csv.DictReader(_lines[_data_start:])
    _rows = [r for r in _reader if r.get("First Name") or r.get("Last Name")]
    _imported = database.import_connections(_rows)
    st.sidebar.success(f"Imported {_imported} connections")
    st.rerun()


# ---------------------------------------------------------------------------
# Shared table helpers
# ---------------------------------------------------------------------------


def _add_delete_col(frame):
    frame = frame.copy()
    frame["\U0001f5d1\ufe0f"] = False
    return frame


# ===================================================================
# PAGE: Dashboard
# ===================================================================

if page == "Dashboard":
    st.title("Startup Radar")
    user_name = cfg.get("user", {}).get("name", "")
    if user_name:
        st.caption(f"Welcome back, {user_name}")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Companies Tracked", len(df_startups))
    col2.metric("Job Matches", len(df_jobs))
    interested = len(df_startups[df_startups["Status"].str.lower() == "interested"])
    col3.metric("Interested", interested)
    wishlisted = len(df_startups[df_startups["Status"].str.lower() == "wishlist"])
    col4.metric("Wishlist", wishlisted)
    _tracker_statuses = database.get_all_tracker_statuses()
    applied_count = len([v for v in _tracker_statuses.values() if v["status"] == "Applied"])
    applied_count += len(df_startups[df_startups["Status"].str.lower() == "applied"])
    col5.metric("Applied", applied_count)

    _today_iso = datetime.now().strftime("%Y-%m-%d")
    _overdue = database.get_overdue_followups(_today_iso)
    if not _overdue.empty:
        st.divider()
        st.subheader(f"Follow-ups Due ({len(_overdue)})")
        for _, row in _overdue.iterrows():
            _is_overdue = row["follow_up_date"] < _today_iso
            _icon = "\U0001f534" if _is_overdue else "\U0001f7e1"
            _contact = f" \u2014 {row['contact_name']}" if row.get("contact_name") else ""
            _role = f" ({row['role_title']})" if row.get("role_title") else ""
            st.markdown(
                f"{_icon} **{row['company_name']}**{_role}{_contact}  \n"
                f"Due: {row['follow_up_date']} \u00b7 {row.get('notes', '')}"
            )

    st.divider()

    st.subheader("Today's Companies")
    todays_companies = df_startups[df_startups["Date Found"] == TODAY]
    if todays_companies.empty:
        _log_file = PROJECT_DIR / "logs" / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        _reason = "No new companies matched filters today."
        if _log_file.exists():
            _log_text = _log_file.read_text(encoding="utf-8", errors="replace")
            if "No new emails found" in _log_text:
                _reason = "No new funding newsletter emails received today."
            elif "all duplicates" in _log_text.lower():
                _reason = "Companies were found but all were already in the database."
        st.caption(_reason)
    else:
        for _, row in todays_companies.iterrows():
            c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
            _url = row.get("Website") or row.get("Source URL") or ""
            c1.markdown(f"**[{row['Company Name']}]({_url})**" if _url else f"**{row['Company Name']}**")
            desc = row["Description"]
            c2.write(desc[:80] + "..." if len(str(desc)) > 80 else desc)
            c3.write(row["Funding Stage"])
            c4.write(row["Amount Raised"])

    st.divider()

    st.subheader("Today's Job Matches")
    todays_jobs = df_jobs[df_jobs["Date Found"] == TODAY]
    if todays_jobs.empty:
        st.caption("No job matches found today.")
    else:
        for _, row in todays_jobs.iterrows():
            c1, c2, c3, c4 = st.columns([2, 3, 2, 1])
            c1.markdown(f"**{row.get('Company', '')}**")
            c2.write(row.get("Role", ""))
            c3.write(row.get("Location", ""))
            priority = row.get("Priority", "")
            if priority == "High":
                c4.markdown(":red[**High**]")
            elif priority == "Medium":
                c4.markdown(":orange[**Medium**]")
            else:
                c4.write(priority)


# ===================================================================
# PAGE: Companies
# ===================================================================

elif page == "Companies":
    st.title("Companies")

    if st.button("+ Add Company", key="add_company_btn"):
        st.session_state["show_add_company"] = not st.session_state.get("show_add_company", False)
        st.session_state.pop("co_lookup", None)
        st.session_state.pop("co_lookup_v", None)

    if st.session_state.get("show_add_company"):
        ac_name = st.text_input("Company Name *", key="ac_name_input")
        if st.button("Lookup", key="co_lookup_btn"):
            if ac_name.strip():
                with st.spinner(f"Looking up {ac_name.strip()}..."):
                    info = _lookup_company(ac_name.strip())
                if info:
                    st.session_state["co_lookup"] = info
                    st.session_state["co_lookup_v"] = st.session_state.get("co_lookup_v", 0) + 1
                    st.rerun()
                else:
                    st.warning("No results found. Fill in details manually.")
            else:
                st.error("Enter a company name first.")

        lookup = st.session_state.get("co_lookup", {})
        ver = st.session_state.get("co_lookup_v", 0)
        with st.form(f"add_company_form_{ver}"):
            ac_desc = st.text_input("Description", value=lookup.get("description", ""))
            ac_stage = st.text_input("Funding Stage", value=lookup.get("funding_stage", ""))
            ac_amount = st.text_input("Amount Raised", value=lookup.get("amount_raised", ""))
            ac_loc = st.text_input("Location", value=lookup.get("location", ""))
            ac_submit = st.form_submit_button("Add Company")
        if ac_submit:
            if not ac_name.strip():
                st.error("Company Name is required.")
            else:
                inserted = database.insert_startups([{
                    "company_name": ac_name.strip(),
                    "description": ac_desc.strip(),
                    "funding_stage": ac_stage.strip(),
                    "amount_raised": ac_amount.strip(),
                    "location": ac_loc.strip(),
                    "source": "Manual",
                    "date_found": TODAY,
                    "status": "",
                }])
                if inserted:
                    st.session_state["show_add_company"] = False
                    st.session_state.pop("co_lookup", None)
                    st.session_state.pop("co_lookup_v", None)
                    st.rerun()
                else:
                    st.warning(f"'{ac_name.strip()}' already exists.")

    search = st.text_input("Search", placeholder="Company name or keyword...", key="co_search")
    filtered = df_startups.copy()
    if search:
        mask = (
            filtered["Company Name"].str.contains(search, case=False, na=False)
            | filtered["Description"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    status_lower = filtered["Status"].str.strip().str.lower()
    wishlist = filtered[status_lower == "wishlist"]
    interested_co = filtered[status_lower == "interested"]
    not_interested = filtered[status_lower == "not interested"]
    uncategorized = filtered[~status_lower.isin(["applied", "wishlist", "interested", "not interested"])]

    _col_config = {
        "Website": st.column_config.LinkColumn("Website", display_text=r"https?://(?:www\.)?([^/]+)", width="small"),
        "Status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS, width="medium"),
        "Connections": st.column_config.TextColumn("Connections", width="medium"),
        "\U0001f5d1\ufe0f": st.column_config.CheckboxColumn("\U0001f5d1\ufe0f", width="small"),
    }

    def _persist_company_changes(original_df, edited_df):
        changed = False
        for idx in edited_df.index:
            if idx not in original_df.index:
                continue
            company = original_df.loc[idx, "Company Name"]
            if edited_df.loc[idx, "\U0001f5d1\ufe0f"]:
                database.delete_startup(company)
                changed = True
                continue
            old = original_df.loc[idx, "Status"]
            new = edited_df.loc[idx, "Status"]
            if old != new:
                database.update_startup_status(company, new)
                if new == "Applied":
                    ts = database.get_tracker_status(company)
                    if not ts:
                        database.upsert_tracker_status(company, "Applied", "", "")
                        database.insert_activity({
                            "company_name": company, "role_title": "",
                            "activity_type": "Applied", "contact_name": "",
                            "contact_title": "", "contact_email": "",
                            "date": TODAY, "follow_up_date": "", "notes": "",
                        })
                changed = True
        return changed

    _needs_rerun = False

    st.subheader(f"Wishlist ({len(wishlist)})")
    if wishlist.empty:
        st.caption("No wishlisted companies yet.")
    else:
        edited_wl = st.data_editor(
            _add_delete_col(_add_connections_col(wishlist)), column_config=_col_config,
            hide_index=True, use_container_width=True, disabled=[], key="wishlist_editor",
        )
        if _persist_company_changes(wishlist, edited_wl):
            _needs_rerun = True

    st.divider()

    st.subheader(f"Interested ({len(interested_co)})")
    if interested_co.empty:
        st.caption("No companies marked as interested yet.")
    else:
        edited_int = st.data_editor(
            _add_delete_col(_add_connections_col(interested_co)), column_config=_col_config,
            hide_index=True, use_container_width=True, disabled=[], key="interested_editor",
        )
        if _persist_company_changes(interested_co, edited_int):
            _needs_rerun = True

    st.divider()

    with st.expander(f"Not Interested ({len(not_interested)})"):
        if not_interested.empty:
            st.caption("No companies marked as not interested.")
        else:
            edited_ni = st.data_editor(
                _add_delete_col(not_interested), column_config=_col_config,
                hide_index=True, use_container_width=True, disabled=[], key="not_interested_editor",
            )
            if _persist_company_changes(not_interested, edited_ni):
                _needs_rerun = True

    st.divider()

    st.subheader(f"Uncategorized ({len(uncategorized)})")
    if uncategorized.empty:
        st.caption("All companies have been categorized.")
    else:
        edited_unc = st.data_editor(
            _add_delete_col(uncategorized), column_config=_col_config,
            hide_index=True, use_container_width=True, disabled=[], key="uncategorized_editor",
        )
        if _persist_company_changes(uncategorized, edited_unc):
            _needs_rerun = True

    if _needs_rerun:
        st.rerun()


# ===================================================================
# PAGE: Job Matches
# ===================================================================

elif page == "Job Matches":
    st.title("Job Matches")

    if st.button("+ Add Role", key="add_role_btn"):
        st.session_state["show_add_role"] = not st.session_state.get("show_add_role", False)

    if st.session_state.get("show_add_role"):
        company_options = ["-- New company --"] + df_startups["Company Name"].tolist()
        with st.form("add_role_form"):
            ar_company = st.selectbox("Company", company_options)
            ar_new_company = st.text_input("New Company Name (if above is '-- New company --')")
            ar_role = st.text_input("Role Title *")
            ar_desc = st.text_input("Company Description")
            ar_loc = st.text_input("Location")
            ar_url = st.text_input("URL")
            ar_priority = st.selectbox("Priority", ["", "High", "Medium", "Low"])
            ar_submit = st.form_submit_button("Add Role")
        if ar_submit:
            company_name = ar_new_company.strip() if ar_company == "-- New company --" else ar_company
            if not company_name:
                st.error("Company is required.")
            elif not ar_role.strip():
                st.error("Role Title is required.")
            else:
                inserted = database.insert_job_matches([{
                    "company_name": company_name,
                    "company_description": ar_desc.strip(),
                    "role_title": ar_role.strip(),
                    "location": ar_loc.strip(),
                    "url": ar_url.strip(),
                    "priority": ar_priority,
                    "status": "",
                    "date_found": TODAY,
                }])
                if inserted:
                    st.session_state["show_add_role"] = False
                    st.rerun()
                else:
                    st.warning(f"Role '{ar_role.strip()}' at '{company_name}' already exists.")

    job_search = st.text_input("Search", placeholder="Company name or role...", key="job_search")
    filtered_jobs = df_jobs.copy()
    if job_search:
        mask = (
            filtered_jobs["Role"].str.contains(job_search, case=False, na=False)
            | filtered_jobs["Company"].str.contains(job_search, case=False, na=False)
        )
        filtered_jobs = filtered_jobs[mask]

    job_status_lower = filtered_jobs["Status"].str.strip().str.lower()
    wishlist_jobs = filtered_jobs[job_status_lower == "wishlist"]
    interested_jobs = filtered_jobs[job_status_lower == "interested"]
    ni_jobs = filtered_jobs[job_status_lower == "not interested"]
    uncategorized_jobs = filtered_jobs[~job_status_lower.isin(["applied", "wishlist", "interested", "not interested"])]

    display_cols = [c for c in filtered_jobs.columns if c != "Priority"]

    def _add_job_connections_col(frame):
        frame = frame.copy()
        if database.get_connections_count() == 0:
            frame["Connections"] = ""
            return frame
        conn_map = _get_connections_for_companies(frame["Company"].tolist())
        frame["Connections"] = frame["Company"].map(conn_map).fillna("")
        return frame

    _job_col_config = {
        "Status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS, width="medium"),
        "Link": st.column_config.LinkColumn("Link", display_text="Apply"),
        "Connections": st.column_config.TextColumn("Connections", width="medium"),
        "\U0001f5d1\ufe0f": st.column_config.CheckboxColumn("\U0001f5d1\ufe0f", width="small"),
    }

    def _persist_job_changes(original_df, edited_df):
        changed = False
        for idx in edited_df.index:
            if idx not in original_df.index:
                continue
            if edited_df.loc[idx, "\U0001f5d1\ufe0f"]:
                database.delete_job_match(original_df.loc[idx, "Company"], original_df.loc[idx, "Role"])
                changed = True
                continue
            old = original_df.loc[idx, "Status"]
            new = edited_df.loc[idx, "Status"]
            if old != new:
                company = original_df.loc[idx, "Company"]
                role = original_df.loc[idx, "Role"]
                database.update_job_status(company, role, new)
                if new == "Applied":
                    ts = database.get_tracker_status(company)
                    if not ts:
                        database.upsert_tracker_status(company, "Applied", role, "")
                        database.insert_activity({
                            "company_name": company, "role_title": role,
                            "activity_type": "Applied", "contact_name": "",
                            "contact_title": "", "contact_email": "",
                            "date": TODAY, "follow_up_date": "", "notes": "",
                        })
                changed = True
        return changed

    _jobs_needs_rerun = False

    st.subheader(f"Wishlist ({len(wishlist_jobs)})")
    if wishlist_jobs.empty:
        st.caption("No wishlisted jobs yet.")
    else:
        edited = st.data_editor(
            _add_delete_col(_add_job_connections_col(wishlist_jobs[display_cols])),
            column_config=_job_col_config, hide_index=True, use_container_width=True,
            disabled=[], key="wl_jobs_editor",
        )
        if _persist_job_changes(wishlist_jobs, edited):
            _jobs_needs_rerun = True

    st.divider()

    st.subheader(f"Interested ({len(interested_jobs)})")
    if interested_jobs.empty:
        st.caption("No jobs marked as interested yet.")
    else:
        edited = st.data_editor(
            _add_delete_col(_add_job_connections_col(interested_jobs[display_cols])),
            column_config=_job_col_config, hide_index=True, use_container_width=True,
            disabled=[], key="int_jobs_editor",
        )
        if _persist_job_changes(interested_jobs, edited):
            _jobs_needs_rerun = True

    st.divider()

    with st.expander(f"Not Interested ({len(ni_jobs)})"):
        if ni_jobs.empty:
            st.caption("No jobs marked as not interested.")
        else:
            edited = st.data_editor(
                _add_delete_col(ni_jobs[display_cols]),
                column_config=_job_col_config, hide_index=True, use_container_width=True,
                disabled=[], key="ni_jobs_editor",
            )
            if _persist_job_changes(ni_jobs, edited):
                _jobs_needs_rerun = True

    st.divider()

    st.subheader(f"Uncategorized ({len(uncategorized_jobs)})")
    if uncategorized_jobs.empty:
        st.caption("All jobs have been categorized.")
    else:
        edited = st.data_editor(
            _add_delete_col(_add_job_connections_col(uncategorized_jobs[display_cols])),
            column_config=_job_col_config, hide_index=True, use_container_width=True,
            disabled=[], key="unc_jobs_editor",
        )
        if _persist_job_changes(uncategorized_jobs, edited):
            _jobs_needs_rerun = True

    if _jobs_needs_rerun:
        st.rerun()


# ===================================================================
# PAGE: Company DeepDive
# ===================================================================

elif page == "Company DeepDive":
    st.title("Company DeepDive")
    st.caption("Generate a one-page research brief for any company")

    if st.button("+ Add Company", key="add_company_dd_btn"):
        st.session_state["show_add_company_dd"] = not st.session_state.get("show_add_company_dd", False)
        st.session_state.pop("dd_lookup", None)
        st.session_state.pop("dd_lookup_v", None)

    if st.session_state.get("show_add_company_dd"):
        dd_name = st.text_input("Company Name *", key="dd_name_input")
        if st.button("Lookup", key="dd_lookup_btn"):
            if dd_name.strip():
                with st.spinner(f"Looking up {dd_name.strip()}..."):
                    info = _lookup_company(dd_name.strip())
                if info:
                    st.session_state["dd_lookup"] = info
                    st.session_state["dd_lookup_v"] = st.session_state.get("dd_lookup_v", 0) + 1
                    st.rerun()
                else:
                    st.warning("No results found. Fill in details manually.")
            else:
                st.error("Enter a company name first.")

        lookup = st.session_state.get("dd_lookup", {})
        ver = st.session_state.get("dd_lookup_v", 0)
        with st.form(f"add_company_dd_form_{ver}"):
            dd_desc = st.text_input("Description", value=lookup.get("description", ""))
            dd_stage = st.text_input("Funding Stage", value=lookup.get("funding_stage", ""))
            dd_amount = st.text_input("Amount Raised", value=lookup.get("amount_raised", ""))
            dd_loc = st.text_input("Location", value=lookup.get("location", ""))
            dd_submit = st.form_submit_button("Add Company")
        if dd_submit:
            if not dd_name.strip():
                st.error("Company Name is required.")
            else:
                inserted = database.insert_startups([{
                    "company_name": dd_name.strip(),
                    "description": dd_desc.strip(),
                    "funding_stage": dd_stage.strip(),
                    "amount_raised": dd_amount.strip(),
                    "location": dd_loc.strip(),
                    "source": "Manual",
                    "date_found": TODAY,
                    "status": "",
                }])
                if inserted:
                    st.session_state["show_add_company_dd"] = False
                    st.session_state.pop("dd_lookup", None)
                    st.session_state.pop("dd_lookup_v", None)
                    st.rerun()
                else:
                    st.warning(f"'{dd_name.strip()}' already exists.")

    company_names = df_startups["Company Name"].tolist()
    selected = st.selectbox("Select a company", [""] + company_names, key="deepdive_select")

    if selected:
        report = _report_path(selected)
        btn_col1, btn_col2 = st.columns(2)

        with btn_col1:
            if report.exists():
                col_a, col_b = st.columns([1, 2])
                col_a.success("Report ready")
                with open(report, "rb") as f:
                    col_b.download_button(
                        label="Download Research Brief",
                        data=f, file_name=report.name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
            elif st.session_state.get("generating") == selected:
                proc = st.session_state.get("gen_proc")
                start = st.session_state.get("gen_start", time.time())
                if report.exists():
                    st.session_state.pop("generating", None)
                    st.session_state.pop("gen_proc", None)
                    st.session_state.pop("gen_start", None)
                    st.success(f"Report for {selected} is ready.")
                    st.rerun()
                elif proc is not None and proc.poll() is not None:
                    st.session_state.pop("generating", None)
                    st.session_state.pop("gen_proc", None)
                    st.session_state.pop("gen_start", None)
                    if report.exists():
                        st.success("Report ready!")
                        st.rerun()
                    else:
                        st.error("Report generation failed. Check logs.")
                else:
                    elapsed = int(time.time() - start)
                    pct = min(elapsed / 60.0, 0.95)
                    stages = [
                        (0.0, "Starting research..."), (0.1, "Searching for company info..."),
                        (0.25, "Gathering funding data..."), (0.45, "Analyzing competitors..."),
                        (0.65, "Scoring company fit..."), (0.8, "Generating report..."),
                    ]
                    label = stages[0][1]
                    for threshold, stage_label in stages:
                        if pct >= threshold:
                            label = stage_label
                    st.progress(pct, text=label)
                    st.caption(f"Elapsed: {elapsed // 60}m {elapsed % 60}s")
                    time.sleep(3)
                    st.rerun()
            else:
                if st.button("Generate DeepDive Report", key="deepdive_btn"):
                    proc = subprocess.Popen(
                        [sys.executable or "python", "deepdive.py", selected],
                        cwd=str(PROJECT_DIR),
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    )
                    st.session_state["generating"] = selected
                    st.session_state["gen_proc"] = proc
                    st.session_state["gen_start"] = time.time()
                    st.rerun()

        with btn_col2:
            if st.button("Find Warm Intros", key="warm_intros_btn"):
                st.session_state["show_warm_intros"] = selected
            elif st.session_state.get("show_warm_intros") != selected:
                st.session_state.pop("show_warm_intros", None)

        if st.session_state.get("show_warm_intros") == selected:
            if database.get_connections_count() == 0:
                st.warning("No LinkedIn connections uploaded. Use the sidebar to upload your connections CSV.")
            else:
                with st.spinner(f"Searching connections for intros to {selected}..."):
                    tier1 = database.search_connections_by_company(selected)

                    investor_names = []
                    inv_path = _investors_path(selected)
                    if inv_path.exists():
                        try:
                            investor_names = json.loads(inv_path.read_text())
                        except Exception:
                            pass
                    elif report.exists():
                        try:
                            from docx import Document as DocxDocument
                            doc = DocxDocument(str(report))
                            full_text = "\n".join(p.text for p in doc.paragraphs)
                            for m in re.finditer(r"(?:led by|investors?\s+include|backed by)\s+([^.]+)",
                                                 full_text, re.IGNORECASE):
                                for inv in re.split(r",\s*|\s+and\s+", m.group(1)):
                                    inv = inv.strip().rstrip(".")
                                    if inv and 2 < len(inv) < 50 and inv not in investor_names:
                                        investor_names.append(inv)
                        except Exception:
                            pass

                    tier2 = database.search_connections_by_companies(investor_names) if investor_names else pd.DataFrame()
                    if not tier2.empty and not tier1.empty:
                        tier2 = tier2[~tier2["url"].isin(tier1["url"])]

                    hidden = database.get_hidden_intros(selected)
                    intro_rows = []
                    for df_tier, tier_label in [(tier1, "Direct"), (tier2, "Investor")]:
                        if df_tier.empty:
                            continue
                        for _, c in df_tier.iterrows():
                            url = c.get("url", "") or ""
                            if url in hidden:
                                continue
                            name = f"{c['first_name']} {c['last_name']}".strip()
                            intro_rows.append({
                                "Tier": tier_label,
                                "Name": name,
                                "Position": c.get("position", ""),
                                "Company": c.get("company", ""),
                                "LinkedIn": url,
                                "Action": "",
                            })

                st.divider()
                if not intro_rows:
                    if not investor_names:
                        st.info(f"No direct connections at {selected}. Generate a DeepDive report to unlock investor-based intros.")
                    else:
                        st.info(f"No connections found related to {selected}.")
                else:
                    st.markdown(f"**{len(intro_rows)} connection(s) found**")
                    _intro_df = pd.DataFrame(intro_rows)
                    edited_intros = st.data_editor(
                        _intro_df,
                        column_config={
                            "LinkedIn": st.column_config.LinkColumn("LinkedIn", display_text="Profile", width="small"),
                            "Action": st.column_config.SelectboxColumn("Action", options=["", "Save to Tracker", "Hide"], width="small"),
                        },
                        hide_index=True, use_container_width=True, key="warm_intros_editor",
                    )
                    _intros_changed = False
                    for idx in edited_intros.index:
                        action = edited_intros.loc[idx, "Action"]
                        if not action:
                            continue
                        row = _intro_df.loc[idx]
                        if action == "Hide":
                            database.hide_intro(row["LinkedIn"], selected)
                            _intros_changed = True
                        elif action == "Save to Tracker":
                            database.insert_activity({
                                "company_name": selected, "role_title": "",
                                "activity_type": "Note",
                                "contact_name": row["Name"],
                                "contact_title": f"{row['Position']} at {row['Company']}",
                                "contact_email": "", "date": TODAY,
                                "follow_up_date": "",
                                "notes": f"Warm intro lead ({row['Tier']})",
                            })
                            _intros_changed = True
                    if _intros_changed:
                        st.rerun()

    st.divider()
    st.subheader("Past Reports")
    existing_reports = sorted(REPORTS_DIR.glob("*_Research_Brief.docx"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not existing_reports:
        st.caption("No reports generated yet. Select a company above to create one.")
    else:
        for rpt in existing_reports:
            display_name = rpt.stem.replace("_Research_Brief", "")
            generated = datetime.fromtimestamp(rpt.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.markdown(f"**{display_name}**")
            col2.caption(f"Generated: {generated}")
            with open(rpt, "rb") as f:
                col3.download_button(label="Download", data=f, file_name=rpt.name,
                                     mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                     key=f"dl_{rpt.stem}")


# ===================================================================
# PAGE: Application Tracker
# ===================================================================

elif page == "Application Tracker":
    st.title("Application Tracker")

    if st.button("+ Log Activity", key="add_activity_btn"):
        st.session_state["show_add_activity"] = not st.session_state.get("show_add_activity", False)

    if st.session_state.get("show_add_activity"):
        company_opts = [""] + df_startups["Company Name"].tolist()
        with st.form("add_activity_form"):
            act_company = st.selectbox("Company *", company_opts)
            act_role = st.text_input("Role Title (optional)")
            act_type = st.selectbox("Activity Type *", ACTIVITY_TYPES)
            act_contact = st.text_input("Contact Name")
            act_title = st.text_input("Contact Title")
            act_email = st.text_input("Contact Email")
            act_date = st.date_input("Date *", value=datetime.now())
            act_followup = st.date_input("Follow-up Date (optional)", value=None)
            act_notes = st.text_area("Notes")
            act_submit = st.form_submit_button("Log Activity")
        if act_submit:
            if not act_company:
                st.error("Company is required.")
            else:
                database.insert_activity({
                    "company_name": act_company,
                    "role_title": act_role.strip(),
                    "activity_type": act_type,
                    "contact_name": act_contact.strip(),
                    "contact_title": act_title.strip(),
                    "contact_email": act_email.strip(),
                    "date": act_date.strftime("%Y-%m-%d"),
                    "follow_up_date": act_followup.strftime("%Y-%m-%d") if act_followup else "",
                    "notes": act_notes.strip(),
                })
                st.session_state["show_add_activity"] = False
                st.rerun()

    # Reminders
    _reminders = []
    _overdue_tracker = database.get_overdue_followups(TODAY)
    for _, row in _overdue_tracker.iterrows():
        _is_overdue = row["follow_up_date"] < TODAY
        _contact = f" \u2014 {row['contact_name']}" if row.get("contact_name") else ""
        _role = f" \u00b7 {row['role_title']}" if row.get("role_title") else ""
        _reminders.append({
            "icon": "\U0001f534" if _is_overdue else "\U0001f7e1",
            "text": f"**{row['company_name']}**{_role}{_contact}",
            "detail": f"Scheduled follow-up due: {row['follow_up_date']} \u00b7 {row.get('notes', '')}",
        })

    _all_acts = database.get_activities()
    if not _all_acts.empty:
        _email_acts = _all_acts[_all_acts["activity_type"] == "Emailed"]
        if not _email_acts.empty:
            _today_dt = datetime.now()
            _seen_keys = set()
            for _, act in _email_acts.iterrows():
                key = f"{act['company_name']}|{act['contact_name']}"
                if key in _seen_keys:
                    continue
                _seen_keys.add(key)
                try:
                    start = datetime.strptime(act["date"], "%Y-%m-%d")
                except Exception:
                    continue
                bdays = 0
                current = start + timedelta(days=1)
                while current <= _today_dt:
                    if current.weekday() < 5:
                        bdays += 1
                    current += timedelta(days=1)
                if bdays >= 3:
                    _contact = f" \u2014 {act['contact_name']}" if act.get("contact_name") else ""
                    icon = "\U0001f534" if bdays >= 5 else "\U0001f7e1"
                    urgency = f"{bdays} business days since last email"
                    _has_scheduled = any(act["company_name"] in r.get("text", "") for r in _reminders)
                    if not _has_scheduled:
                        _reminders.append({
                            "icon": icon,
                            "text": f"**{act['company_name']}**{_contact}",
                            "detail": f"Last emailed: {act['date']} \u2014 {urgency}",
                        })

    if _reminders:
        st.subheader(f"Reminders ({len(_reminders)})")
        for r in _reminders:
            st.markdown(f"{r['icon']} {r['text']}  \n{r['detail']}")
        st.divider()

    tracker_summary = database.get_tracker_summary()
    _activity_log_statuses = ["In Progress", "Gone Cold"]
    _applied_tracker = tracker_summary[~tracker_summary["Status"].isin(_activity_log_statuses + ["Rejected"])].copy() if not tracker_summary.empty else pd.DataFrame()
    _active_tracker = tracker_summary[tracker_summary["Status"].isin(_activity_log_statuses)].copy() if not tracker_summary.empty else pd.DataFrame()
    _rejected_tracker = tracker_summary[tracker_summary["Status"] == "Rejected"].copy() if not tracker_summary.empty else pd.DataFrame()

    # Applied
    st.divider()
    st.subheader("Applied")

    if st.button("+ Add Application", key="add_applied_btn"):
        st.session_state["show_add_applied"] = not st.session_state.get("show_add_applied", False)

    if st.session_state.get("show_add_applied"):
        with st.form("add_applied_form"):
            ap_company = st.selectbox("Company *", [""] + df_startups["Company Name"].tolist(), key="ap_company")
            ap_new = st.text_input("Or enter new company name")
            ap_role = st.text_input("Role Title *", key="ap_role")
            ap_status = st.selectbox("Status", APPLIED_STATUS_OPTIONS, key="ap_status")
            ap_contact = st.text_input("Contact Name", key="ap_contact")
            ap_contact_title = st.text_input("Contact Title", key="ap_contact_title")
            ap_date = st.date_input("Date Applied *", value=datetime.now(), key="ap_date")
            ap_notes = st.text_area("Notes", key="ap_notes")
            ap_submit = st.form_submit_button("Add Application")
        if ap_submit:
            company_name = ap_new.strip() if ap_new.strip() else ap_company
            if not company_name:
                st.error("Company is required.")
            elif not ap_role.strip():
                st.error("Role Title is required.")
            else:
                database.insert_activity({
                    "company_name": company_name, "role_title": ap_role.strip(),
                    "activity_type": "Applied", "contact_name": ap_contact.strip(),
                    "contact_title": ap_contact_title.strip(), "contact_email": "",
                    "date": ap_date.strftime("%Y-%m-%d"), "follow_up_date": "",
                    "notes": ap_notes.strip(),
                })
                database.upsert_tracker_status(company_name, ap_status, ap_role.strip(), ap_notes.strip())
                existing_keys = database.get_existing_job_keys()
                key = f"{company_name.lower().strip()}|{ap_role.strip().lower()}"
                if key not in existing_keys:
                    database.insert_job_matches([{
                        "company_name": company_name, "company_description": "",
                        "role_title": ap_role.strip(), "location": "", "url": "",
                        "priority": "", "status": ap_status,
                        "date_found": ap_date.strftime("%Y-%m-%d"),
                    }])
                database.update_job_status(company_name, ap_role.strip(), ap_status)
                st.session_state["show_add_applied"] = False
                st.rerun()

    _applied_col_config = {
        "Status": st.column_config.SelectboxColumn("Status", options=APPLIED_STATUS_OPTIONS, width="small"),
        "Notes": st.column_config.TextColumn("Notes", width="large"),
        "\U0001f5d1\ufe0f": st.column_config.CheckboxColumn("\U0001f5d1\ufe0f", width="small"),
    }

    def _persist_tracker(original_df, edited_df):
        changed = False
        for idx in edited_df.index:
            if idx not in original_df.index:
                continue
            company = original_df.loc[idx, "Company"]
            if edited_df.loc[idx, "\U0001f5d1\ufe0f"]:
                database.delete_tracker_entry(company)
                changed = True
                continue
            old_s = original_df.loc[idx, "Status"]
            new_s = edited_df.loc[idx, "Status"] or ""
            new_r = edited_df.loc[idx, "Role"] or ""
            new_n = edited_df.loc[idx, "Notes"] or ""
            if old_s != new_s or (original_df.loc[idx, "Role"] or "") != new_r or (original_df.loc[idx, "Notes"] or "") != new_n:
                database.upsert_tracker_status(company, new_s, new_r, new_n)
                changed = True
        return changed

    if _applied_tracker.empty:
        st.caption("No applications yet.")
    else:
        _applied_display = _applied_tracker.copy()
        _applied_display["\U0001f5d1\ufe0f"] = False
        edited = st.data_editor(
            _applied_display, column_config=_applied_col_config,
            hide_index=True, use_container_width=True, disabled=[], key="tracker_applied_editor",
        )
        if _persist_tracker(_applied_tracker, edited):
            st.rerun()

    # Activity Log
    st.divider()
    st.subheader("Activity Log")

    if st.button("+ Add Entry", key="add_activity_log_btn"):
        st.session_state["show_add_activity_log"] = not st.session_state.get("show_add_activity_log", False)

    if st.session_state.get("show_add_activity_log"):
        with st.form("add_activity_log_form"):
            al_company = st.selectbox("Company *", [""] + df_startups["Company Name"].tolist(), key="al_company")
            al_new = st.text_input("Or enter new company name", key="al_new")
            al_role = st.text_input("Role Title", key="al_role")
            al_type = st.selectbox("Activity Type *", ACTIVITY_TYPES, key="al_type")
            al_contact = st.text_input("Contact Name", key="al_contact")
            al_contact_title = st.text_input("Contact Title", key="al_contact_title")
            al_email = st.text_input("Contact Email", key="al_email")
            al_date = st.date_input("Date *", value=datetime.now(), key="al_date")
            al_followup = st.date_input("Follow-up Date (optional)", value=None, key="al_followup")
            al_notes = st.text_area("Notes", key="al_notes")
            al_submit = st.form_submit_button("Add Entry")
        if al_submit:
            company_name = al_new.strip() if al_new.strip() else al_company
            if not company_name:
                st.error("Company is required.")
            else:
                database.insert_activity({
                    "company_name": company_name, "role_title": al_role.strip(),
                    "activity_type": al_type, "contact_name": al_contact.strip(),
                    "contact_title": al_contact_title.strip(), "contact_email": al_email.strip(),
                    "date": al_date.strftime("%Y-%m-%d"),
                    "follow_up_date": al_followup.strftime("%Y-%m-%d") if al_followup else "",
                    "notes": al_notes.strip(),
                })
                ts = database.get_tracker_status(company_name)
                if not ts:
                    database.upsert_tracker_status(company_name, "In Progress", al_role.strip(), "")
                st.session_state["show_add_activity_log"] = False
                st.rerun()

    if _active_tracker.empty:
        st.caption("No activities logged yet. Click '+ Add Entry' to start tracking.")
    else:
        _tracker_col_config = {
            "Status": st.column_config.SelectboxColumn("Status", options=TRACKER_STATUS_OPTIONS, width="small"),
            "Notes": st.column_config.TextColumn("Notes", width="large"),
            "\U0001f5d1\ufe0f": st.column_config.CheckboxColumn("\U0001f5d1\ufe0f", width="small"),
        }
        st.caption(f"{len(_active_tracker)} active application(s)")
        _active_display = _active_tracker.copy()
        _active_display["\U0001f5d1\ufe0f"] = False
        edited = st.data_editor(
            _active_display, column_config=_tracker_col_config,
            hide_index=True, use_container_width=True, disabled=[], key="tracker_active_editor",
        )
        if _persist_tracker(_active_tracker, edited):
            st.rerun()

    # Rejected
    st.divider()
    _total_rejected = len(_rejected_tracker)
    with st.expander(f"Rejected ({_total_rejected})"):
        if _total_rejected == 0:
            st.caption("No rejected entries.")
        else:
            _rej_display = _rejected_tracker.copy()
            _rej_display["\U0001f5d1\ufe0f"] = False
            edited = st.data_editor(
                _rej_display,
                column_config={
                    "Status": st.column_config.SelectboxColumn("Status", options=TRACKER_STATUS_OPTIONS, width="small"),
                    "\U0001f5d1\ufe0f": st.column_config.CheckboxColumn("\U0001f5d1\ufe0f", width="small"),
                },
                hide_index=True, use_container_width=True, disabled=[], key="rejected_tracker_editor",
            )
            if _persist_tracker(_rejected_tracker, edited):
                st.rerun()


# Missing import for subprocess in DeepDive
import sys
