# backend/app/db.py
# ============================================================
# Tiny SQLite layer for TAU Work History.
# ------------------------------------------------------------
# Deliberately minimal: ONE table, stdlib sqlite3, no ORM,
# no migration framework. This is an ARCHIVE (click-to-reopen /
# re-download), NOT semantic recall. Meaning-based recall
# (embeddings, vector search) stays in standalone CASSIA.
# ============================================================

from __future__ import annotations

import sqlite3
from pathlib import Path
from contextlib import contextmanager

# backend/tau_history.db
#   app/db.py -> app -> backend  (two parents up from this file)
DB_PATH = Path(__file__).resolve().parent.parent / "tau_history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id                       TEXT PRIMARY KEY,
    tool_name                TEXT NOT NULL,
    title                    TEXT NOT NULL DEFAULT '',
    created_at               TEXT NOT NULL,
    language                 TEXT NOT NULL DEFAULT '',
    input_summary            TEXT NOT NULL DEFAULT '',
    output_preview           TEXT NOT NULL DEFAULT '',
    output_content           TEXT NOT NULL DEFAULT '',
    output_format            TEXT NOT NULL DEFAULT 'markdown',
    artifact_path            TEXT,
    file_type                TEXT,
    is_sensitive             INTEGER NOT NULL DEFAULT 0,
    masked_export_available  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_history_tool    ON history(tool_name);
CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at);
"""


def init_db(db_path: Path | str | None = None) -> None:
    """Create the history table if it does not exist. Safe to call repeatedly."""
    path = Path(db_path) if db_path else DB_PATH
    with sqlite3.connect(path) as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def get_conn(db_path: Path | str | None = None):
    """Context-managed connection with Row access and auto-commit."""
    path = Path(db_path) if db_path else DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
