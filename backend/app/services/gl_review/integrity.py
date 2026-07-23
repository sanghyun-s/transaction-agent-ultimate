"""
integrity.py — pre-analysis data integrity checks for the GL.

Runs four audit-grade integrity checks on a cleaned GL dataframe:

  1. Hash total          — sum of abs(amount) matches sum of (debit + credit)
  2. Cross-footing       — total debits equal total credits
  3. Date in period      — all transaction dates fall within auditor-specified
                           [period_start, period_end] window
  4. Orphan accounts     — account_name / account_code mapping is 1:1 (a code
                           shouldn't show two different names; a name shouldn't
                           have two different codes)

Behavior: returns a structured list of `Finding` records. App.py decides how
to display them. Convention is warn-and-continue: integrity checks never
block the ML pipeline, they surface to the user as advisory information.

The checks operate on the CLEANED dataframe (after clean_gl_data), so date
and amount are already coerced to proper dtypes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Finding record — a single check outcome
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    name: str           # short identifier, e.g. "Hash total"
    status: str         # "Pass" | "Warning" | "Fail"
    summary: str        # one-line user-facing summary
    detail: dict[str, Any] = field(default_factory=dict)  # numeric backing data


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_hash_total(df: pd.DataFrame, tol: float = 0.01) -> Finding:
    """If debit/credit columns exist, the sum of debits + credits should equal
    the sum of abs(amount). Falls back to Pass when columns are absent."""
    if not {"debit_amount", "credit_amount"}.issubset(df.columns):
        return Finding(
            name="Hash total",
            status="Pass",
            summary="Hash-total check skipped (no debit_amount / credit_amount columns).",
        )
    sum_abs = float(df["amount"].abs().sum())
    sum_dc = float(df["debit_amount"].sum() + df["credit_amount"].sum())
    diff = abs(sum_abs - sum_dc)
    ok = diff <= tol
    return Finding(
        name="Hash total",
        status="Pass" if ok else "Warning",
        summary=(
            f"Σ|amount| = ${sum_abs:,.2f}; Σ(debit+credit) = ${sum_dc:,.2f}; "
            f"diff = ${diff:,.2f}."
        ),
        detail={"sum_abs": sum_abs, "sum_dc": sum_dc, "diff": diff},
    )


def check_cross_footing(df: pd.DataFrame, tol: float = 0.01) -> Finding:
    """Total debits should equal total credits in a balanced GL. Falls back to
    Pass when the columns aren't available."""
    if not {"debit_amount", "credit_amount"}.issubset(df.columns):
        return Finding(
            name="Cross-footing",
            status="Pass",
            summary="Cross-footing check skipped (no debit_amount / credit_amount columns).",
        )
    sum_d = float(df["debit_amount"].sum())
    sum_c = float(df["credit_amount"].sum())
    diff = abs(sum_d - sum_c)
    ok = diff <= tol
    pct = (diff / max(sum_d, 1.0)) * 100
    return Finding(
        name="Cross-footing",
        status="Pass" if ok else "Warning",
        summary=(
            f"ΣDebit = ${sum_d:,.2f}; ΣCredit = ${sum_c:,.2f}; "
            f"diff = ${diff:,.2f} ({pct:.2f}%)."
        ),
        detail={"sum_d": sum_d, "sum_c": sum_c, "diff": diff, "pct": pct},
    )


def check_date_in_period(
    df: pd.DataFrame,
    period_start: date | None,
    period_end: date | None,
) -> Finding:
    """All rows should have dates in [period_start, period_end]."""
    if period_start is None or period_end is None:
        return Finding(
            name="Date in period",
            status="Pass",
            summary="Period bounds not provided — check skipped.",
        )

    ps = pd.Timestamp(period_start)
    pe = pd.Timestamp(period_end)
    dates = df["date"]
    n_total = int(dates.notna().sum())
    n_oob = int(((dates < ps) | (dates > pe)).sum())
    n_null = int(dates.isna().sum())

    status = "Pass" if (n_oob == 0 and n_null == 0) else "Warning"
    parts = [f"{n_oob} of {n_total} rows fall outside "
             f"[{period_start.isoformat()} .. {period_end.isoformat()}]"]
    if n_null:
        parts.append(f"{n_null} rows have an unparseable date")
    return Finding(
        name="Date in period",
        status=status,
        summary="; ".join(parts) + ".",
        detail={
            "n_total": n_total,
            "n_out_of_bounds": n_oob,
            "n_null": n_null,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        },
    )


def check_orphan_accounts(df: pd.DataFrame) -> Finding:
    """A code should map to exactly one name and vice versa. Multiple mappings
    indicate a chart-of-accounts inconsistency."""
    if not {"account_code", "account_name"}.issubset(df.columns):
        return Finding(
            name="Account mapping",
            status="Pass",
            summary="Account mapping check skipped (columns missing).",
        )
    code_to_names = df.groupby("account_code")["account_name"].nunique()
    name_to_codes = df.groupby("account_name")["account_code"].nunique()
    bad_codes = code_to_names[code_to_names > 1].index.tolist()
    bad_names = name_to_codes[name_to_codes > 1].index.tolist()
    ok = not bad_codes and not bad_names
    parts = []
    if bad_codes:
        parts.append(f"{len(bad_codes)} account_code(s) map to multiple names "
                     f"(e.g. {bad_codes[:3]})")
    if bad_names:
        parts.append(f"{len(bad_names)} account_name(s) map to multiple codes "
                     f"(e.g. {bad_names[:3]})")
    return Finding(
        name="Account mapping",
        status="Pass" if ok else "Warning",
        summary="Account code ↔ name mapping is consistent."
                if ok else "; ".join(parts) + ".",
        detail={"bad_codes": bad_codes, "bad_names": bad_names},
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_integrity_checks(
    df: pd.DataFrame,
    period_start: date | None = None,
    period_end: date | None = None,
) -> list[Finding]:
    """Run all integrity checks and return findings in display order."""
    return [
        check_hash_total(df),
        check_cross_footing(df),
        check_date_in_period(df, period_start, period_end),
        check_orphan_accounts(df),
    ]


def summarize_findings(findings: list[Finding]) -> dict[str, int]:
    """Convenience: counts by status for header display."""
    counts = {"Pass": 0, "Warning": 0, "Fail": 0}
    for f in findings:
        counts[f.status] = counts.get(f.status, 0) + 1
    return counts
