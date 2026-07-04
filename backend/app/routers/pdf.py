# backend/app/routers/pdf.py
# ============================================================
# Shared statement ingestion endpoint.
#   POST /api/pdf/ingest  (multipart)
#     pdf_file : the statement PDF
#     engine   : "skill" (default) | "rule"
#     model    : "sonnet" (default) | "opus" | full model id  (skill engine)
#     source   : "bank" (default) | "credit_card"
# Returns classified transactions + breakdown + reconciliation_snapshot.
# Consumed by the 1099 Worksheet, Statement Review, and Consolidated Workbook.
# ============================================================

import tempfile
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form

from app.services.pdf import ingest_statement

router = APIRouter(prefix="/api/pdf", tags=["pdf"])


@router.post("/ingest")
async def pdf_ingest(
    pdf_file: UploadFile = File(...),
    engine: str = Form("skill"),
    model: str = Form("sonnet"),
    source: str = Form("bank"),
):
    tmp = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}.pdf"
    with tmp.open("wb") as f:
        shutil.copyfileobj(pdf_file.file, f)
    try:
        result = ingest_statement(str(tmp), engine=engine, model=model, source=source)
        result["filename"] = pdf_file.filename
        return result
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
