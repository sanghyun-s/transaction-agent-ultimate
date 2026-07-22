# backend/app/services/chat/rag_engine.py
# ============================================================
# Retrieval-augmented answering over an IN-MEMORY vector store (session-scoped).
# ChromaDB is replaced by a numpy matrix + cosine similarity - that swap is what
# lets this run on TAU's existing deps (no chromadb/numpy<2 conflict).
#
# Chunking is context-preserving, which matters a lot for statements:
#   * a short document is kept whole (one chunk per page) instead of being
#     sliced mid-row;
#   * every chunk carries a CONTEXT PREFIX - the document title block and the
#     table's column header - so an orphaned run of numbers still says which
#     column is which.
# Retrieval sends the WHOLE document when it is small (<= FULL_DOC_CHUNKS),
# so short statements never lose information to top-k.
# ============================================================

from __future__ import annotations

import io
import re

import numpy as np
import pdfplumber

from .text_splitter import split_text

_EMBED_MODEL = "text-embedding-3-small"
_GEN_MODEL = "gpt-4o-mini"
_EMBED_BATCH = 64
TOP_K = 6
FULL_DOC_CHUNKS = 10          # <= this many chunks -> send them all
PAGE_WHOLE_LIMIT = 1800       # a page shorter than this is kept as ONE chunk

_DATE_START = re.compile(r"^\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})")
_HEADERISH = re.compile(
    r"(date|description|amount|balance|withdraw|deposit|credit|debit|vendor|payee|qty|total)",
    re.IGNORECASE,
)


def extract_pdf_pages(pdf_bytes: bytes) -> list[str]:
    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return pages


_PERIOD = re.compile(
    r"(?:statement period|period|for the month(?: of)?|month ended|as of)\s*[:\-]?\s*([^\n]{3,40})",
    re.IGNORECASE,
)
_MONTH_YEAR = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
    re.IGNORECASE,
)


def _period_label(page_text: str) -> str | None:
    """A human label for the page's period, e.g. 'September 2025'. Used to tag
    PDF table rows so a multi-month statement stays distinguishable."""
    m = _MONTH_YEAR.search(page_text or "")
    if m:
        return f"{m.group(1).title()} {m.group(2)}"
    m = _PERIOD.search(page_text or "")
    if m:
        return m.group(1).strip(" .;")[:40] or None
    return None


def extract_pdf_tables(pdf_bytes: bytes) -> list[dict]:
    """Structured tables detected in the PDF (free, no API call).
    Returns [{rows, page, label}] - row 0 of `rows` is the header."""
    out: list[dict] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            label = _period_label(page.extract_text() or "")
            for t in page.extract_tables() or []:
                if t and len(t) >= 2 and len(t[0]) >= 2:
                    out.append({"rows": t, "page": page_no, "label": label})
    return out


def _doc_title(pages: list[str], max_lines: int = 3, max_chars: int = 180) -> str:
    for p in pages:
        lines = [l.strip() for l in (p or "").splitlines() if l.strip()]
        if lines:
            return " | ".join(lines[:max_lines])[:max_chars]
    return ""


def _column_header(page_text: str) -> str:
    """Find the table's column-header line: a header-ish line whose next
    non-empty line starts with a date or a number."""
    lines = [l for l in (page_text or "").splitlines()]
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or len(s.split()) < 2 or not _HEADERISH.search(s):
            continue
        for nxt in lines[i + 1:]:
            n = nxt.strip()
            if not n:
                continue
            if _DATE_START.match(n) or re.match(r"^[\d$(]", n):
                return s[:160]
            break
    return ""


def chunk_pdf(pdf_bytes: bytes) -> list[dict]:
    """PDF -> context-preserving chunks: [{text, page, prefix}]."""
    pages = extract_pdf_pages(pdf_bytes)
    title = _doc_title(pages)
    chunks: list[dict] = []
    for page_no, page_text in enumerate(pages, start=1):
        text = (page_text or "").strip()
        if not text:
            continue
        col_hdr = _column_header(text)
        prefix_bits = [b for b in (title, col_hdr) if b]
        prefix = " || ".join(prefix_bits)

        pieces = [text] if len(text) <= PAGE_WHOLE_LIMIT else split_text(text)
        for piece in pieces:
            body = piece.strip()
            if not body:
                continue
            full = f"[{prefix}]\n{body}" if prefix and prefix not in body[:len(prefix) + 5] else body
            chunks.append({"text": full, "page": page_no, "prefix": prefix})
    return chunks


# ---- OpenAI calls -----------------------------------------------------------

def embed_texts(client, texts: list[str]) -> np.ndarray:
    vectors: list[list[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH):
        resp = client.embeddings.create(model=_EMBED_MODEL, input=texts[i:i + _EMBED_BATCH])
        vectors.extend([d.embedding for d in resp.data])
    return np.asarray(vectors, dtype=np.float32)


def _chat(client, messages: list[dict]) -> str:
    resp = client.chat.completions.create(model=_GEN_MODEL, messages=messages, temperature=0)
    return resp.choices[0].message.content or ""


# ---- deterministic retrieval math ------------------------------------------

def cosine_top_k(query_vec: np.ndarray, matrix: np.ndarray, k: int = TOP_K) -> list[int]:
    if matrix is None or len(matrix) == 0:
        return []
    q = query_vec.astype(np.float32).ravel()
    qn = q / (np.linalg.norm(q) + 1e-8)
    mn = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8)
    sims = mn @ qn
    k = min(k, len(sims))
    idx = np.argpartition(-sims, k - 1)[:k]
    return [int(i) for i in idx[np.argsort(-sims[idx])]]


def build_context(chunks: list[dict], indices: list[int]) -> str:
    blocks = []
    for rank, i in enumerate(indices, start=1):
        c = chunks[i]
        blocks.append(f"[{rank}] (p.{c.get('page', '?')}) {c['text']}")
    return "\n\n".join(blocks)


def answer_rag(client, question, chunks, matrix, lang_instruction) -> dict:
    if not chunks or matrix is None or len(matrix) == 0:
        return {"answer": None, "error": "No document content loaded."}

    if len(chunks) <= FULL_DOC_CHUNKS:
        idx = list(range(len(chunks)))          # small doc -> send it all
    else:
        q_vec = embed_texts(client, [question])[0]
        idx = cosine_top_k(q_vec, matrix, TOP_K)

    context = build_context(chunks, idx)
    messages = [
        {"role": "system", "content":
            "You are a knowledgeable accounting and tax assistant. Answer using ONLY the "
            "provided document context. Quote exact figures from it. If the answer is not "
            "in the context, say so plainly. " + lang_instruction},
        {"role": "user", "content": f"Document context:\n{context}\n\nQuestion: {question}"},
    ]
    answer = _chat(client, messages)
    pages = sorted({chunks[i].get("page") for i in idx if chunks[i].get("page")})
    return {"answer": answer, "source_pages": pages, "chunks_used": len(idx)}
