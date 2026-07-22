# backend/app/services/chat/service.py
# ============================================================
# Data & Document Chat facade (CASSIA add-on, minimal).
#
# Session state lives in a module-level dict keyed by a client-generated
# session_id: ephemeral by design ("new chat = blank session"), single-process,
# fine for local single-user TAU. Upload is a SIDE action; the chat and the
# router are available with or without it.
#
# A PDF is ingested TWICE, cheaply:
#   * as text chunks  -> RAG (narrative questions)
#   * as detected tables -> in-memory SQLite (numeric questions)
# so "what were total deposits?" can be answered exactly by SQL over the
# statement's own rows, instead of read off the prose.
# ============================================================

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field

import numpy as np

from . import rag_engine, sql_engine
from .router import (ROUTE_GENERAL, ROUTE_RAG, ROUTE_SQL, ROUTE_SQL_THEN_RAG,
                     decide_route)

_GEN_MODEL = "gpt-4o-mini"


@dataclass
class Session:
    sql_conn: sqlite3.Connection | None = None
    table_names: list = field(default_factory=list)
    schema: str = ""
    pdf_chunks: list = field(default_factory=list)
    pdf_matrix: object | None = None
    loaded_files: list = field(default_factory=list)
    history: list = field(default_factory=list)


_SESSIONS: dict[str, Session] = {}


def _session(session_id: str) -> Session:
    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = Session()
    return _SESSIONS[session_id]


def _conn(s: Session) -> sqlite3.Connection:
    if s.sql_conn is None:
        s.sql_conn = sqlite3.connect(":memory:", check_same_thread=False)
    return s.sql_conn


def _client():
    from openai import OpenAI
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=key)


def _lang_instruction(lang: str) -> str:
    if lang == "\ud55c\uad6d\uc5b4":
        return "Respond in Korean."
    if lang == "Bilingual":
        return "Respond in Korean first, then English."
    return "Respond in English."


def reset(session_id: str) -> dict:
    s = _SESSIONS.pop(session_id, None)
    if s and s.sql_conn is not None:
        try:
            s.sql_conn.close()
        except Exception:
            pass
    return {"success": True, "loaded_files": []}


def session_state(session_id: str) -> dict:
    s = _SESSIONS.get(session_id)
    if not s:
        return {"loaded_files": [], "has_table": False, "has_pdf": False, "tables": []}
    return {
        "loaded_files": s.loaded_files,
        "has_table": bool(s.table_names),
        "has_pdf": bool(s.pdf_chunks),
        "tables": s.table_names,
    }


def _table_label(rows: list[list], stem: str, i: int) -> str:
    """Name a PDF-extracted table after what it looks like."""
    header = " ".join(str(c or "") for c in rows[0]).lower()
    if "date" in header and ("description" in header or "amount" in header):
        return f"{stem}_transactions"
    if len(rows[0]) == 2:
        return f"{stem}_summary"
    return f"{stem}_t{i}"


def ingest_upload(session_id: str, filename: str, file_bytes: bytes) -> dict:
    s = _session(session_id)
    lower = (filename or "").lower()

    if lower.endswith((".csv", ".tsv", ".xlsx", ".xls", ".xltx")):
        conn, tables, _ = sql_engine.load_tables(file_bytes, filename, conn=_conn(s))
        s.table_names = sorted(set(s.table_names) | set(tables))
        s.schema = sql_engine.get_schema(conn)
        s.loaded_files.append({"name": filename, "kind": "table"})
        return {"success": True, "kind": "table", "tables": tables,
                "loaded_files": s.loaded_files}

    if lower.endswith(".pdf"):
        chunks = rag_engine.chunk_pdf(file_bytes)
        if not chunks:
            return {"success": False, "error": "No extractable text in PDF."}
        matrix = rag_engine.embed_texts(_client(), [c["text"] for c in chunks])
        s.pdf_chunks.extend(chunks)
        s.pdf_matrix = matrix if s.pdf_matrix is None else np.vstack([s.pdf_matrix, matrix])

        # also make the PDF's tables queryable (free, no API call)
        stem = sql_engine._safe_name(lower.rsplit(".", 1)[0], "pdf")
        made: list[str] = []
        try:
            for i, tbl in enumerate(rag_engine.extract_pdf_tables(file_bytes), start=1):
                rows = tbl["rows"]
                _, tname = sql_engine.load_rows(
                    rows, _table_label(rows, stem, i), conn=_conn(s),
                    source_page=tbl.get("page"), source_label=tbl.get("label"))
                if tname:
                    made.append(tname)
        except Exception:
            made = []
        if made:
            s.table_names = sorted(set(s.table_names) | set(made))
            s.schema = sql_engine.get_schema(_conn(s))

        s.loaded_files.append({"name": filename, "kind": "pdf"})
        return {"success": True, "kind": "pdf", "chunks": len(chunks),
                "tables_from_pdf": made, "loaded_files": s.loaded_files}

    return {"success": False, "error": f"Unsupported file type: {filename}"}


def _answer_general(client, question: str, lang_instruction: str) -> dict:
    messages = [
        {"role": "system", "content":
            "You are a knowledgeable accounting and tax assistant. Answer the user's question "
            "clearly. If it would require their specific data or documents, invite them to add "
            "a CSV/Excel or PDF on the side. " + lang_instruction},
        {"role": "user", "content": question},
    ]
    resp = client.chat.completions.create(model=_GEN_MODEL, messages=messages, temperature=0)
    return {"answer": resp.choices[0].message.content or ""}


def ask(session_id: str, question: str, lang: str = "English") -> dict:
    s = _session(session_id)
    route = decide_route(question, has_table=bool(s.table_names), has_pdf=bool(s.pdf_chunks))
    instr = _lang_instruction(lang)
    client = _client()
    fell_back = None

    if route in (ROUTE_SQL, ROUTE_SQL_THEN_RAG):
        out = sql_engine.answer_sql(client, question, _conn(s), s.schema, instr)
        if out.get("no_sql"):
            # the schema genuinely can't answer it -> try the document instead
            if s.pdf_chunks:
                fell_back = out.get("reason")
                out = rag_engine.answer_rag(client, question, s.pdf_chunks, s.pdf_matrix, instr)
                route = ROUTE_RAG
            else:
                out = {"answer": None,
                       "error": _no_data_message(s, out.get("reason"), lang)}
                route = ROUTE_SQL
    elif route == ROUTE_RAG:
        out = rag_engine.answer_rag(client, question, s.pdf_chunks, s.pdf_matrix, instr)
    else:
        out = _answer_general(client, question, instr)

    out["route"] = route
    if fell_back:
        out["fell_back_from_sql"] = fell_back
    if out.get("answer") is not None:
        s.history.append({"role": "user", "content": question})
        s.history.append({"role": "assistant", "content": out["answer"]})
    return out


def _no_data_message(s: Session, reason: str | None, lang: str) -> str:
    cols = []
    if s.sql_conn is not None:
        for t, c in sql_engine.schema_map(s.sql_conn).items():
            cols.append(f"{t} ({', '.join(c[:8])})")
    listing = "; ".join(cols) if cols else "-"
    if lang == "\ud55c\uad6d\uc5b4":
        return ("\ubd88\ub7ec\uc628 \ub370\uc774\ud130\ub85c\ub294 \ub2f5\ubcc0\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4. "
                f"\ud604\uc7ac \uc0ac\uc6a9 \uac00\ub2a5\ud55c \ud45c: {listing}")
    return ("I can't answer that from the data that's loaded. "
            f"Available table(s): {listing}")
