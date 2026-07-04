# backend/app/routers/core.py
# ============================================================
# Core tools: Journal Entry Generator + Term Explainer.
# Work History is now button-driven for EVERY tool via
# POST /api/history/save, so journal no longer auto-saves.
# ============================================================

from fastapi import APIRouter

from app.models.schemas import (
    JournalEntryRequest,
    TermExplanationRequest,
    APIResponse,
)
from app.services.openai_service import get_journal_entry, get_term_explanation

router = APIRouter(prefix="/api", tags=["core"])


@router.post("/journal", response_model=APIResponse)
def create_journal_entry(request: JournalEntryRequest):
    """거래 설명을 받아 분개를 생성합니다."""
    return get_journal_entry(request.transaction, request.language)


@router.post("/term", response_model=APIResponse)
def explain_term(request: TermExplanationRequest):
    """회계 용어를 설명합니다."""
    return get_term_explanation(request.term, request.language)
