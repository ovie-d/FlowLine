"""Descriptive insights computed live from the database (observed patterns, not forecasts)."""

from __future__ import annotations

from typing import Any

import psycopg

from core.taxonomy import GEOTECHNICAL, HAZARD_LABELS

SHIFT_YEAR = 2022
NOTE = (
    "Observed pattern in public CER incident records and ECCC station weather, not a "
    "model forecast. Weather did not improve the forecast model (see About this model)."
)

WASHOUT_SQL = """
SELECT (extract(year FROM i.event_date) >= %(year)s) AS recent,
       (i.hazard_group = %(geo)s) AS is_geo,
       count(*) AS n,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY w.precip_30d) AS median_precip,
       count(w.precip_30d) AS n_precip
FROM incidents i LEFT JOIN incident_weather w USING (incident_number)
WHERE i.is_alberta AND i.is_model_target
GROUP BY 1, 2
"""


def washout_insight(conn: psycopg.Connection) -> dict[str, Any]:
    rows = conn.execute(
        WASHOUT_SQL, {"year": SHIFT_YEAR, "geo": GEOTECHNICAL}
    ).fetchall()
    cell = {(r["recent"], r["is_geo"]): r for r in rows}

    def period(recent: bool) -> dict[str, Any]:
        geo, other = cell.get((recent, True)), cell.get((recent, False))
        n_geo = int(geo["n"]) if geo else 0
        n_all = n_geo + (int(other["n"]) if other else 0)

        def med(r: dict[str, Any] | None) -> float | None:
            return (
                None
                if not r or r["median_precip"] is None
                else round(float(r["median_precip"]), 1)
            )

        return {
            "incidents": n_all,
            "geotechnical": n_geo,
            "geotechnical_share": round(n_geo / n_all, 3) if n_all else None,
            "median_precip_30d_geotechnical_mm": med(geo),
            "n_geotechnical_with_precip": int(geo["n_precip"]) if geo else 0,
            "median_precip_30d_other_mm": med(other),
            "n_other_with_precip": int(other["n_precip"]) if other else 0,
        }

    before, after = period(False), period(True)
    ratio = (
        round(after["geotechnical_share"] / before["geotechnical_share"], 1)
        if before["geotechnical_share"] and after["geotechnical_share"] is not None
        else None
    )
    headline = None
    if ratio is not None and after["median_precip_30d_geotechnical_mm"] is not None:
        headline = (
            f"Since {SHIFT_YEAR}, washouts and ground movement rose from "
            f"{before['geotechnical_share']:.1%} to {after['geotechnical_share']:.1%} of Alberta "
            f"incidents ({ratio}×), and followed wetter months (median "
            f"{after['median_precip_30d_geotechnical_mm']} mm vs "
            f"{after['median_precip_30d_other_mm']} mm prior-30-day rain)."
        )
    return {
        "id": "washout_shift",
        "hazard_group": GEOTECHNICAL,
        "hazard_label": HAZARD_LABELS[GEOTECHNICAL],
        "headline": headline,
        "before": {"period": f"before {SHIFT_YEAR}", **before},
        "after": {"period": f"{SHIFT_YEAR} onward", **after},
        "share_ratio": ratio,
        "note": NOTE,
        "is_forecast": False,
    }
