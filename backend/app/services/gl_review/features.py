# backend/app/services/gl_review/features.py
# ============================================================
# The six LUCENT review signals, ported faithfully from the standalone app.
# Pure pandas/numpy — no ML here (that's anomaly.py). Each signal maps to a
# recognized audit red flag (see anchors.py for the standards grounding).
#
# TAU note: LUCENT required account_code; the compact add-on relaxes it to
# OPTIONAL so a lean GL export (date, amount, account_name, vendor,
# description, journal_ref) runs without it.
# ============================================================

from __future__ import annotations

import pandas as pd

# TAU-relaxed required set (account_code moved to optional).
REQUIRED_COLUMNS: list[str] = [
    "date", "amount", "account_name", "vendor", "description", "journal_ref",
]
OPTIONAL_COLUMNS: list[str] = [
    "account_code", "debit_amount", "credit_amount", "dr_cr_pattern",
    "department", "location", "preparer", "approver",
]

APPROVAL_THRESHOLDS: list[int] = [5000, 10000, 25000]

# Feature matrix for the IsolationForest (anomaly.py).
FEATURE_COLS: list[str] = [
    "amount_zscore_by_account",
    "is_round_number",
    "is_weekend_posting",
    "missing_description",
    "is_new_vendor",
    "is_near_approval_threshold",
]

# The five binary indicators that count toward fraud_flag_count. The z-score is
# deliberately excluded (it is statistical, not a discrete red flag) — this
# mirrors LUCENT and the Study Reference note.
FRAUD_FLAG_COLS: list[str] = [
    "is_round_number",
    "is_weekend_posting",
    "missing_description",
    "is_new_vendor",
    "is_near_approval_threshold",
]

FLAG_LABELS: dict[str, str] = {
    "is_round_number": "Round number amount",
    "is_weekend_posting": "Weekend posting",
    "missing_description": "Missing description",
    "is_new_vendor": "New vendor",
    "is_near_approval_threshold": "Near approval threshold",
}


def validate_required_columns(df: pd.DataFrame) -> tuple[bool, list[str]]:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    return (len(missing) == 0, missing)


def clean_gl_data(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce dtypes and add abs_amount. Does not mutate input."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["abs_amount"] = df["amount"].abs()

    for col in ("debit_amount", "credit_amount"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    for col in ("vendor", "description", "account_name", "account_code"):
        if col in df.columns:
            df[col] = df[col].astype("string")
    return df


def _is_round_number(amount: float) -> int:
    if pd.isna(amount):
        return 0
    return int(abs(amount) % 100 == 0)


def _near_approval_threshold(amount: float) -> int:
    if pd.isna(amount):
        return 0
    amount = abs(amount)
    for threshold in APPROVAL_THRESHOLDS:
        if threshold * 0.95 <= amount < threshold:
            return 1
    return 0


def _amount_zscore_by_account(df: pd.DataFrame) -> pd.Series:
    def _z(group: pd.Series) -> pd.Series:
        std = group.std(ddof=0)
        if std == 0 or pd.isna(std):
            return pd.Series(0.0, index=group.index)
        return (group - group.mean()) / std
    return df.groupby("account_name", group_keys=False)["abs_amount"].apply(_z)


def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Add the six signals plus fraud_flag_count / fraud_risk_flag (the
    qualitative-override trigger, which fires at >= 2 discrete flags)."""
    df = df.copy()
    df["amount_zscore_by_account"] = _amount_zscore_by_account(df)
    df["is_round_number"] = df["abs_amount"].apply(_is_round_number).astype(int)
    df["is_weekend_posting"] = df["date"].dt.weekday.isin([5, 6]).astype(int)
    df["missing_description"] = (
        df["description"].isna()
        | (df["description"].astype(str).str.strip() == "")
        | (df["description"].astype(str).str.strip().str.lower() == "nan")
    ).astype(int)

    vendor_counts = df["vendor"].fillna("UNKNOWN").value_counts()
    df["vendor_txn_count"] = df["vendor"].fillna("UNKNOWN").map(vendor_counts)
    df["is_new_vendor"] = (df["vendor_txn_count"] < 3).astype(int)

    df["is_near_approval_threshold"] = df["abs_amount"].apply(_near_approval_threshold).astype(int)

    df["control_gap_score"] = (
        df["missing_description"].astype(int) + df["is_weekend_posting"].astype(int)
    )
    df["fraud_flag_count"] = df[FRAUD_FLAG_COLS].sum(axis=1).astype(int)
    df["fraud_risk_flag"] = (df["fraud_flag_count"] >= 2).astype(int)
    return df
