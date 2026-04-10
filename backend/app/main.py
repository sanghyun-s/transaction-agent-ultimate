# backend/app/main.py
# ============================================================
# FastAPI Backend — Complete API with all SOTA endpoints
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models.schemas import (
    JournalEntryRequest,
    TermExplanationRequest,
    APIResponse,
)
from app.services.openai_service import get_journal_entry, get_term_explanation

app = FastAPI(
    title="Accounting Transaction Agent API",
    description="AI-powered accounting journal entry helper",
    version="0.2.0",
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

    # 성공 시 히스토리에 저장
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
