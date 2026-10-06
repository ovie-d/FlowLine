"""Leakage diagnostics: does a feature's missingness (or value) reveal the class?

A pre-event feature should not be filled *because of* what went wrong. If the
missing-indicator of a column is strongly associated with the hazard class,
the column was recorded conditional on the outcome and must not be a feature.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Bias-corrected Cramér's V thresholds for the missing-indicator vs class.
LEAK_V = 0.20
CAUTION_V = 0.10


def cramers_v(x: pd.Series, y: pd.Series) -> float:
    """Bias-corrected Cramér's V (Bergsma 2013) between two categorical series."""
    table = pd.crosstab(x, y).to_numpy(dtype=float)
    n = table.sum()
    r, k = table.shape
    if n == 0 or r < 2 or k < 2:
        return 0.0
    expected = table.sum(1, keepdims=True) @ table.sum(0, keepdims=True) / n
    chi2 = float(((table - expected) ** 2 / expected).sum())
    phi2 = max(0.0, chi2 / n - (k - 1) * (r - 1) / (n - 1))
    r_c = r - (r - 1) ** 2 / (n - 1)
    k_c = k - (k - 1) ** 2 / (n - 1)
    denom = min(r_c - 1, k_c - 1)
    return float(np.sqrt(phi2 / denom)) if denom > 0 else 0.0


def missing_rate_by_class(values: pd.Series, y: pd.Series) -> pd.Series:
    return values.isna().groupby(y).mean()


def leakage_verdict(missing_v: float, overall_missing: float) -> str:
    if overall_missing == 0:
        return "ok (always filled)"
    if missing_v >= LEAK_V:
        return "LEAKS via missingness"
    if missing_v >= CAUTION_V:
        return "caution"
    return "ok"


def leakage_row(values: pd.Series, y: pd.Series) -> dict[str, object]:
    """Summary stats for one candidate feature against class labels `y`."""
    missing = values.isna()
    by_class = missing_rate_by_class(values, y)
    miss_v = cramers_v(missing, y) if missing.any() else 0.0
    filled = ~missing
    value_v = (
        cramers_v(values[filled].astype(str), y[filled]) if filled.sum() > 1 else 0.0
    )
    return {
        "missing": float(missing.mean()),
        "missing_min": float(by_class.min()),
        "missing_max": float(by_class.max()),
        "missing_max_class": str(by_class.idxmax()),
        "missing_v": round(miss_v, 3),
        "value_v": round(value_v, 3),
        "verdict": leakage_verdict(miss_v, float(missing.mean())),
    }
