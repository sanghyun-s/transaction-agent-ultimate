# backend/app/services/gl_review/anomaly.py
# ============================================================
# The "ML finds" layer of "ML finds, audit logic adjusts, GPT explains."
# An IsolationForest over the six signals produces an anomaly_score, bucketed
# into a raw_tier that the materiality cascade and qualitative override then
# adjust (scoring.py).
#
# TAU note (Option 1): the IsolationForest is KEPT — it is LUCENT's core
# unsupervised thesis. The Phase-3 supervised RandomForest layer is DROPPED:
# it needs a `label` column that GL exports don't carry, so it self-skips to
# fraud_probability = 0 anyway, and carrying it would add training machinery
# the compact tool never exercises.
# ============================================================

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from .features import FEATURE_COLS

# Detection sensitivity -> IsolationForest contamination. In audit terms, the
# reviewer-controlled Detection Risk dial.
SENSITIVITY_MAP: dict[str, float] = {
    "Conservative (0.03)": 0.03,
    "Balanced (0.05)": 0.05,
    "Aggressive (0.10)": 0.10,
}
DEFAULT_SENSITIVITY = "Balanced (0.05)"

# raw_tier binning.
#
# LUCENT shipped fixed score cutoffs ([-inf, -0.15, -0.05, inf]) with an
# explicit note to "adjust after testing with real sample GL data if the
# distribution skews." Testing against a realistic 465-row GL confirmed the
# skew: 459 of 465 rows landed in Low, so the IsolationForest barely
# differentiated tiers and only the qualitative override produced High rows.
#
# So the tiers are cut by QUANTILE of the anomaly score instead. This ties the
# tier spread to the contamination dial the reviewer already sets: the most
# anomalous `contamination` share becomes High, the next band Medium, the rest
# Low. Same model, same scores, same ordering — only the bucketing changes, and
# the sensitivity setting now visibly drives the queue.
MEDIUM_BAND_MULTIPLE: float = 3.0   # Medium band = contamination x this
RAW_TIER_LABELS: list[str] = ["High", "Medium", "Low"]


def _quantile_tiers(scores: "pd.Series", contamination: float) -> "pd.Series":
    """Assign High/Medium/Low by percentile of anomaly_score (lower = more
    anomalous). High = most-anomalous `contamination` fraction."""
    high_q = contamination
    med_q = min(contamination * (1.0 + MEDIUM_BAND_MULTIPLE), 0.95)
    high_cut = scores.quantile(high_q)
    med_cut = scores.quantile(med_q)
    return pd.Series(
        np.where(scores <= high_cut, "High",
                 np.where(scores <= med_cut, "Medium", "Low")),
        index=scores.index,
    )


def run_isolation_forest(
    df: pd.DataFrame,
    detection_sensitivity: str = DEFAULT_SENSITIVITY,
    random_state: int = 42,
) -> pd.DataFrame:
    """Fit IsolationForest on the six signals; add anomaly_score + raw_tier.
    Sorted ascending by anomaly_score (most anomalous first)."""
    if detection_sensitivity not in SENSITIVITY_MAP:
        detection_sensitivity = DEFAULT_SENSITIVITY
    contamination = SENSITIVITY_MAP[detection_sensitivity]

    df = df.copy()
    X = df[FEATURE_COLS].fillna(0).values

    # StandardScaler is non-negotiable: without it the dollar-scale z-score
    # dominates the binary flags in the tree splits.
    X_scaled = StandardScaler().fit_transform(X)

    model = IsolationForest(
        n_estimators=200, contamination=contamination, random_state=random_state,
    )
    model.fit(X_scaled)
    df["anomaly_score"] = model.decision_function(X_scaled)   # lower = more anomalous
    df["anomaly_label"] = model.predict(X_scaled)             # -1 anomaly, 1 normal
    df["raw_tier"] = _quantile_tiers(df["anomaly_score"], contamination)

    return df.sort_values("anomaly_score", ascending=True).reset_index(drop=True)
