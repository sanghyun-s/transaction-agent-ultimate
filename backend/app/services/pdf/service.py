# backend/app/services/pdf/service.py
# ============================================================
# Shared PDF ingestion facade for TAU.
#   engine="skill" (default) — Claude PDF Skill (Sonnet/Opus): reads + classifies
#                              each row and transcribes a reconciliation_snapshot
#                              (stated balances). ~1-4 min, ~$0.20-0.60 per PDF.
#   engine="rule"            — pdfplumber + regex + deterministic classifier.
#                              ~seconds, $0. No reconciliation_snapshot.
# Output is uniform across engines so every statement tool (1099 Worksheet,
# Statement Review, Consolidated Workbook) consumes one shape.
# ============================================================

from __future__ import annotations

from pathlib import Path

from .reconciliation import compute_reconciliation


def _txn_from_obj(t) -> dict:
    return {
        "date": getattr(t, "date", "") or "",
        "description": getattr(t, "description", "") or "",
        "amount": float(getattr(t, "amount", 0) or 0),
        "transaction_type": getattr(t, "transaction_type", "vendor_payment"),
        "include_for_1099": bool(getattr(t, "include_for_1099", True)),
        "review_required": bool(getattr(t, "review_required", False)),
        "exclusion_reason": getattr(t, "exclusion_reason", "") or "",
        "confidence": float(getattr(t, "confidence", 0.0) or 0.0),
        "source_page": int(getattr(t, "source_page", 0) or 0),
    }


def _txn_from_dict(d: dict) -> dict:
    return {
        "date": d.get("date", "") or "",
        "description": d.get("description", "") or "",
        "amount": float(d.get("amount", 0) or 0),
        "transaction_type": d.get("transaction_type", "vendor_payment"),
        "include_for_1099": bool(d.get("include_for_1099", True)),
        "review_required": bool(d.get("review_required", False)),
        "exclusion_reason": d.get("exclusion_reason", "") or "",
        "confidence": float(d.get("confidence", 0.0) or 0.0),
        "source_page": int(d.get("source_page", 0) or 0),
    }


def _summarize(txns: list[dict]) -> tuple[int, int, dict]:
    breakdown: dict[str, int] = {}
    included = 0
    for t in txns:
        breakdown[t["transaction_type"]] = breakdown.get(t["transaction_type"], 0) + 1
        if t["include_for_1099"]:
            included += 1
    return included, len(txns) - included, breakdown


def _included_total(txns: list[dict]) -> float:
    return round(sum(t["amount"] for t in txns if t["include_for_1099"]), 2)


def ingest_statement(pdf_path, *, engine: str = "skill", model: str = "sonnet", source: str = "bank") -> dict:
    """Ingest one statement PDF. Never raises — returns a dict with success flag."""
    pdf_path = str(pdf_path)
    if not Path(pdf_path).exists():
        return {"success": False, "engine": engine, "error": f"PDF not found: {pdf_path}", "transactions": []}
    return _ingest_rule(pdf_path, source) if engine == "rule" else _ingest_skill(pdf_path, model)


def _ingest_rule(pdf_path: str, source: str) -> dict:
    from .rule_extractor import extract_transactions
    from .classifier import classify_transactions
    try:
        result = extract_transactions(pdf_path, source=source)
        classify_transactions(result.transactions)  # mutates rows in place
        txns = [_txn_from_obj(t) for t in result.transactions]
        included, excluded, breakdown = _summarize(txns)
        return {
            "success": True,
            "engine": "rule",
            "extraction_method": result.extraction_method,
            "document_type": result.document_type,
            "transactions": txns,
            "included_count": included,
            "excluded_count": excluded,
            "included_total": _included_total(txns),
            "breakdown": breakdown,
            "reconciliation_snapshot": {},  # rule engine doesn't transcribe stated balances
            "reconciliation": {"available": False, "reason": "Run Full (Skill) analysis to reconcile."},
            "metadata": {"pages_processed": result.pages_processed, "confidence": result.confidence},
            "warnings": result.warnings,
            "cost_usd": 0.0,
            "agent_seconds": 0.0,
        }
    except Exception as e:
        return {"success": False, "engine": "rule", "error": f"{type(e).__name__}: {e}", "transactions": []}


def _ingest_skill(pdf_path: str, model: str) -> dict:
    from .skill_adapter import extract_from_pdf
    r = extract_from_pdf(pdf_path, model=model)
    if not r.success:
        return {
            "success": False,
            "engine": "skill",
            "error": f"{r.failure_reason}: {r.failure_details}",
            "failure_reason": r.failure_reason,
            "transactions": [],
            "cost_usd": r.cost_usd,
            "agent_seconds": r.agent_seconds,
        }
    txns = [_txn_from_dict(d) for d in r.all_transactions]
    included, excluded, breakdown = _summarize(txns)
    return {
        "success": True,
        "engine": "skill",
        "extraction_method": "pdf_skill",
        "document_type": r.metadata.get("detected_type", "unknown"),
        "transactions": txns,
        "included_count": included,
        "excluded_count": excluded,
        "included_total": _included_total(txns),
        "breakdown": breakdown or r.breakdown,
        "reconciliation_snapshot": r.reconciliation_snapshot,
        "reconciliation": compute_reconciliation(r.reconciliation_snapshot),
        "metadata": r.metadata,
        "warnings": [],
        "cost_usd": r.cost_usd,
        "agent_seconds": r.agent_seconds,
        "skill_was_used": r.skill_was_used,
    }
