# backend/app/services/history_service.py
# ============================================================
# Work History service — the shared archive every TAU tool writes to.
# ------------------------------------------------------------
# Extends the old journal-only, in-memory list into a global,
# filterable, restart-surviving archive.
#   * save_to_history(...)  — one call any tool/endpoint can make
#   * list_history(tool)    — newest-first, optional tool filter
#   * get_history(id)       — one item (for click-to-reopen)
#   * delete_history(id) / reset_history()
# No semantic recall by design — that boundary stays CASSIA-standalone.
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from app.db import get_conn, init_db

# Ensure the table exists as soon as this module is imported (idempotent).
init_db()

_PREVIEW_LEN = 240


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["is_sensitive"] = bool(d.get("is_sensitive", 0))
    d["masked_export_available"] = bool(d.get("masked_export_available", 0))
    return d


def save_to_history(
    *,
    tool_name: str,
    title: str = "",
    language: str = "",
    input_summary: str = "",
    output_content: str = "",
    output_preview: str = "",
    output_format: str = "markdown",
    artifact_path: Optional[str] = None,
    file_type: Optional[str] = None,
    is_sensitive: bool = False,
    masked_export_available: bool = False,
) -> dict:
    """Insert one archive entry and return it as a dict."""
    item_id = uuid.uuid4().hex
    if not output_preview:
        output_preview = (output_content or "")[:_PREVIEW_LEN]

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO history
                 (id, tool_name, title, created_at, language, input_summary,
                  output_preview, output_content, output_format, artifact_path,
                  file_type, is_sensitive, masked_export_available)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                item_id, tool_name, title, _now(), language, input_summary,
                output_preview, output_content, output_format, artifact_path,
                file_type, int(is_sensitive), int(masked_export_available),
            ),
        )
    return get_history(item_id)


def list_history(tool_name: Optional[str] = None) -> list[dict]:
    """Newest-first. Pass tool_name to filter (the 'view by preference' path)."""
    with get_conn() as conn:
        if tool_name:
            rows = conn.execute(
                "SELECT * FROM history WHERE tool_name=? "
                "ORDER BY created_at DESC, rowid DESC",
                (tool_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM history ORDER BY created_at DESC, rowid DESC"
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_history(item_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM history WHERE id=?", (item_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def delete_history(item_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM history WHERE id=?", (item_id,))
        return cur.rowcount > 0


def reset_history() -> int:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM history")
        return cur.rowcount


def list_tools() -> list[str]:
    """Distinct tool_names present — powers the filter dropdown."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT tool_name FROM history ORDER BY tool_name"
        ).fetchall()
    return [r["tool_name"] for r in rows]
