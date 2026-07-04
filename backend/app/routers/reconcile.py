# backend/app/routers/reconcile.py
# ============================================================
# 1099 Pre-Reconciliation — rule-based + Claude Agent SDK paths.
# (Extracted from the old main.py; behavior unchanged. This is the
# existing "quick 1099 worksheet" ancestor — the PREPARE add-ons that
# add per-statement evidence review + consolidated validation land in
# their own router later.)
# ============================================================

import tempfile
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.services.reconciliation_service import (
    run_rule_based_pipeline,
    run_agent_pipeline,
    OUTPUT_DIR as RECON_OUTPUT_DIR,
)
from app.models.reconciliation_schemas import ReconciliationResponse

router = APIRouter(prefix="/api/reconcile", tags=["reconcile"])


def _save_upload(upload: UploadFile, suffix: str) -> Path:
    tmp = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}{suffix}"
    with tmp.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return tmp


@router.post("/rule-based", response_model=ReconciliationResponse)
async def reconcile_rule_based(
    pdf_file: UploadFile = File(...),
    vendor_list: UploadFile = File(None),
):
    """Rule-based 1099 pre-reconciliation. Fast, deterministic, no API cost."""
    try:
        pdf_tmp = _save_upload(pdf_file, ".pdf")
        csv_tmp = _save_upload(vendor_list, ".csv") if vendor_list else None
        return run_rule_based_pipeline(
            pdf_path=str(pdf_tmp),
            vendor_csv_path=str(csv_tmp) if csv_tmp else None,
        )
    except Exception as e:
        return {"success": False, "error": str(e), "mode": "rule-based"}


@router.post("/agent", response_model=ReconciliationResponse)
async def reconcile_agent(
    pdf_file: UploadFile = File(...),
    vendor_list: UploadFile = File(None),
    model: str = Form("claude-haiku-4-5-20251001"),
):
    """Claude-Agent-SDK-powered 1099 pre-reconciliation."""
    try:
        pdf_tmp = _save_upload(pdf_file, ".pdf")
        csv_tmp = _save_upload(vendor_list, ".csv") if vendor_list else None
        return await run_agent_pipeline(
            pdf_path=str(pdf_tmp),
            vendor_csv_path=str(csv_tmp) if csv_tmp else None,
            model=model,
        )
    except Exception as e:
        return {"success": False, "error": str(e), "mode": "agent"}


@router.get("/download/{file_id}")
async def reconcile_download(file_id: str):
    """Download the generated Excel file."""
    path = RECON_OUTPUT_DIR / file_id
    if not path.exists():
        return {"success": False, "error": "File not found"}
    return FileResponse(
        path,
        filename="vendor_reconciliation.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
