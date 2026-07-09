# backend/app/services/pdf/source_b.py
# ============================================================
# Source B — extraction-completeness cross-check (companion to Source A).
# Source A (reconciliation.py) asks "does the statement's stated math balance?"
# Source B asks "do the EXTRACTED rows sum to the statement's stated activity
# totals?" — catching missed/miscounted rows during extraction.
#
# Ported from PREPARE's pipeline._compute_source_b. Same bucketing, same 0.01
# tolerance, same arithmetic-in-one-place discipline. Adapted to TAU's
# reconciliation block: TAU emits `available: true` + stated totals exactly
# when PREPARE would set `extraction_complete: true`, so `available` is the
# gate here.
# ============================================================

from __future__ import annotations

_TOLERANCE = 0.01

# transaction_type -> activity bucket. Verified against the Skill engine's
# emitted vocabulary (pdf_skill_prompt.md). Types not listed (payroll_deposit,
# balance_line, metadata, unknown) don't represent account-summary activity.
_BUCKET_MAP = {
    "deposit": "deposits",
    "interest": "deposits",
    "reimbursement": "deposits",
    "vendor_payment": "withdrawals",
    "check_payment": "checks",
    "transfer": "transfers",
    "owner_draw": "transfers",
    "bank_fee": "fees",
}


def _row_type(t) -> str | None:
    if isinstance(t, dict):
        return t.get("transaction_type")
    return getattr(t, "transaction_type", None)


def _row_amount(t) -> float:
    v = t.get("amount") if isinstance(t, dict) else getattr(t, "amount", 0)
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def compute_source_b(transactions: list, reconciliation: dict, raw_snapshot: dict | None = None) -> dict:
    """Bucket extracted rows by transaction_type and compare to the stated
    activity totals in TAU's reconciliation block.

    `raw_snapshot` is the Skill's untouched reconciliation_snapshot (where an
    absent checks/transfers/fees line is None, not coerced to 0.0). It's used
    only to detect the lumped-debits case; pass None to disable that detection.

    Status:
      complete    — reconciliation available AND every bucket delta within tolerance
      incomplete  — reconciliation available but a bucket delta exceeds tolerance
      unavailable — no reconciliation (rule engine, or Skill found no summary)
    """
    row_sums = {"deposits": 0.0, "withdrawals": 0.0, "checks": 0.0,
                "transfers": 0.0, "fees": 0.0}
    for t in transactions or []:
        bucket = _BUCKET_MAP.get(_row_type(t))
        if bucket is None:
            continue
        row_sums[bucket] += _row_amount(t)
    row_sums = {k: round(v, 2) for k, v in row_sums.items()}

    available = bool(reconciliation and reconciliation.get("available"))
    if not available:
        return {
            "status": "unavailable",
            "deposits_stated": None, "deposits_row_sum": row_sums["deposits"], "deposits_delta": None,
            "withdrawals_stated": None, "withdrawals_row_sum": row_sums["withdrawals"], "withdrawals_delta": None,
            "checks_stated": None, "checks_row_sum": row_sums["checks"], "checks_delta": None,
            "transfers_stated": None, "transfers_row_sum": row_sums["transfers"], "transfers_delta": None,
            "fees_stated": None, "fees_row_sum": row_sums["fees"], "fees_delta": None,
            "notes": None,
        }

    def _stated(key):
        v = reconciliation.get(key)
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    stated = {
        "deposits": _stated("total_deposits"),
        "withdrawals": _stated("total_withdrawals"),
        "checks": _stated("checks"),
        "transfers": _stated("transfers"),
        "fees": _stated("fees"),
    }

    # ── TAU adaptation (not in PREPARE's verbatim Source B) ──
    # PREPARE assumes the statement breaks out withdrawals / checks / transfers /
    # fees as separate stated lines. Many statements instead LUMP every debit into
    # a single "Total Withdrawals & Debits" figure. Detect that — total_withdrawals
    # present while checks/transfers/fees are NOT separately stated — and compare
    # the COMBINED debit row-sum against the lumped total, so a correctly-extracted
    # lumped statement reads "complete" instead of false-alarming "incomplete".
    #
    # "Not separately stated" = None OR 0.0: the Skill sometimes fills these with 0
    # (rather than null) when it recognizes there's no broken-out line, so we treat
    # both the same. This also correctly models completeness — when a category has
    # no separate stated total, the meaningful check is "did we capture all the
    # money?" (combined debits), not "did our internal bucketing match the bank's?".
    def _absent(v):
        return v is None or abs(v) <= _TOLERANCE

    lumped = (
        stated["withdrawals"] is not None
        and _absent(stated["checks"])
        and _absent(stated["transfers"])
        and _absent(stated["fees"])
    )
    if lumped:
        combined_debits = round(
            row_sums["withdrawals"] + row_sums["checks"]
            + row_sums["transfers"] + row_sums["fees"], 2
        )
        wd_delta = round(combined_debits - stated["withdrawals"], 2)
        dep_delta = (
            None if stated["deposits"] is None and abs(row_sums["deposits"]) <= _TOLERANCE
            else round(row_sums["deposits"] - (stated["deposits"] or 0.0), 2)
        )
        any_mismatch = abs(wd_delta) > _TOLERANCE or (dep_delta is not None and abs(dep_delta) > _TOLERANCE)
        return {
            "status": "incomplete" if any_mismatch else "complete",
            "lumped_debits": True,
            "deposits_stated": stated["deposits"], "deposits_row_sum": row_sums["deposits"], "deposits_delta": dep_delta,
            "withdrawals_stated": stated["withdrawals"], "withdrawals_row_sum": combined_debits, "withdrawals_delta": wd_delta,
            "checks_stated": None, "checks_row_sum": row_sums["checks"], "checks_delta": None,
            "transfers_stated": None, "transfers_row_sum": row_sums["transfers"], "transfers_delta": None,
            "fees_stated": None, "fees_row_sum": row_sums["fees"], "fees_delta": None,
            "notes": "Statement lumps all debits into one total; compared combined debit rows against it.",
        }

    deltas, any_mismatch = {}, False
    for k in ("deposits", "withdrawals", "checks", "transfers", "fees"):
        rs, st = row_sums[k], stated[k]
        if st is None:
            if abs(rs) <= _TOLERANCE:
                deltas[k] = None            # genuinely-absent section — fine
            else:
                deltas[k] = round(rs, 2)    # rows exist but statement didn't summarize
                any_mismatch = True
        else:
            d = round(rs - st, 2)
            deltas[k] = d
            if abs(d) > _TOLERANCE:
                any_mismatch = True

    return {
        "status": "incomplete" if any_mismatch else "complete",
        "deposits_stated": stated["deposits"], "deposits_row_sum": row_sums["deposits"], "deposits_delta": deltas["deposits"],
        "withdrawals_stated": stated["withdrawals"], "withdrawals_row_sum": row_sums["withdrawals"], "withdrawals_delta": deltas["withdrawals"],
        "checks_stated": stated["checks"], "checks_row_sum": row_sums["checks"], "checks_delta": deltas["checks"],
        "transfers_stated": stated["transfers"], "transfers_row_sum": row_sums["transfers"], "transfers_delta": deltas["transfers"],
        "fees_stated": stated["fees"], "fees_row_sum": row_sums["fees"], "fees_delta": deltas["fees"],
        "notes": None,
    }
