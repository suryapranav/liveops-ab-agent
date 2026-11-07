"""SQLite storage for an experiment: one table of players, one row of metadata.

Why a database at all? The agent gets a SQL tool for questions the fixed
stats tools don't cover. And building the database from a DataFrame (not
straight from the CSV) lets the eval suite create deliberately broken
experiments (skewed split, tiny sample) by editing a DataFrame first.

The agent only ever gets a READ-ONLY connection (open_readonly). That is
enforced by SQLite itself, not by asking the model nicely.
"""
import sqlite3
from pathlib import Path

from .data import CONTROL, OUTCOME_METRICS, TREATMENT

SCHEMA = """
CREATE TABLE players (
    userid         INTEGER PRIMARY KEY,
    version        TEXT    NOT NULL CHECK (version IN ('gate_30', 'gate_40')),
    sum_gamerounds INTEGER NOT NULL,
    retention_1    INTEGER NOT NULL CHECK (retention_1 IN (0, 1)),
    retention_7    INTEGER NOT NULL CHECK (retention_7 IN (0, 1))
);
-- Decisions made BEFORE looking at results. Stored with the data so the
-- tools (and later the guardrails) read them instead of the model guessing.
CREATE TABLE experiment (
    name                   TEXT NOT NULL,
    control                TEXT NOT NULL,
    treatment              TEXT NOT NULL,
    primary_metric         TEXT NOT NULL,
    expected_share_control REAL NOT NULL,  -- planned split, e.g. 0.5
    alpha                  REAL NOT NULL,  -- significance level
    target_mde_abs         REAL NOT NULL   -- smallest lift worth detecting
);
"""


def build_database(df, db_path, *, name="cookie_cats_gate_30_vs_40",
                   primary_metric="retention_7", expected_share_control=0.5,
                   alpha=0.05, target_mde_abs=0.01):
    """Write a validated Cookie Cats DataFrame (see data.load_cookie_cats) to SQLite."""
    if primary_metric not in OUTCOME_METRICS:
        raise ValueError(f"primary_metric must be one of {OUTCOME_METRICS}")
    db_path = Path(db_path)
    if db_path.exists():
        raise FileExistsError(f"{db_path} already exists; refusing to overwrite")

    rows = [
        (int(r.userid), r.version, int(r.sum_gamerounds), int(r.retention_1), int(r.retention_7))
        for r in df.itertuples(index=False)
    ]
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO players VALUES (?, ?, ?, ?, ?)", rows)
        conn.execute(
            "INSERT INTO experiment VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, CONTROL, TREATMENT, primary_metric,
             expected_share_control, alpha, target_mde_abs),
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def open_readonly(db_path):
    """Open the database so that ANY write raises sqlite3.OperationalError."""
    db_path = Path(db_path).resolve()
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    # as_uri() percent-encodes spaces etc.; mode=ro makes SQLite refuse writes.
    conn = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
