"""
Reconciliation Schemas
----------------------
Pydantic models for the 1099 pre-reconciliation feature.
Matches the pattern of file_schemas.py — each feature has its own schema file.
"""

from pydantic import BaseModel
from typing import Optional


class ReconciliationResponse(BaseModel):
    """Response from /api/reconcile/rule-based and /api/reconcile/agent"""
    success: bool
    mode: str = ""                         # "rule-based" or "agent"
    file_id: str = ""                      # Used to download: /api/reconcile/download/{file_id}
    transaction_count: int = 0
    vendor_count: int = 0
    total_amount: float = 0.0
    vendors_over_600: int = 0
    vendors_needing_review: int = 0
    extraction_method: str = ""
    warnings: list[str] = []
    vendor_preview: list[dict] = []        # Vendor summary rows for UI rendering
    agent_summary: Optional[str] = None    # Claude's natural-language summary (agent mode only)
    agent_cost_usd: float = 0.0
    agent_tool_calls: int = 0
    model: Optional[str] = None
    error: Optional[str] = None
