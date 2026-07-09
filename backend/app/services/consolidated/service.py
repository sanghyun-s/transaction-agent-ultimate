# backend/app/services/consolidated/service.py
# ============================================================
# Consolidated Workbook Builder (PREPARE Add-on 2).
#
# Combines multiple statement results into:
#   • a cross-statement vendor rollup (same vendor across statements -> one total),
#   • deterministic cross-statement VALIDATION (validation_engine): cross-matches,
#     combined-only $600 crossings, name-variant pairs, amount mismatches,
#     near-threshold vendors,
#   • an accountant-ready 5-sheet MASTER workbook (master_excel_generator).
#
# Reuses the shared PDF service for ingestion; runs PREPARE's chain per statement,
# then validates across statements. consolidate_rows() is the testable core;
# consolidate() adds multi-PDF ingestion. Neither raises.
# ============================================================

from __future__ import annotations

import re
import tempfile
from dataclasses import asdict
from pathlib import Path
from datetime import datetime

from .transaction_aggregator import Transaction, aggregate_by_vendor
from .vendor_normalizer import normalize_vendor
from .vendor_classifier_1099 import classify_all_vendors
from .review_flag_engine import build_flags_for_statement
from .validation_engine import run_deterministic_validation
from .master_excel_generator import generate_master_workbook


# Leading statement descriptors that aren't part of the payee. Stripped ONLY
# when followed by a separator, so real names ("Card Kingdom", "Check Point
# Software") are left intact. Complements vendor_normalizer's NOISE_PATTERNS,
# which strips inner tokens (ACH, #1234) but not these leading descriptors.
_PREFIX_NOISE = re.compile(
    r"^\s*(?:"
    r"ach\s+(?:payment|debit|credit|transfer)|"
    r"check\s*#?\s*\d*|"
    r"debit\s+card|credit\s+card|card|"
    r"customer\s+deposit(?:\s*-\s*invoice\s*\d*)?|"
    r"online\s+(?:bill\s+)?pay(?:ment)?|bill\s*pay|"
    r"wire(?:\s+transfer)?|eft|pos|electronic\s+payment|payment|deposit|withdrawal"
    r")\s*[-–:]\s*",
    re.IGNORECASE,
)


def _preclean_description(desc: str) -> str:
    """Strip leading transaction-descriptor prefixes before vendor normalization,
    so 'ACH Payment - Greenleaf Nursery' and 'Check 1022 - Greenleaf Nursery LLC'
    both canonicalize to 'Greenleaf Nursery' and merge across statements."""
    s = (desc or "").strip()
    prev = None
    while prev != s:                       # handle stacked prefixes
        prev = s
        s = _PREFIX_NOISE.sub("", s).strip()
    return s or (desc or "")               # never return empty


def _recon_to_snapshot(recon: dict) -> dict:
    """Map TAU's reconciliation block to the master workbook's snapshot shape
    (adds the `status` field the Executive Summary roll-up reads)."""
    if not recon or not recon.get("available"):
        return {"status": "unavailable"}
    return {
        "status": "balanced" if recon.get("balanced") else "needs_review",
        "beginning_balance": recon.get("beginning_balance"),
        "total_deposits": recon.get("total_deposits"),
        "total_withdrawals": recon.get("total_withdrawals"),
        "checks": recon.get("checks"),
        "transfers": recon.get("transfers"),
        "fees": recon.get("fees"),
        "reported_ending_balance": recon.get("reported_ending_balance"),
        "calculated_ending_balance": recon.get("calculated_ending"),
        "difference": recon.get("difference"),
    }


