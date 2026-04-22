# backend/app/main.py
# ============================================================
# FastAPI Backend — Complete API with all SOTA endpoints
# ============================================================

# Load .env at startup so environment variables are available to all services
# (including ANTHROPIC_API_KEY for the Claude Agent SDK)
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import json
import tempfile
import shutil
import uuid
from pathlib import Path

from app.models.schemas import (
    JournalEntryRequest,
    TermExplanationRequest,
    APIResponse,
)
from app.services.openai_service import get_journal_entry, get_term_explanation
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

# NEW — Reconciliation feature (1099 pre-reconciliation)
from app.services.reconciliation_service import (
    run_rule_based_pipeline,
    run_agent_pipeline,
    OUTPUT_DIR as RECON_OUTPUT_DIR,
)
from app.models.reconciliation_schemas import ReconciliationResponse

app = FastAPI(
    title="Accounting Transaction Agent API",
    description="AI-powered accounting journal entry helper",
    version="0.5.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory history storage (resets when server restarts)
journal_history = []


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Accounting Transaction Agent API is running"}


@app.post("/api/journal", response_model=APIResponse)
def create_journal_entry(request: JournalEntryRequest):
    """거래 설명을 받아 분개를 생성합니다."""
    result = get_journal_entry(request.transaction, request.language)

    if result.success:
        from datetime import datetime
        journal_history.insert(0, {
            "id": len(journal_history) + 1,
            "transaction": request.transaction,
            "language": request.language,
            "content": result.content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    return result


@app.post("/api/term", response_model=APIResponse)
def explain_term(request: TermExplanationRequest):
    """회계 용어를 설명합니다."""
    return get_term_explanation(request.term, request.language)


@app.get("/api/history")
def get_history():
    """분개 히스토리를 반환합니다."""
    return {"history": journal_history}


@app.delete("/api/history")
def clear_history():
    """분개 히스토리를 초기화합니다."""
    journal_history.clear()
    return {"message": "히스토리가 초기화되었습니다."}


@app.post("/api/analyze-file")
async def analyze_file(file: UploadFile = File(...)):
    """
    Upload a CSV, Excel, or PDF file → clean with pandas → analyze with GPT.
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
        if filename.endswith(".pdf"):
            df_clean = df_raw
        else:
            df_clean = clean_gl_data(df_raw)

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


# ============================================================
# NEW — Reconciliation Endpoints (Session 3 Add-On)
# ============================================================

@app.post("/api/reconcile/rule-based", response_model=ReconciliationResponse)
async def reconcile_rule_based(
    pdf_file: UploadFile = File(...),
    vendor_list: UploadFile = File(None),
):
    """
    Rule-based 1099 pre-reconciliation.
    Fast, deterministic, no API cost.

    Returns a ReconciliationResponse with vendor summary and a file_id
    the frontend can use to download the generated Excel.
    """
    try:
        pdf_tmp = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}.pdf"
        with pdf_tmp.open("wb") as f:
            shutil.copyfileobj(pdf_file.file, f)

        csv_tmp = None
        if vendor_list:
            csv_tmp = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}.csv"
            with csv_tmp.open("wb") as f:
                shutil.copyfileobj(vendor_list.file, f)

        result = run_rule_based_pipeline(
            pdf_path=str(pdf_tmp),
            vendor_csv_path=str(csv_tmp) if csv_tmp else None,
        )
        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "mode": "rule-based",
        }


@app.post("/api/reconcile/agent", response_model=ReconciliationResponse)
async def reconcile_agent(
    pdf_file: UploadFile = File(...),
    vendor_list: UploadFile = File(None),
    model: str = Form("claude-haiku-4-5-20251001"),
):
    """
    Claude-Agent-SDK-powered 1099 pre-reconciliation.
    Uses Anthropic API credits.

    The Claude agent autonomously orchestrates the extraction, normalization,
    aggregation, and Excel generation tools. Returns the same shape as the
    rule-based endpoint PLUS agent_summary, agent_cost_usd, agent_tool_calls.
    """
    try:
        pdf_tmp = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}.pdf"
        with pdf_tmp.open("wb") as f:
            shutil.copyfileobj(pdf_file.file, f)

        csv_tmp = None
        if vendor_list:
            csv_tmp = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}.csv"
            with csv_tmp.open("wb") as f:
                shutil.copyfileobj(vendor_list.file, f)

        result = await run_agent_pipeline(
            pdf_path=str(pdf_tmp),
            vendor_csv_path=str(csv_tmp) if csv_tmp else None,
            model=model,
        )
        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "mode": "agent",
        }


@app.get("/api/reconcile/download/{file_id}")
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