# backend/app/routers/files.py
# ============================================================
# File Analyzer — upload CSV/Excel/PDF, clean, summarize, GPT-analyze.
# (Extracted verbatim from the old main.py; behavior unchanged.)
# ============================================================

import json

from fastapi import APIRouter, UploadFile, File

from app.services.file_service import (
    read_uploaded_file,
    clean_gl_data,
    generate_summary,
    df_to_preview,
)
from app.services.file_prompts import (
    FILE_ANALYSIS_SYSTEM_PROMPT,
    FILE_ANALYSIS_USER_PROMPT_TEMPLATE,
)

router = APIRouter(prefix="/api", tags=["files"])


@router.post("/analyze-file")
async def analyze_file(file: UploadFile = File(...)):
    """
    Upload a CSV, Excel, or PDF file -> clean with pandas -> analyze with GPT.
    Returns cleaned data preview, statistical summary, and GPT analysis.
    """
    try:
        filename = file.filename or "unknown"
        if not filename.endswith((".csv", ".xlsx", ".xls", ".pdf")):
            return {
                "success": False,
                "error": "Unsupported file type. Please upload CSV, Excel (.xlsx), or PDF files.",
                "filename": filename,
                "row_count": 0,
                "columns": [],
                "preview": [],
                "summary": {},
            }

        file_bytes = await file.read()
        df_raw = read_uploaded_file(file_bytes, filename)

        # For PDFs, skip GL-specific cleaning (PDF tables are already extracted)
        df_clean = df_raw if filename.endswith(".pdf") else clean_gl_data(df_raw)

        summary = generate_summary(df_clean)
        preview = df_to_preview(df_clean, max_rows=50)

        summary_json = json.dumps(summary, indent=2, default=str)
        user_prompt = FILE_ANALYSIS_USER_PROMPT_TEMPLATE.format(
            summary_json=summary_json,
            filename=filename,
            row_count=len(df_clean),
            columns=list(df_clean.columns),
        )

        from app.services.openai_service import _get_client
        client = _get_client()

        if client is None:
            return {
                "success": True,
                "filename": filename,
                "row_count": len(df_clean),
                "columns": list(df_clean.columns),
                "preview": preview,
                "summary": summary,
                "gpt_analysis": "⚠️ API key not configured. Data was cleaned and summarized, but GPT analysis is unavailable.",
            }

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": FILE_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        gpt_analysis = response.choices[0].message.content

        return {
            "success": True,
            "filename": filename,
            "row_count": len(df_clean),
            "columns": list(df_clean.columns),
            "preview": preview,
            "summary": summary,
            "gpt_analysis": gpt_analysis,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "filename": file.filename or "unknown",
            "row_count": 0,
            "columns": [],
            "preview": [],
            "summary": {},
        }
