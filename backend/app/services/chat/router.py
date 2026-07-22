# backend/app/services/chat/router.py
# ============================================================
# Route a question to an engine.
#
# WHY THIS IS NOT A KEYWORD CLASSIFIER ANY MORE
# ---------------------------------------------
# v1 guessed SQL-vs-RAG from aggregation keywords ("total", "how many", ...).
# That failed systematically: accounting questions are almost ALWAYS numeric,
# so with both a table and a document loaded, essentially every question was
# routed to SQL - even "what is the total deposits in the bank statement",
# whose answer lives in the PDF. No keyword list (English or Korean) can know
# WHICH SOURCE holds the answer.
#
# So routing now works on evidence rather than phrasing:
#   1. explicit intent in the question wins  ("read the PDF" / "in the table")
#   2. only one source loaded -> that source
#   3. both loaded -> "sql_then_rag": try SQL; if the schema can't answer it,
#      the SQL engine reports NO_SQL and the caller falls back to RAG.
#   4. nothing loaded -> general Q&A
#
# Because the fallback is decided by the SQL engine looking at the actual
# schema (not by matching words), this is language-agnostic: Korean, English,
# or anything else routes correctly without a translated keyword list.
# ============================================================

from __future__ import annotations

import re

ROUTE_SQL = "sql"
ROUTE_RAG = "rag"
ROUTE_SQL_THEN_RAG = "sql_then_rag"
ROUTE_GENERAL = "general"

# Explicit "use the document" / "use the table" cues, EN + KO.
_RAG_INTENT = re.compile(
    r"(read the pdf|in the pdf|from the pdf|the pdf says|in the document"
    r"|from the document|per the document|according to the document"
    r"|in the statement|on the statement"
    r"|\ubb38\uc11c\uc5d0\uc11c|\ubb38\uc11c\ub97c|pdf\uc5d0\uc11c|pdf\ub97c"
    r"|\uba85\uc138\uc11c\uc5d0\uc11c|\uc11c\ub958\uc5d0\uc11c)",
    re.IGNORECASE,
)
_SQL_INTENT = re.compile(
    r"(in the table|from the table|in the csv|from the csv|in the spreadsheet"
    r"|from the spreadsheet|in the excel|from the excel|query the table|run sql"
    r"|\ud45c\uc5d0\uc11c|\ud45c\ub97c|\uc5d1\uc140\uc5d0\uc11c|\uc5d1\uc140\uc744"
    r"|csv\uc5d0\uc11c|\uc2dc\ud2b8\uc5d0\uc11c|\ub370\uc774\ud130\uc5d0\uc11c)",
    re.IGNORECASE,
)


def explicit_intent(question: str) -> str | None:
    """Return 'rag' / 'sql' when the question names its source, else None."""
    q = question or ""
    rag_hit = bool(_RAG_INTENT.search(q))
    sql_hit = bool(_SQL_INTENT.search(q))
    if rag_hit and not sql_hit:
        return ROUTE_RAG
    if sql_hit and not rag_hit:
        return ROUTE_SQL
    return None


def decide_route(question: str, has_table: bool, has_pdf: bool) -> str:
    """Return 'sql' | 'rag' | 'sql_then_rag' | 'general'."""
    intent = explicit_intent(question)
    if intent == ROUTE_RAG and has_pdf:
        return ROUTE_RAG
    if intent == ROUTE_SQL and has_table:
        return ROUTE_SQL

    if has_table and has_pdf:
        return ROUTE_SQL_THEN_RAG
    if has_table:
        return ROUTE_SQL
    if has_pdf:
        return ROUTE_RAG
    return ROUTE_GENERAL
