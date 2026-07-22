# backend/app/services/chat/text_splitter.py
# ============================================================
# Minimal recursive character splitter — a stand-in for LangChain's
# RecursiveCharacterTextSplitter (chunk_size=1000, chunk_overlap=200) so the
# RAG path needs no LangChain dependency. Prefers to break on paragraph, then
# line, then sentence, then word boundaries, packing to ~chunk_size with a
# chunk_overlap tail shared between adjacent chunks.
# ============================================================

from __future__ import annotations

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def _split_on(text: str, sep: str) -> list[str]:
    if sep == "":
        return list(text)
    parts = text.split(sep)
    # keep the separator attached (except the trailing empty split)
    out = []
    for i, p in enumerate(parts):
        if i < len(parts) - 1:
            out.append(p + sep)
        elif p:
            out.append(p)
    return out


def _recursive_pack(text: str, seps: list[str], size: int) -> list[str]:
    """Break text into pieces each <= size, splitting on the coarsest separator
    that works and recursing into any piece still too large."""
    if len(text) <= size:
        return [text] if text else []
    sep = seps[0] if seps else ""
    pieces = _split_on(text, sep)
    chunks, buf = [], ""
    for piece in pieces:
        if len(piece) > size:
            if buf:
                chunks.append(buf); buf = ""
            chunks.extend(_recursive_pack(piece, seps[1:], size))
            continue
        if len(buf) + len(piece) <= size:
            buf += piece
        else:
            if buf:
                chunks.append(buf)
            buf = piece
    if buf:
        chunks.append(buf)
    return chunks


def split_text(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks. Overlap is achieved by prefixing each
    chunk (after the first) with the tail of the previous one."""
    base = _recursive_pack(text or "", _SEPARATORS, chunk_size)
    base = [c.strip() for c in base if c and c.strip()]
    if chunk_overlap <= 0 or len(base) <= 1:
        return base
    out = [base[0]]
    for i in range(1, len(base)):
        tail = out[-1][-chunk_overlap:]
        out.append((tail + " " + base[i]).strip())
    return out


def split_pages(pages: list[str], chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Split a list of page texts into chunks, tagged with their source page (1-based)."""
    chunks: list[dict] = []
    for page_no, page_text in enumerate(pages, start=1):
        for piece in split_text(page_text, chunk_size, chunk_overlap):
            chunks.append({"text": piece, "page": page_no})
    return chunks
