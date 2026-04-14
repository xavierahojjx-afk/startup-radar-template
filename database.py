"""SQLite database — generic startup + job + connections store."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from models import Startup, JobMatch

DB_PATH = Path(__file__).parent / "startup_radar.db"


def set_db_path(path: str) -> None:
    global DB_PATH
    DB_PATH = Path(path)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS startups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                description TEXT DEFAULT '',
                funding_stage TEXT DEFAULT '',
                amount_raised TEXT DEFAULT '',
                location TEXT DEFAULT '',
                website TEXT DEFAULT '',
                source TEXT DEFAULT '',
                source_url TEXT DEFAULT '',
                date_found TEXT,
                status TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_startups_name
                ON startups(company_name COLLATE NOCASE);

            CREATE TABLE IF NOT EXISTS job_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                company_description TEXT DEFAULT '',
                role_title TEXT DEFAULT '',
                location TEXT DEFAULT '',
                url TEXT DEFAULT '',
                priority TEXT DEFAULT 'Medium',
                source TEXT DEFAULT '',
                status TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                date_found TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_company_role
                ON job_matches(company_name COLLATE NOCASE, role_title COLLATE NOCASE);

            CREATE TABLE IF NOT EXISTS connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT DEFAULT '',
                last_name TEXT DEFAULT '',
                url TEXT DEFAULT '',
                email TEXT DEFAULT '',
                company TEXT DEFAULT '',
                position TEXT DEFAULT '',
                connected_on TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_connections_company
                ON connections(company COLLATE NOCASE);

            CREATE TABLE IF NOT EXISTS connections_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_uploaded TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS hidden_intros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connection_url TEXT NOT NULL,
                company_name TEXT NOT NULL,
                UNIQUE(connection_url, company_name)
            );

            CREATE TABLE IF NOT EXISTS processed_items (
                source TEXT NOT NULL,
                item_id TEXT NOT NULL,
                processed_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (source, item_id)
            );
        """)
        conn.commit()
    finally:
        conn.close()


# ---------- dedup helpers ----------

def get_existing_companies() -> set[str]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT company_name FROM startups").fetchall()
        return {r[0].lower().strip() for r in rows}
    finally:
        conn.close()


def get_rejected_companies() -> set[str]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT company_name FROM startups WHERE LOWER(TRIM(status)) = 'not interested'"
        ).fetchall()
        return {r[0].lower().strip() for r in rows}
    finally:
        conn.close()


def get_existing_job_keys() -> set[str]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT company_name, role_title FROM job_matches").fetchall()
        return {f"{r[0].lower().strip()}|{r[1].lower().strip()}" for r in rows}
    finally:
        conn.close()


