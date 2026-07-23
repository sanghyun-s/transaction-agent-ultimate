# backend/app/services/gl_review/scoring.py
# ============================================================
# The "audit logic adjusts" layer. Two moves, applied to the IsolationForest's
# raw_tier:
#   1. Materiality cascade — quantitative severity by dollar amount.
#        amount >= transaction_materiality  -> keep raw_tier
#        amount >= performance_materiality  -> downgrade one tier
#        amount <  performance_materiality  -> force Monitor
#   2. Qualitative override — when >= 2 discrete red flags co-occur, the item
#      matters regardless of amount (co-occurrence signals a possible control
#      breakdown), so escalate one tier ABOVE the raw ML tier.
#
# TAU note (Option 1): the Phase-3 supervised escalation (fraud_probability
# nudge) is DROPPED with the RandomForest layer. The two moves above are the
# faithful deterministic heart of LUCENT's scoring.
# ============================================================

from __future__ import annotations

import pandas as pd

TIER_ORDER: list[str] = ["Monitor", "Low", "Medium", "High"]

PCAOB_LABELS: dict[str, str] = {
    "High":    "Potential Material Weakness Indicator",
    "Medium":  "Potential Significant Deficiency",
    "Low":     "Monitor — Below Escalation Threshold",
    "Monitor": "Monitor — Below Escalation Threshold",
}

FLAG_LABELS: dict[str, str] = {
    "is_round_number":            "Round number amount",
    "is_weekend_posting":         "Weekend posting",
    "missing_description":        "Missing description",
    "is_new_vendor":              "New vendor",
    "is_near_approval_threshold": "Near approval threshold",
}


def downgrade_tier(tier: str, steps: int = 1) -> str:
    if tier not in TIER_ORDER:
        return "Monitor"
    return TIER_ORDER[max(0, TIER_ORDER.index(tier) - steps)]


def upgrade_tier(tier: str, steps: int = 1) -> str:
    if tier not in TIER_ORDER:
        return tier
    return TIER_ORDER[min(len(TIER_ORDER) - 1, TIER_ORDER.index(tier) + steps)]


def apply_materiality_filter(row: pd.Series, performance_materiality: float,
                             transaction_materiality: float) -> str:
    raw_tier = str(row.get("raw_tier", "Low"))
    amount = row.get("abs_amount", 0) or 0
    if amount >= transaction_materiality:
        return raw_tier
    if amount >= performance_materiality:
        return downgrade_tier(raw_tier, steps=1)
    return "Monitor"


def get_materiality_annotation(amount: float, performance_materiality: float,
                               transaction_materiality: float) -> str:
    if pd.isna(amount):
        amount = 0
    if amount >= transaction_materiality:
        return "Exceeds Transaction Materiality"
    if amount >= performance_materiality:
        return "Below Transaction Materiality"
    return "Below Performance Materiality"


def get_active_flags(row: pd.Series) -> str:
    """Semicolon-joined human-readable list of which signals fired."""
    flags: list[str] = []
    z = row.get("amount_zscore_by_account", 0)
    try:
        if abs(float(z)) >= 2.0:
            flags.append("Unusual amount for account")
    except (TypeError, ValueError):
        pass
    for col, label in FLAG_LABELS.items():
        try:
            if int(row.get(col, 0) or 0) == 1:
                flags.append(label)
        except (TypeError, ValueError):
            continue
    return "; ".join(flags) if flags else "Statistical anomaly only"


def apply_qualitative_override(row: pd.Series) -> tuple[str, int, str]:
    """>= 2 red flags co-occur -> escalate one tier above raw_tier (undoing any
    materiality downgrade). Returns (resolved_tier, is_override, note)."""
    final_tier = str(row.get("final_tier", "Monitor"))
    if int(row.get("fraud_risk_flag", 0) or 0) != 1:
        return final_tier, 0, ""

    raw_tier = str(row.get("raw_tier", "Low"))
    escalated = upgrade_tier(raw_tier, steps=1)
    if TIER_ORDER.index(escalated) <= TIER_ORDER.index(final_tier):
        return final_tier, 0, ""

    fraud_count = int(row.get("fraud_flag_count", 0) or 0)
    note = (
        f"Escalated to {escalated}: {fraud_count} indicators co-occur "
        f"(qualitative materiality). Raw tier {raw_tier}; materiality alone "
        f"would assign {final_tier}."
    )
    return escalated, 1, note


def score_dataframe(df: pd.DataFrame, performance_materiality: float,
                    transaction_materiality: float) -> pd.DataFrame:
    """Apply both moves across the frame. Adds final_tier, pcaob_label,
    materiality_annotation, active_flags, is_qualitative_override,
    qualitative_override_note, flagged_status."""
    df = df.copy()
    df["final_tier"] = df.apply(
        lambda r: apply_materiality_filter(r, performance_materiality, transaction_materiality),
        axis=1)
    df["materiality_annotation"] = df["abs_amount"].apply(
        lambda a: get_materiality_annotation(a, performance_materiality, transaction_materiality))
    df["active_flags"] = df.apply(get_active_flags, axis=1)

    overrides = df.apply(apply_qualitative_override, axis=1, result_type="expand")
    df["final_tier"] = overrides[0]
    df["is_qualitative_override"] = overrides[1]
    df["qualitative_override_note"] = overrides[2]

    df["pcaob_label"] = df["final_tier"].map(PCAOB_LABELS).fillna("Monitor — Below Escalation Threshold")
    df["flagged_status"] = df["final_tier"].apply(
        lambda t: "Flagged" if t in ("High", "Medium") else "Not flagged")
    return df
