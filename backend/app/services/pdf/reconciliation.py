# backend/app/services/pdf/reconciliation.py
# ============================================================
# Source-A reconciliation: "does the statement's OWN stated math balance?"
# The PDF Skill transcribes the account-summary figures AS STATED into the
# reconciliation_snapshot; THIS module does the arithmetic. The model never
# computes — it only transcribes — so it can't quietly nudge numbers to balance.
# (Source-B — did we extract every row the statement reported? — is added later
#  with PREPARE's validation_engine.)
# ============================================================

from __future__ import annotations

_TOLERANCE = 0.01


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def compute_reconciliation(snapshot: dict) -> dict:
    """Deterministic reconciliation from a stated-figures snapshot.

    calculated_ending = beginning + deposits - withdrawals - checks - transfers - fees
    Fields the statement doesn't break out separately arrive as 0, so a statement
    that lumps everything into one 'total_withdrawals' line still balances.
    """
    if not snapshot:
        return {"available": False, "reason": "No reconciliation snapshot (use the Skill engine)."}

    beginning = _num(snapshot.get("beginning_balance", snapshot.get("beginning")))
    deposits = _num(snapshot.get("total_deposits", snapshot.get("deposits")))
    withdrawals = _num(snapshot.get("total_withdrawals", snapshot.get("withdrawals")))
    checks = _num(snapshot.get("checks")) or 0.0
    transfers = _num(snapshot.get("transfers")) or 0.0
    fees = _num(snapshot.get("fees")) or 0.0
    reported = _num(snapshot.get("reported_ending_balance", snapshot.get("ending_balance")))

    if any(v is None for v in (beginning, deposits, withdrawals, reported)):
        return {
            "available": False,
            "reason": "Statement did not report all four figures needed to reconcile.",
            "beginning_balance": beginning,
            "total_deposits": deposits,
            "total_withdrawals": withdrawals,
            "reported_ending_balance": reported,
        }

    calculated = round(beginning + deposits - withdrawals - checks - transfers - fees, 2)
    difference = round(calculated - reported, 2)
    return {
        "available": True,
        "beginning_balance": beginning,
        "total_deposits": deposits,
        "total_withdrawals": withdrawals,
        "checks": checks,
        "transfers": transfers,
        "fees": fees,
        "calculated_ending": calculated,
        "reported_ending_balance": reported,
        "difference": difference,
        "balanced": abs(difference) <= _TOLERANCE,
        "notes": snapshot.get("notes", ""),
    }
