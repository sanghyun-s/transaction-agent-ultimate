# backend/app/services/chat/sql_engine.py
# ============================================================
# Text-to-SQL over an IN-MEMORY SQLite database (session-scoped, ephemeral).
#
#   CSV/Excel bytes -> pandas -> to_sql(:memory:)      (load_tables)
#   PDF table rows  -> pandas -> to_sql(:memory:)      (load_rows)
#   question + schema -> LLM writes SQL -> guard -> execute -> LLM explains
#
# Two things beyond a plain text-to-SQL:
#  * NO_SQL escape - the model may answer "NO_SQL" when the schema genuinely
#    cannot answer the question. The caller then falls back to RAG. This is
#    what lets routing be language-agnostic: the decision comes from reading
#    the schema, not from matching keywords in the question.
#  * read-only guard + schema validation - LLM-written SQL never mutates, and
#    a query naming unknown tables/columns is rejected BEFORE execution so the
#    user never sees a raw "no such column" error.
# ============================================================

from __future__ import annotations

import io
import re
import sqlite3

import pandas as pd

_GEN_MODEL = "gpt-4o-mini"
NO_SQL = "NO_SQL"

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|pragma|vacuum)\b",
    re.IGNORECASE,
)
_MONEY = re.compile(r"^\(?-?\$?\s*[\d,]+(\.\d+)?\)?$")


