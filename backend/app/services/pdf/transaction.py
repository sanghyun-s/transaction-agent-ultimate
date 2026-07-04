# backend/app/services/pdf/transaction.py
# ============================================================
# The shared row contract produced by BOTH ingestion engines
# (rule extractor + PDF Skill adapter). Extracted from PREPARE's
# transaction_aggregator so the ingestion layer carries no
# aggregation/normalization dependency — vendor grouping and 1099
# eligibility live in the PREPARE add-ons that consume this.
# ============================================================

from dataclasses import dataclass
from typing import Optional


@dataclass
class Transaction:
    """A single line item from a bank or credit card statement."""
    date: Optional[str]
    description: str
    amount: float
    source: str = "bank"            # "bank" | "credit_card"

    # Classifier-populated fields (set by classifier.classify_transactions,
    # or by the PDF Skill directly).
    transaction_type: str = "vendor_payment"
    include_for_1099: bool = True
    review_required: bool = False
    exclusion_reason: str = ""
