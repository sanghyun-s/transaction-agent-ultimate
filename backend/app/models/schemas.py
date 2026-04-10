# backend/app/models/schemas.py
# ============================================================
# API request/response models
# ============================================================
# These define the exact shape of data the frontend sends
# and what the backend returns. FastAPI auto-generates
# API documentation from these models.
# ============================================================

from pydantic import BaseModel, Field


class JournalEntryRequest(BaseModel):
    """Frontend sends this when user clicks '분개 생성'"""
    transaction: str = Field(..., min_length=1, description="거래 설명")
    language: str = Field(default="한국어", description="응답 언어")


class TermExplanationRequest(BaseModel):
    """Frontend sends this when user clicks '용어 설명'"""
    term: str = Field(..., min_length=1, description="회계 용어")
    language: str = Field(default="한국어", description="응답 언어")


class APIResponse(BaseModel):
    """Backend always returns this shape"""
    success: bool
    content: str = ""
    error: str = ""
