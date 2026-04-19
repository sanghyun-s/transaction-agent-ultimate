"""
File Analysis Schemas
---------------------
Pydantic models for file upload and analysis responses.
Add these to your existing schemas.py file.
"""

from pydantic import BaseModel
from typing import Optional


class FileAnalysisResponse(BaseModel):
    success: bool
    filename: str
    row_count: int
    columns: list[str]
    preview: list[dict]          # First 50 rows as list of dicts
    summary: dict                # Statistical summary
    gpt_analysis: Optional[str] = None  # GPT's written analysis
    error: Optional[str] = None
