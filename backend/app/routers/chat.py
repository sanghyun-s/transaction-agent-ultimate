# backend/app/routers/chat.py
# ============================================================
# Data & Document Chat endpoints (CASSIA add-on).
#   POST /api/chat/upload  — load a CSV/Excel/PDF into the session (side action)
#   POST /api/chat/ask     — ask a question; routed to sql / rag / general
#   POST /api/chat/reset   — clear the session (new blank chat)
#   GET  /api/chat/state   — what's currently loaded in the session
# ============================================================

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.services import chat as chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/upload")
async def upload(session_id: str = Form(...), file: UploadFile = File(...)):
    data = await file.read()
    try:
        return chat_service.ingest_upload(session_id, file.filename, data)
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/ask")
async def ask(session_id: str = Form(...), question: str = Form(...),
              language: str = Form("English")):
    try:
        return {"success": True, **chat_service.ask(session_id, question, language)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/reset")
async def reset(session_id: str = Form(...)):
    return chat_service.reset(session_id)


@router.get("/state")
async def state(session_id: str):
    return chat_service.session_state(session_id)