def _safe_name(name: str, fallback: str = "table") -> str:
    base = re.sub(r"[^0-9a-zA-Z_]", "_", (name or "").strip())
    base = re.sub(r"_+", "_", base).strip("_")
    if base and base[0].isdigit():
        base = "t_" + base
    return base or fallback


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Turn money-looking text columns ('1,850.00', '$12,450.00', '(25.00)')
    into real numbers so SUM/AVG work. Leaves genuine text columns alone."""
    for col in df.columns:
        s = df[col]
        # pandas 2.x gives text columns dtype 'object'; pandas 3.x gives 'str'.
        # Check both, or coercion silently never runs (SUM then returns garbage
        # because SQLite casts '4,200.00' to 4).
        if not (s.dtype == object or pd.api.types.is_string_dtype(s)):
            continue
        vals = s.dropna().astype(str).str.strip()
        vals = vals[vals != ""]
        if len(vals) == 0:
            continue
        if (vals.str.match(_MONEY)).mean() < 0.8:
            continue
        cleaned = (s.astype(str).str.strip()
                   .str.replace(r"[$,\s]", "", regex=True)
                   .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
                   .replace({"": None, "nan": None, "None": None}))
        df[col] = pd.to_numeric(cleaned, errors="coerce")
    return df


_DATE_PATTERNS = [
    (re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$"), "ymd"),
    (re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$"), "slash4"),
    (re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2})$"), "slash2"),
    (re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$"), "dot"),
]


def _date_parts(val: str):
    s = (val or "").strip()
    for rx, kind in _DATE_PATTERNS:
        m = rx.match(s)
        if m:
            return kind, m.groups()
    return None, None


def _add_iso_dates(df: pd.DataFrame) -> pd.DataFrame:
    """For each date-looking text column, add a companion '<col>_iso' column in
    YYYY-MM-DD. SQLite's date functions and BETWEEN only work on ISO strings, so
    without this a filter like strftime('%m', Date)='07' returns NULL and the
    answer comes back as a silent 0 instead of an error."""
    for col in list(df.columns):
        s = df[col]
        if not (s.dtype == object or pd.api.types.is_string_dtype(s)):
            continue
        vals = s.dropna().astype(str).str.strip()
        vals = vals[vals != ""]
        if len(vals) == 0:
            continue
        parsed = [_date_parts(v) for v in vals]
        if sum(1 for k, _ in parsed if k) / len(parsed) < 0.8:
            continue

        # Decide day-first vs month-first from the data itself: a first
        # component above 12 can only be a day.
        day_first = False
        for kind, g in parsed:
            if kind in ("slash4", "slash2", "dot") and g and int(g[0]) > 12:
                day_first = True
                break

        iso = []
        for v in s.astype(str):
            kind, g = _date_parts(v)
            if not kind:
                iso.append(None)
                continue
            if kind == "ymd":
                y, mo, d = g
            else:
                a, b, y = g
                mo, d = (b, a) if day_first else (a, b)
                if kind == "slash2":
                    y = ("20" + y) if int(y) < 70 else ("19" + y)
            try:
                iso.append(f"{int(y):04d}-{int(mo):02d}-{int(d):02d}")
            except (TypeError, ValueError):
                iso.append(None)
        if any(iso):
            df[f"{col}_iso"] = iso
    return df


def _dedupe_columns(cols: list[str]) -> list[str]:
    out, seen = [], {}
    for i, c in enumerate(cols):
        name = _safe_name(str(c) if c is not None else "", f"col{i+1}")
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        out.append(name)
    return out


def load_tables(file_bytes: bytes, filename: str, conn: sqlite3.Connection | None = None):
    """Load a CSV/Excel file into SQLite. Returns (conn, table_names, schema)."""
    conn = conn or sqlite3.connect(":memory:")
    lower = (filename or "").lower()
    stem = _safe_name(lower.rsplit(".", 1)[0] if "." in lower else lower, "data")
    tables: list[str] = []

    if lower.endswith((".xlsx", ".xls", ".xltx")):
        sheets = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None)
        for sheet_name, df in sheets.items():
            tname = _safe_name(sheet_name, stem) if len(sheets) > 1 else stem
            df.columns = _dedupe_columns(list(df.columns))
            df = _add_iso_dates(_coerce_numeric(df))
            df.to_sql(tname, conn, if_exists="replace", index=False)
            tables.append(tname)
    else:
        sep = "\t" if lower.endswith(".tsv") else ","
        df = pd.read_csv(io.BytesIO(file_bytes), sep=sep)
        df.columns = _dedupe_columns(list(df.columns))
        df = _add_iso_dates(_coerce_numeric(df))
        df.to_sql(stem, conn, if_exists="replace", index=False)
        tables.append(stem)

    return conn, tables, get_schema(conn)


def _looks_like_data(row: list) -> bool:
    """True when the 'header' row is really data - e.g. a summary block like
    ['Beginning Balance', '$12,450.00'] that has no header at all."""
    for cell in row:
        s = str(cell or "").strip()
        if s and (_MONEY.match(s) or re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$", s)):
            return True
    return False


def load_rows(rows: list[list], table_name: str, conn: sqlite3.Connection | None = None,
              source_page: int | None = None, source_label: str | None = None):
    """Load a table extracted from a PDF into SQLite. Row 0 is treated as the
    header unless it looks like data, in which case generic names are used.

    `source_page` / `source_label` tag each row with where it came from. Without
    them a 3-month statement yields three rows all labelled 'Ending Balance'
    with no way to tell July from September - the question is then genuinely
    unanswerable."""
    conn = conn or sqlite3.connect(":memory:")
    if not rows or len(rows) < 1:
        return conn, None

    if _looks_like_data(rows[0]):
        width = max(len(r) for r in rows)
        header = ["label", "value"] if width == 2 else [f"col{i+1}" for i in range(width)]
        header = _dedupe_columns(header)
        body = [r for r in rows if any((c or "").strip() for c in r)]
    else:
        header = _dedupe_columns([c if c else "" for c in rows[0]])
        body = [r for r in rows[1:] if any((c or "").strip() for c in r)]
    if not body:
        return conn, None
    width = len(header)
    body = [(list(r) + [None] * width)[:width] for r in body]
    df = pd.DataFrame(body, columns=header)
    df = _coerce_numeric(df)
    df = _add_iso_dates(df)
    if source_page is not None:
        df["source_page"] = source_page
    if source_label:
        df["source_label"] = source_label
    tname = _safe_name(table_name, "pdf_table")

    # A multi-page statement yields one table PER PAGE with identical columns.
    # Those are one logical table: APPEND them, or the later pages would silently
    # replace the earlier ones and most of the document would disappear.
    existing = schema_map(conn)
    if tname in existing:
        if list(existing[tname]) == list(df.columns):
            df.to_sql(tname, conn, if_exists="append", index=False)
            return conn, tname
        n = 2
        while f"{tname}_{n}" in existing:
            n += 1
        tname = f"{tname}_{n}"

    df.to_sql(tname, conn, if_exists="replace", index=False)
    return conn, tname


def get_schema(conn: sqlite3.Connection, samples: int = 3) -> str:
    """Schema string for the LLM. Includes a few DISTINCT sample values per
    column: without them the model can't see that, say, w9_on_file holds
    'Yes'/'No', and it guesses `IS NULL` - returning a confident, wrong 0."""
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    parts = []
    for (tname,) in cur.fetchall():
        cur.execute(f"PRAGMA table_info({tname})")
        info = cur.fetchall()
        try:
            cur.execute(f"SELECT COUNT(*) FROM {tname}")
            n = cur.fetchone()[0]
        except Exception:
            n = "?"
        lines = []
        for c in info:
            col, ctype = c[1], (c[2] or "TEXT")
            ex = ""
            if samples:
                try:
                    cur.execute(
                        f'SELECT DISTINCT "{col}" FROM {tname} '
                        f'WHERE "{col}" IS NOT NULL AND TRIM(CAST("{col}" AS TEXT)) <> "" '
                        f"LIMIT {samples}")
                    vals = [str(r[0]) for r in cur.fetchall()]
                    if vals:
                        shown = ", ".join(v[:28] for v in vals)
                        ex = f"   e.g. {shown}"
                except Exception:
                    ex = ""
            lines.append(f"  {col} ({ctype}){ex}")
        parts.append(f"Table: {tname}  ({n} rows)\nColumns:\n" + "\n".join(lines))
    return "\n\n".join(parts)


def schema_map(conn: sqlite3.Connection) -> dict[str, list[str]]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    out = {}
    for (tname,) in cur.fetchall():
        cur.execute(f"PRAGMA table_info({tname})")
        out[tname] = [c[1] for c in cur.fetchall()]
    return out


def guard_sql(sql: str) -> tuple[bool, str]:
    """Read-only guard: allow a single SELECT (or WITH...SELECT) statement only."""
    s = (sql or "").strip().rstrip(";").strip()
    if not s:
        return False, "empty query"
    if ";" in s:
        return False, "only a single statement is allowed"
    if _FORBIDDEN.search(s):
        return False, "only read-only SELECT queries are allowed"
    head = s.lower().lstrip("(")
    if not (head.startswith("select") or head.startswith("with")):
        return False, "query must start with SELECT"
    return True, ""


def validate_against_schema(sql: str, smap: dict[str, list[str]]) -> tuple[bool, str]:
    """Reject SQL that references a table not in the schema, before executing,
    so the user never sees a raw sqlite 'no such table/column' error."""
    referenced = set(m.group(1) for m in re.finditer(r"\b(?:from|join)\s+([A-Za-z_][\w]*)", sql, re.IGNORECASE))
    known = {t.lower() for t in smap}
    unknown = [t for t in referenced if t.lower() not in known]
    if unknown:
        return False, f"unknown table(s): {', '.join(unknown)}"
    return True, ""


def _extract_sql(text: str) -> str:
    m = re.search(r"```(?:sql)?\s*(.+?)```", text, re.DOTALL | re.IGNORECASE)
    return (m.group(1) if m else text).strip()


# ---- OpenAI calls -----------------------------------------------------------

def _chat(client, messages: list[dict]) -> str:
    resp = client.chat.completions.create(model=_GEN_MODEL, messages=messages, temperature=0)
    return resp.choices[0].message.content or ""


def write_sql(client, question: str, schema: str) -> str:
    messages = [
        {"role": "system", "content":
            "You are a SQLite expert. Given a database schema and a question, write ONE "
            "read-only SQLite SELECT query that answers it, using ONLY tables and columns "
            "that appear in the schema.\n"
            "Notes on the schema:\n"
            "- Sample values are shown after each column as 'e.g. ...'. Match filters to "
            "those actual values (for example a Yes/No column needs = 'No', not IS NULL).\n"
            "- Columns ending in _iso hold normalized YYYY-MM-DD dates. ALWAYS use the _iso "
            "column for any date filtering, comparison, or grouping; the original date "
            "column is display text and will not compare correctly.\n"
            "- source_page / source_label identify which page or statement period a row came "
            "from; use them when the question is about a specific month or period.\n"
            "- Some tables are key/value summaries with a label column and a value column "
            "(e.g. label='Beginning Balance'/'Ending Balance'/'Total Deposits & Credits'). "
            "For these, filter the label to the SPECIFIC line the question asks for and return "
            "that row's value - do not confuse 'ending balance' with 'total deposits'. When a "
            "period is named, add the matching source_label/source_page filter too.\n"
            f"If the schema does not contain the data needed, reply with exactly {NO_SQL} and "
            "nothing else. Do not invent tables or columns.\n"
            "Otherwise reply with ONLY the SQL, no prose, no code fences."},
        {"role": "user", "content": f"Schema:\n{schema}\n\nQuestion: {question}"},
    ]
    return _extract_sql(_chat(client, messages))


def explain_result(client, question, sql, rows, columns, lang_instruction) -> str:
    preview = [dict(zip(columns, r)) for r in rows[:50]]
    messages = [
        {"role": "system", "content":
            "You are an accounting assistant. Answer the user's question directly using the "
            "SQL result. Be concise and state the number(s) plainly. " + lang_instruction},
        {"role": "user", "content":
            f"Question: {question}\nSQL: {sql}\nResult rows (up to 50): {preview}\n"
            f"Total rows returned: {len(rows)}"},
    ]
    return _chat(client, messages)


def run_sql(conn: sqlite3.Connection, sql: str) -> tuple[list, list]:
    cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description] if cur.description else []
    return cur.fetchall(), cols


def _looks_empty(rows: list) -> bool:
    """A result that is structurally empty - no rows at all, or a single row of
    all-NULLs (SUM/AVG over an empty match). Usually means the filter was wrong
    (a bad date format, a guessed value), not that the answer is genuinely zero.
    A legitimate COUNT(*)=0 returns [(0,)], which is NOT all-NULL, so it passes
    through as a real answer."""
    if not rows:
        return True
    if len(rows) == 1 and all(v is None for v in rows[0]):
        return True
    return False


def answer_sql(client, question, conn, schema, lang_instruction) -> dict:
    """Full SQL path. Returns {'no_sql': True, ...} when the schema can't answer,
    so the caller can fall back to RAG."""
    raw = write_sql(client, question, schema)
    if raw.strip().upper().startswith(NO_SQL):
        return {"answer": None, "no_sql": True, "reason": "schema cannot answer this question"}

    ok, reason = guard_sql(raw)
    if not ok:
        return {"answer": None, "no_sql": True, "sql": raw, "reason": f"query rejected: {reason}"}

    ok, reason = validate_against_schema(raw, schema_map(conn))
    if not ok:
        return {"answer": None, "no_sql": True, "sql": raw, "reason": reason}

    try:
        rows, cols = run_sql(conn, raw)
    except Exception as e:
        return {"answer": None, "no_sql": True, "sql": raw, "reason": f"execution failed: {e}"}

    if _looks_empty(rows):
        # Don't report a confident 0 - for an accounting tool that is the worst
        # failure mode, because it looks like a real answer. Hand off to RAG.
        return {"answer": None, "no_sql": True, "sql": raw,
                "reason": "query returned no matching rows"}

    answer = explain_result(client, question, raw, rows, cols, lang_instruction)
    return {"answer": answer, "sql": raw, "row_count": len(rows), "columns": cols}
