# backend/app/models/history_schemas.py
# ============================================================
# Work History request/response models.
# Field list follows the plan doc (TAU 앱 1,2,3 축소화 애드온 계획).
# ============================================================

from pydantic import BaseModel, Field
from typing import Optional


class HistorySaveRequest(BaseModel):
    """Any tool posts this to POST /api/history/save."""
    tool_name: str = Field(..., description="Producing tool, e.g. 'journal', 'statement_review'")
    title: str = ""
    language: str = ""
    input_summary: str = ""
    output_preview: str = ""            # short teaser; auto-derived if omitted
    output_content: str = ""            # full markdown/html to re-open
    output_format: str = "markdown"     # 'markdown' | 'html'
    artifact_path: Optional[str] = None  # absolute server path for re-download
    file_type: Optional[str] = None      # e.g. 'xlsx', 'csv'
    is_sensitive: bool = False
    masked_export_available: bool = False


class HistoryItem(BaseModel):
    """One stored archive entry."""
    id: str
    tool_name: str
    title: str
    created_at: str
    language: str = ""
    input_summary: str = ""
    output_preview: str = ""
    output_content: str = ""
    output_format: str = "markdown"
    artifact_path: Optional[str] = None
    file_type: Optional[str] = None
    is_sensitive: bool = False
    masked_export_available: bool = False