def is_processed(source: str, item_id: str) -> bool:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT 1 FROM processed_items WHERE source = ? AND item_id = ?",
            (source, item_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def mark_processed(source: str, item_ids: Iterable[str]) -> None:
    conn = _connect()
    try:
        conn.executemany(
            "INSERT OR IGNORE INTO processed_items (source, item_id) VALUES (?, ?)",
            [(source, i) for i in item_ids],
        )
        conn.commit()
    finally:
        conn.close()


# ---------- inserts ----------

def insert_startups(startups: list[Startup]) -> int:
    if not startups:
        return 0
    conn = _connect()
    count = 0
    try:
        for s in startups:
            date_str = (s.date_found or datetime.now()).strftime("%Y-%m-%d")
            try:
                conn.execute(
                    """INSERT INTO startups
                       (company_name, description, funding_stage, amount_raised,
                        location, website, source, source_url, date_found)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (s.company_name, s.description, s.funding_stage, s.amount_raised,
                     s.location, s.website, s.source, s.source_url, date_str),
                )
                count += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    finally:
        conn.close()
    return count


def insert_job_matches(jobs: list[JobMatch]) -> int:
    if not jobs:
        return 0
    conn = _connect()
    count = 0
    try:
        for j in jobs:
            date_str = (j.date_found or datetime.now()).strftime("%Y-%m-%d")
            try:
                conn.execute(
                    """INSERT INTO job_matches
                       (company_name, company_description, role_title, location,
                        url, priority, source, date_found)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (j.company_name, j.company_description, j.role_title, j.location,
                     j.url, j.priority, j.source, date_str),
                )
                count += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    finally:
        conn.close()
    return count


def update_startup_website(company_name: str, website: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE startups SET website = ? WHERE company_name = ? COLLATE NOCASE",
            (website, company_name),
        )
        conn.commit()
    finally:
        conn.close()


# ---------- read ----------

def get_all_startups() -> pd.DataFrame:
    conn = _connect()
    try:
        return pd.read_sql_query(
            "SELECT * FROM startups ORDER BY date_found DESC, id DESC", conn
        )
    finally:
        conn.close()


def get_all_jobs() -> pd.DataFrame:
    conn = _connect()
    try:
        return pd.read_sql_query(
            "SELECT * FROM job_matches ORDER BY date_found DESC, id DESC", conn
        )
    finally:
        conn.close()


def update_status(table: str, row_id: int, status: str) -> None:
    if table not in ("startups", "job_matches"):
        raise ValueError(f"Invalid table: {table}")
    conn = _connect()
    try:
        conn.execute(f"UPDATE {table} SET status = ? WHERE id = ?", (status, row_id))
        conn.commit()
    finally:
        conn.close()


# ---------- connections ----------

def import_connections(rows: list[dict]) -> int:
    conn = _connect()
    try:
        conn.execute("DELETE FROM connections")
        count = 0
        for r in rows:
            conn.execute(
                """INSERT INTO connections
                   (first_name, last_name, url, email, company, position, connected_on)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    r.get("First Name", ""),
                    r.get("Last Name", ""),
                    r.get("URL", ""),
                    r.get("Email Address", ""),
                    r.get("Company", ""),
                    r.get("Position", ""),
                    r.get("Connected On", ""),
                ),
            )
            count += 1
        conn.execute("DELETE FROM connections_meta")
        conn.execute(
            "INSERT INTO connections_meta (id, last_uploaded) VALUES (1, ?)",
            (datetime.now().isoformat(),),
        )
        conn.commit()
        return count
    finally:
        conn.close()


def get_connections_count() -> int:
    conn = _connect()
    try:
        row = conn.execute("SELECT COUNT(*) FROM connections").fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def get_connections_last_uploaded() -> str:
    conn = _connect()
    try:
        row = conn.execute("SELECT last_uploaded FROM connections_meta WHERE id = 1").fetchone()
        return row[0] if row else ""
    finally:
        conn.close()


def search_connections_by_company(company_name: str) -> pd.DataFrame:
    conn = _connect()
    try:
        return pd.read_sql_query(
            """SELECT first_name, last_name, url, company, position
               FROM connections
               WHERE company LIKE ? COLLATE NOCASE
               ORDER BY last_name""",
            conn,
            params=(f"%{company_name}%",),
        )
    finally:
        conn.close()


def search_connections_by_companies(company_names: list[str]) -> pd.DataFrame:
    if not company_names:
        return pd.DataFrame()
    conn = _connect()
    try:
        placeholders = " OR ".join(["company LIKE ? COLLATE NOCASE"] * len(company_names))
        params = [f"%{n}%" for n in company_names]
        return pd.read_sql_query(
            f"""SELECT first_name, last_name, url, company, position
                FROM connections WHERE {placeholders}
                ORDER BY last_name""",
            conn,
            params=params,
        )
    finally:
        conn.close()


def hide_intro(connection_url: str, company_name: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO hidden_intros (connection_url, company_name) VALUES (?, ?)",
            (connection_url, company_name),
        )
        conn.commit()
    finally:
        conn.close()


def get_hidden_intros(company_name: str) -> set[str]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT connection_url FROM hidden_intros WHERE company_name = ? COLLATE NOCASE",
            (company_name,),
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()
