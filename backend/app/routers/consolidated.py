# backend/app/routers/consolidated.py
# ============================================================
# Consolidated Workbook (PREPARE Tool 2) endpoints.
#   POST /api/consolidated/analyze   multipart:
#       pdf_files[]  : two or more statement PDFs
#       vendor_csv   : optional vendor master (first column = canonical names)
#       engine       : "skill" (default) | "rule"
#       model        : "sonnet" (default) | "opus" | full id
#   GET  /api/consolidated/download/{req_id}/{fname}   the generated .xlsx
# ============================================================

import os
import csv
import io
import shutil
import uuid
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.services.consolidated import consolidate

router = APIRouter(prefix="/api/consolidated", tags=["consolidated"])

OUT_DIR = Path(tempfile.gettempdir()) / "tau_consolidated"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _parse_vendor_csv(raw: str) -> list[str]:
    """First column = canonical vendor names. Skips an obvious header row."""
    names: list[str] = []
    reader = csv.reader(io.StringIO(raw))
    for i, row in enumerate(reader):
        if not row:
            continue
        cell = (row[0] or "").strip()
        if not cell:
            continue
        if i == 0 and cell.lower() in {"vendor", "name", "vendor name", "canonical", "canonical name"}:
            continue
        names.append(cell)
    return names


@router.post("/analyze")
async def consolidated_analyze(
    pdf_files: list[UploadFile] = File(...),
    vendor_csv: Optional[UploadFile] = File(None),
    engine: str = Form("skill"),
    model: str = Form("sonnet"),
):
    req_id = uuid.uuid4().hex
    req_dir = OUT_DIR / req_id
    req_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for uf in pdf_files:
        safe = os.path.basename(uf.filename or "statement.pdf").replace("/", "_").replace("\\", "_")
        p = req_dir / safe
        with p.open("wb") as f:
            shutil.copyfileobj(uf.file, f)
        paths.append(str(p))

    vendor_list = []
    if vendor_csv is not None:
        raw = (await vendor_csv.read()).decode("utf-8", errors="ignore")
        vendor_list = _parse_vendor_csv(raw)

    result = consolidate(paths, vendor_list=vendor_list, engine=engine,
                         model=model, output_dir=str(req_dir))

    if result.get("excel_path"):
        result["excel_file_id"] = f"{req_id}/{Path(result['excel_path']).name}"
    result.pop("excel_path", None)  # don't leak server paths to the client

    # remove the uploaded PDFs; keep only the workbook for download
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass
    return result


@router.get("/download/{req_id}/{fname}")
def consolidated_download(req_id: str, fname: str):
    safe = os.path.basename(fname)
    path = OUT_DIR / req_id / safe
    if not path.exists():
        return {"error": "file not found or expired"}
    return FileResponse(str(path), filename=safe, media_type=_XLSX_MIME)
