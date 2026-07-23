# backend/app/services/gl_review/anchors.py
# ============================================================
# Section 5 audit-standards anchor map (from the LUCENT Study Reference).
# Each signal and each scoring move traces to a real audit-standard source.
# This is what makes the evidence memo an AUDIT memo rather than a generic
# file summary — it grounds every flag in a recognized red-flag category.
#
# THE FRAMING RULE (governs how these are used in the memo):
#   LUCENT is *anchored* to these standards — designed with their intent in
#   mind. It does NOT implement or perform the procedures they define.
# So the memo cites an anchor as DESIGN RATIONALE ("the round-number flag is
# designed around AS 2401's manual-entry/estimate red flag"), never as a
# compliance finding, a procedure performed, or a fraud conclusion.
# ============================================================

from __future__ import annotations

# signal key -> (standard source, plain-English rationale, evidence hint)
SIGNAL_ANCHORS: dict[str, dict[str, str]] = {
    "amount_zscore_by_account": {
        "source": "AU-C 315 (analytical review procedures)",
        "rationale": "the amount is far from what is normal for this specific account — an analytical-review outlier",
        "evidence": "the supporting documentation explaining why this account carries an amount of this size",
    },
    "is_round_number": {
        "source": "PCAOB AS 2401 (fraud risk factors)",
        "rationale": "a clean, cents-free figure more often reflects a manual entry, estimate, or placeholder than an invoice-driven amount",
        "evidence": "the underlying invoice or calculation that produced the exact figure",
    },
    "is_weekend_posting": {
        "source": "COSO — Control Activities",
        "rationale": "a posting dated outside normal business days is an unusual-timing indicator",
        "evidence": "confirmation of who posted it and why it was recorded on a non-business day",
    },
    "missing_description": {
        "source": "COSO — Information & Communication",
        "rationale": "an entry with no memo is a documentation control gap",
        "evidence": "the business purpose and supporting narrative for the entry",
    },
    "is_new_vendor": {
        "source": "PCAOB AS 2401 (fraud risk factors — misappropriation opportunity)",
        "rationale": "a rare or first-time payee is where misappropriation opportunity tends to concentrate",
        "evidence": "vendor onboarding records — W-9, approval, and validation of the payee",
    },
    "is_near_approval_threshold": {
        "source": "IT / limit controls (invoice-splitting tests)",
        "rationale": "an amount sitting just under an approval limit can indicate structuring to avoid a higher approval tier",
        "evidence": "the approval trail and any related transactions to the same payee near the same date",
    },
}

# scoring move -> (source, rationale) for the AI Review Packet memo
MOVE_ANCHORS: dict[str, dict[str, str]] = {
    "materiality_filter": {
        "source": "PCAOB AS 2201 (legacy AS 5)",
        "rationale": "quantitative severity — dollar size sets the initial review floor",
    },
    "qualitative_override": {
        "source": "PCAOB AS 2401 + AS 2201 (legacy AS 5)",
        "rationale": "when two or more indicators co-occur, the item is material regardless of amount because co-occurrence signals a possible control breakdown",
    },
}

# The framing sentence injected into every prompt as a hard constraint.
FRAMING_RULE = (
    "These standards are DESIGN RATIONALE only. State that a signal is "
    "*designed around* a standard's intent; never state that a procedure was "
    "performed, that a standard was applied or violated, or that a finding is "
    "a compliance result. Never conclude fraud or issue an audit opinion."
)


def anchors_for_flags(active_flag_keys: list[str]) -> list[dict[str, str]]:
    """Return the anchor entries for the signal keys that fired on a row."""
    return [
        {"signal": k, **SIGNAL_ANCHORS[k]}
        for k in active_flag_keys if k in SIGNAL_ANCHORS
    ]