def _money(n) -> float:
    try:
        return round(float(n or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _vendor_dict(s) -> dict:
    return {
        "canonical_name": s.canonical_name,
        "entity_type": s.entity_type,
        "total_amount": _money(s.total_amount),
        "transaction_count": s.transaction_count,
        "first_payment_date": s.first_payment_date,
        "last_payment_date": s.last_payment_date,
        "match_confidence": s.match_confidence,
        "needs_review": s.needs_review,
        "review_reasons": list(s.review_reasons),
        "raw_name_variants": list(s.raw_name_variants),
    }


def _txn_for_master(row: dict, norm) -> dict:
    excluded = bool(norm.excluded or not row.get("include_for_1099", True))
    return {
        "date": row.get("date", "") or "",
        "raw_description": row.get("description", "") or "",
        "canonical_name": "" if excluded else norm.canonical_name,
        "amount": _money(row.get("amount")),
        "excluded": excluded,
        "exclusion_reason": row.get("exclusion_reason", "") or getattr(norm, "exclusion_reason", ""),
    }


def _build_transactions(rows: list[dict], vendor_list: list):
    txns, norms = [], []
    for r in rows:
        src = r.get("source", "bank")
        t = Transaction(
            date=r.get("date") or None,
            description=r.get("description", ""),
            amount=_money(r.get("amount")),
            source=src if src in ("bank", "credit_card") else "bank",
            transaction_type=r.get("transaction_type", "vendor_payment"),
            include_for_1099=bool(r.get("include_for_1099", True)),
            review_required=bool(r.get("review_required", False)),
            exclusion_reason=r.get("exclusion_reason", ""),
        )
        n = normalize_vendor(_preclean_description(t.description), vendor_list)
        txns.append(t)
        norms.append(n)
    return txns, norms


def consolidate_rows(statements: list[dict], *, vendor_list=None, engine_label="skill",
                     output_dir=None) -> dict:
    """`statements` = list of {"file", "rows", "reconciliation", "breakdown",
    "confidence", "included_total"}. rows match the shared PDF service shape."""
    vendor_list = vendor_list or []
    agent_outputs, flags_by_statement, eligibility_by_statement, filename_map = [], {}, {}, {}
    per_statement = []
    pool_txns, pool_norms, pool_src = [], [], []

    for st in statements:
        label = st.get("file", "statement.pdf")
        rows = st.get("rows", [])
        conf = float(st.get("confidence", 1.0) or 1.0)

        txns, norms = _build_transactions(rows, vendor_list)
        summaries = aggregate_by_vendor(txns, norms)              # per statement
        eligibility = classify_all_vendors(summaries)
        flags = build_flags_for_statement(summaries, extraction_confidence=conf)

        agent_outputs.append({
            "statement_label": label,
            "status": "success",
            "vendors": [_vendor_dict(s) for s in summaries],
            "transactions": [_txn_for_master(r, n) for r, n in zip(rows, norms)],
            "reconciliation": st.get("reconciliation", {}) or {},
            "reconciliation_snapshot": _recon_to_snapshot(st.get("reconciliation", {}) or {}),
            "extraction_check": st.get("extraction_check") or {"status": "unavailable"},
            "breakdown": st.get("breakdown", {}) or {},
            "extraction_confidence": conf,
            "error_message": None,
        })
        flags_by_statement[label] = flags
        eligibility_by_statement[label] = eligibility
        filename_map[label] = label

        inc = sum(1 for r in rows if r.get("include_for_1099", True))
        per_statement.append({
            "file": label, "success": True, "rows": len(rows),
            "included": inc, "excluded": len(rows) - inc,
            "included_total": _money(st.get("included_total")),
            "vendor_count": len(summaries),
            "reconciliation": st.get("reconciliation", {}) or {},
        })
        for t, n in zip(txns, norms):
            pool_txns.append(t); pool_norms.append(n); pool_src.append(label)

    # ── cross-statement validation (mutates flags_by_statement in place) ──
    validation = run_deterministic_validation(agent_outputs, flags_by_statement)

    # ── consolidated (pooled) vendor rollup for the on-screen review table ──
    pooled = aggregate_by_vendor(pool_txns, pool_norms)
    pooled_elig = classify_all_vendors(pooled)
    vendor_sources: dict[str, set] = {}
    for t, n, f in zip(pool_txns, pool_norms, pool_src):
        if n.excluded or not getattr(t, "include_for_1099", True):
            continue
        vendor_sources.setdefault(n.canonical_name, set()).add(f)

    vendors = []
    for s in pooled:
        e = pooled_elig.get(s.canonical_name)
        srcs = sorted(vendor_sources.get(s.canonical_name, []))
        vendors.append({
            "canonical_name": s.canonical_name,
            "entity_type": s.entity_type,
            "total_amount": _money(s.total_amount),
            "transaction_count": s.transaction_count,
            "statement_count": len(srcs),
            "source_statements": srcs,
            "first_payment_date": s.first_payment_date,
            "last_payment_date": s.last_payment_date,
            "form_type": e.form_type if e else "REVIEW",
            "eligible": bool(e.eligible) if e else False,
            "threshold_met": bool(e.threshold_met) if e else False,
            "needs_review": bool(s.needs_review or (e and e.form_type == "REVIEW")),
            "raw_name_variants": list(s.raw_name_variants),
            "notes": e.notes if e else "",
        })

    val = asdict(validation)   # fully JSON-serializable

    totals = {
        "vendor_count": len(vendors),
        "total_reconciled": _money(sum(v["total_amount"] for v in vendors)),
        "over_threshold": sum(1 for v in vendors if v["threshold_met"]),
        "eligible_1099": sum(1 for v in vendors if v["eligible"]),
        "needs_review": sum(1 for v in vendors if v["needs_review"]),
        "cross_statement_vendors": len(val.get("cross_matches", [])),
        "combined_only_crossings": sum(1 for c in val.get("cross_matches", []) if c.get("crosses_threshold_combined_only")),
        "name_variant_flags": len(val.get("name_variants", [])),
        "amount_mismatches": len(val.get("amount_mismatches", [])),
        "near_threshold": len(val.get("near_threshold", [])),
    }

    # ── master workbook (5 sheets) ──
    out_dir = output_dir or tempfile.gettempdir()
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx = str(Path(out_dir) / f"master_workbook_{stamp}.xlsx")
    excel_ok, excel_err, sheet_count = True, "", 0
    try:
        generate_master_workbook(
            output_path=xlsx,
            agent_outputs=agent_outputs,
            flags_by_statement=flags_by_statement,
            eligibility_by_statement=eligibility_by_statement,
            validation=validation,
            filename_map=filename_map,
        )
        import openpyxl
        wb = openpyxl.load_workbook(xlsx, read_only=True)
        sheet_count = len(wb.sheetnames)
        wb.close()
    except Exception as ex:
        excel_ok, excel_err, xlsx = False, f"{type(ex).__name__}: {ex}", ""

    return {
        "success": True,
        "engine": engine_label,
        "statements_processed": len(agent_outputs),
        "per_statement": per_statement,
        "vendors": vendors,
        "validation": val,
        "totals": totals,
        "excel_path": xlsx,
        "excel_ok": excel_ok,
        "excel_error": excel_err,
        "sheet_count": sheet_count,
        "errors": [],
    }


def consolidate(pdf_paths: list[str], *, vendor_list=None, engine="skill",
                model="sonnet", output_dir=None) -> dict:
    """Full path: ingest each PDF via the shared service, then consolidate."""
    from app.services.pdf import ingest_statement  # lazy: shared engine

    statements, errors = [], []
    for path in pdf_paths:
        fname = Path(path).name
        res = ingest_statement(path, engine=engine, model=model, source="bank")
        if not res.get("success"):
            errors.append({"file": fname, "error": res.get("error", "ingest failed")})
            continue
        statements.append({
            "file": fname,
            "rows": res.get("transactions", []),
            "included_total": res.get("included_total"),
            "reconciliation": res.get("reconciliation", {}),
            "extraction_check": res.get("extraction_check"),
            "breakdown": res.get("breakdown", {}),
            "confidence": (res.get("metadata", {}) or {}).get("confidence", 1.0),
        })

    if not statements:
        return {"success": False, "engine": engine, "error": "No statements ingested.",
                "errors": errors, "vendors": [], "per_statement": [], "validation": {}}

    result = consolidate_rows(statements, vendor_list=vendor_list,
                              engine_label=engine, output_dir=output_dir)
    result["statements_failed"] = len(errors)
    result["errors"] = errors
    return result
