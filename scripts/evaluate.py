"""Honest evaluation of the hazard-mix forecast -> docs/MODEL_REPORT.md.

Usage: python -m scripts.evaluate
Needs the Postgres database loaded (scripts.load_postgres) incl. weather.

- Time split: train on events up to 2021-12-31, test on 2022 onward (national
  training; results reported for Canada and for Alberta only).
- Rolling origin: each test year Y in ROLLING_YEARS, trained on years < Y.
- Baselines: national base rate, province base rate (= Alberta base rate for
  Alberta), area history only (site-weighted prior mix within 25 km).
- Ablations: without weather, without area history, without both.
- 95% bootstrap CIs on every metric; paired bootstrap for model − baseline.
Nothing is tuned on the test set (see core/model.py).
Also writes the deployable model (trained on all labelled data) to models/.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from core.env import load_dotenv
from core.features import (
    ALL_FEATURES,
    AREA_FEATURES,
    FEATURE_GROUPS,
    training_frame,
)
from core.metrics import (
    LOWER_IS_BETTER,
    METRICS,
    bootstrap,
    calibration_bins,
    confusion,
    paired_difference,
    per_class_recall,
)
from core.model import HazardModel, class_index, class_priors, train
from core.pg import connect
from core.taxonomy import GEOTECHNICAL, HAZARD_LABELS, MODEL_TARGETS
from core.weather import FEATURE_NAMES as WEATHER_FEATURES

ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = ROOT / "docs" / "MODEL_REPORT.md"
CALIBRATION_PNG = ROOT / "docs" / "model_calibration.png"
MODEL_PATH = ROOT / "models" / "hazard_forecast"

TRAIN_END_YEAR = 2021
ROLLING_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)
PROVINCE_ALPHA = 10.0  # pseudo-sites pulling a province's mix toward national
AREA_ALPHA = 2.0  # pseudo-sites pulling an area's mix toward national
LOW_EVIDENCE_SITES = 3  # fewer known prior sites within 25 km = sparse area
K = len(MODEL_TARGETS)

VARIANTS: dict[str, tuple[str, ...]] = {
    "Model (all features)": ALL_FEATURES,
    "Model − weather": tuple(f for f in ALL_FEATURES if f not in WEATHER_FEATURES),
    "Model − area history": tuple(f for f in ALL_FEATURES if f not in AREA_FEATURES),
    "Model − weather − area history": tuple(
        f for f in ALL_FEATURES if f not in WEATHER_FEATURES and f not in AREA_FEATURES
    ),
}
FULL = "Model (all features)"

INCIDENTS_SQL = """
SELECT i.incident_number, i.event_date, i.closed_date, i.province, i.is_alberta,
       i.operator_group, i.commodity, i.latitude, i.longitude, i.site_id,
       i.hazard_group, i.dist_pipeline_km, {weather}
FROM incidents i LEFT JOIN incident_weather w USING (incident_number)
ORDER BY i.event_date, i.incident_number
"""


# ------------------------------------------------------------------ data


def load_incidents() -> pd.DataFrame:
    sql = INCIDENTS_SQL.format(weather=", ".join(f"w.{c}" for c in WEATHER_FEATURES))
    with connect() as conn:
        rows = conn.execute(sql).fetchall()
    df = pd.DataFrame(rows)
    df["event_date"] = pd.to_datetime(df["event_date"])
    for c in (*WEATHER_FEATURES, "dist_pipeline_km"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ------------------------------------------------------------------ baselines


def national_baseline(y_train: pd.Series, n: int) -> np.ndarray:
    return np.tile(class_priors(y_train), (n, 1))


def province_baseline(
    y_train: pd.Series, prov_train: pd.Series, prov_test: pd.Series
) -> np.ndarray:
    national = class_priors(y_train)
    out = np.empty((len(prov_test), K))
    for i, prov in enumerate(prov_test):
        counts = np.bincount(class_index(y_train[prov_train == prov]), minlength=K)
        out[i] = (counts + PROVINCE_ALPHA * national) / (counts.sum() + PROVINCE_ALPHA)
    return out


def area_baseline(y_train: pd.Series, X_test: pd.DataFrame) -> np.ndarray:
    national = class_priors(y_train)
    mix = X_test[[f"ah_mix_{c}" for c in MODEL_TARGETS]].to_numpy()
    sites = X_test["ah_n_known_sites"].to_numpy()[:, None]
    mix = np.where(np.isnan(mix), 0.0, mix)
    return (sites * mix + AREA_ALPHA * national) / (sites + AREA_ALPHA)


# ------------------------------------------------------------------ fitting


def fit_predict(
    X: pd.DataFrame,
    y: pd.Series,
    years: pd.Series,
    train_mask: pd.Series,
    test_mask: pd.Series,
) -> tuple[dict[str, np.ndarray], dict[str, HazardModel]]:
    """Predictions for every baseline and model variant on the test rows."""
    Xtr, ytr, Xte = X[train_mask], y[train_mask], X[test_mask]
    preds = {
        "Baseline: national base rate": national_baseline(ytr, len(Xte)),
        "Baseline: province base rate": province_baseline(
            ytr, Xtr["province"], Xte["province"]
        ),
        "Baseline: area history only": area_baseline(ytr, Xte),
    }
    models: dict[str, HazardModel] = {}
    for name, cols in VARIANTS.items():
        model = train(Xtr, ytr, years[train_mask], list(cols))
        models[name] = model
        preds[name] = model.predict_proba(Xte)
    return preds, models


# ------------------------------------------------------------------ formatting


def fmt_ci(point: float, lo: float, hi: float, digits: int = 3) -> str:
    return f"{point:.{digits}f} [{lo:.{digits}f}, {hi:.{digits}f}]"


def md_table(header: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(v) for v in r) + " |" for r in rows]
    return "\n".join(lines)


def metric_table(preds: dict[str, np.ndarray], y: np.ndarray) -> str:
    rows = []
    for name, p in preds.items():
        rows.append([name, *(fmt_ci(*bootstrap(fn, p, y)) for fn in METRICS.values())])
    header = ["predictor", "log loss ↓", "Brier ↓", "top-1 acc ↑", "top-3 acc ↑"]
    return md_table(header, rows)


def best_baseline(preds: dict[str, np.ndarray], y: np.ndarray) -> str:
    base = {k: v for k, v in preds.items() if k.startswith("Baseline")}
    return min(base, key=lambda k: METRICS["log_loss"](base[k], y))


def diff_table(preds: dict[str, np.ndarray], y: np.ndarray, ref: str) -> str:
    rows = []
    for name, p in preds.items():
        if name == ref:
            continue
        cells = []
        for metric, fn in METRICS.items():
            d, lo, hi = paired_difference(fn, p, preds[ref], y)
            better = (hi < 0) if metric in LOWER_IS_BETTER else (lo > 0)
            worse = (lo > 0) if metric in LOWER_IS_BETTER else (hi < 0)
            tag = " ✅" if better else (" ❌" if worse else "")
            cells.append(f"{d:+.3f} [{lo:+.3f}, {hi:+.3f}]{tag}")
        rows.append([name, *cells])
    header = ["predictor − " + ref, "Δ log loss", "Δ Brier", "Δ top-1", "Δ top-3"]
    note = (
        "✅ = better than the reference with the 95% CI excluding zero; "
        "❌ = worse with the CI excluding zero; blank = not distinguishable."
    )
    return md_table(header, rows) + "\n\n" + note


def recall_table(preds: dict[str, np.ndarray], y: np.ndarray, names: list[str]) -> str:
    counts = np.bincount(y, minlength=K)
    rows = []
    for k, cls in enumerate(MODEL_TARGETS):
        recalls = [per_class_recall(preds[n], y, K)[k] for n in names]
        rows.append(
            [
                HAZARD_LABELS[cls],
                int(counts[k]),
                *("—" if np.isnan(r) else f"{r:.2f}" for r in recalls),
            ]
        )
    return md_table(["hazard group", "n test", *names], rows)


def confusion_table(p: np.ndarray, y: np.ndarray) -> str:
    m = confusion(p, y, K)
    short = [c.split("_")[0][:6] for c in MODEL_TARGETS]
    rows = [[HAZARD_LABELS[c], *m[i]] for i, c in enumerate(MODEL_TARGETS)]
    return md_table(["actual ↓ / predicted →", *short], rows)


# ------------------------------------------------------------------ sections


def section_split(
    X: pd.DataFrame, y: pd.Series, years: pd.Series, ab: pd.Series
) -> tuple[str, dict[str, np.ndarray], dict[str, HazardModel], pd.Series]:
    train_mask = years <= TRAIN_END_YEAR
    test_mask = years > TRAIN_END_YEAR
    preds, models = fit_predict(X, y, years, train_mask, test_mask)
    yte = class_index(y[test_mask])
    ab_te = ab[test_mask].to_numpy()
    preds_ab = {k: v[ab_te] for k, v in preds.items()}
    ref_nat, ref_ab = best_baseline(preds, yte), best_baseline(preds_ab, yte[ab_te])
    text = "\n\n".join(
        [
            "## 2. Main result — time split",
            (
                f"Train: events ≤ {TRAIN_END_YEAR} ({int(train_mask.sum())} incidents, "
                f"national). Test: events ≥ {TRAIN_END_YEAR + 1} ({int(test_mask.sum())} "
                f"national, {int(ab_te.sum())} Alberta). Point estimate with 95% bootstrap CI "
                "(1,000 resamples of test incidents)."
            ),
            "### Canada",
            metric_table(preds, yte),
            f"Paired differences vs the best baseline (**{ref_nat}**):",
            diff_table(preds, yte, ref_nat),
            "### Alberta only (same models, Alberta test incidents)",
            metric_table(preds_ab, yte[ab_te]),
            f"Paired differences vs the best Alberta baseline (**{ref_ab}**):",
            diff_table(preds_ab, yte[ab_te], ref_ab),
        ]
    )
    return text, preds, models, test_mask


def section_rolling(
    X: pd.DataFrame, y: pd.Series, years: pd.Series, ab: pd.Series
) -> str:
    rows = []
    for year in ROLLING_YEARS:
        train_mask, test_mask = years < year, years == year
        if test_mask.sum() == 0:
            continue
        Xtr, ytr, Xte = X[train_mask], y[train_mask], X[test_mask]
        yte = class_index(y[test_mask])
        model = train(Xtr, ytr, years[train_mask], list(ALL_FEATURES))
        p_model = model.predict_proba(Xte)
        p_nat = national_baseline(ytr, len(Xte))
        p_area = area_baseline(ytr, Xte)
        ab_te = ab[test_mask].to_numpy()
        d, lo, hi = paired_difference(METRICS["log_loss"], p_model, p_nat, yte)
        rows.append(
            [
                year,
                int(test_mask.sum()),
                int(ab_te.sum()),
                fmt_ci(*bootstrap(METRICS["log_loss"], p_model, yte)),
                f"{METRICS['log_loss'](p_nat, yte):.3f}",
                f"{METRICS['log_loss'](p_area, yte):.3f}",
                f"{d:+.3f} [{lo:+.3f}, {hi:+.3f}]",
                f"{METRICS['top3'](p_model, yte):.2f} / {METRICS['top3'](p_nat, yte):.2f}",
                f"{METRICS['log_loss'](p_model[ab_te], yte[ab_te]):.3f} / "
                f"{METRICS['log_loss'](p_nat[ab_te], yte[ab_te]):.3f}"
                if ab_te.any()
                else "—",
            ]
        )
    header = [
        "test year",
        "n",
        "n AB",
        "model log loss [CI]",
        "national base",
        "area history",
        "Δ model − national [CI]",
        "top-3 model / national",
        "AB log loss model / national",
    ]
    return "\n\n".join(
        [
            "## 3. Rolling-origin check",
            (
                "Each row trains on all years before the test year (national) and tests on that "
                "year only. Early stopping uses the last training year, never the test year."
            ),
            md_table(header, rows),
        ]
    )


def section_ablation(
    preds: dict[str, np.ndarray], y: np.ndarray, ab: np.ndarray
) -> str:
    rows = []
    full = preds[FULL]
    for name in VARIANTS:
        if name == FULL:
            continue
        for label, mask in (("Canada", np.ones_like(ab)), ("Alberta", ab)):
            d, lo, hi = paired_difference(
                METRICS["log_loss"], full[mask], preds[name][mask], y[mask]
            )
            verdict = (
                "helps" if hi < 0 else ("hurts" if lo > 0 else "not distinguishable")
            )
            rows.append(
                [
                    name.replace("Model − ", "remove "),
                    label,
                    f"{d:+.3f} [{lo:+.3f}, {hi:+.3f}]",
                    verdict,
                ]
            )
    return "\n\n".join(
        [
            "## 4. Ablation — do weather and area history help?",
            (
                "Δ = log loss of the full model minus the ablated model on the same test "
                "incidents (negative = the removed features were helping)."
            ),
            md_table(
                ["ablation", "test set", "Δ log loss full − ablated [CI]", "verdict"],
                rows,
            ),
            (
                "**Narrative features:** not available. Public CER data has cause codes only, "
                "and embedding those would encode the label (decision A, Phase 2). The pgvector "
                "narrative path is ready for operator narratives in a pilot."
            ),
        ]
    )


def section_failures(
    preds: dict[str, np.ndarray], y: np.ndarray, X_test: pd.DataFrame, ab: np.ndarray
) -> str:
    full, nat = preds[FULL], preds["Baseline: national base rate"]
    per_prov = []
    for prov, idx in X_test.groupby("province").indices.items():
        per_prov.append(
            [
                prov,
                len(idx),
                f"{METRICS['log_loss'](full[idx], y[idx]):.3f}",
                f"{METRICS['log_loss'](nat[idx], y[idx]):.3f}",
            ]
        )
    sparse = (X_test["ah_n_known_sites"] < LOW_EVIDENCE_SITES).to_numpy()
    rows_sparse = []
    for label, m in (
        ("sparse (< 3 known prior sites in 25 km)", sparse),
        ("dense", ~sparse),
    ):
        if m.any():
            rows_sparse.append(
                [
                    label,
                    int(m.sum()),
                    f"{METRICS['log_loss'](full[m], y[m]):.3f}",
                    f"{METRICS['log_loss'](nat[m], y[m]):.3f}",
                    f"{METRICS['top1'](full[m], y[m]):.2f}",
                ]
            )
    recall = per_class_recall(full, y, K)
    worst = [
        HAZARD_LABELS[MODEL_TARGETS[k]]
        for k in np.argsort(np.nan_to_num(recall, nan=9))[:3]
    ]
    return "\n\n".join(
        [
            "## 5. Where it fails",
            f"**Worst classes by recall (full model, Canada):** {', '.join(worst)}.",
            "### Per-class recall (top-1), Canada",
            recall_table(
                preds,
                y,
                [FULL, "Baseline: area history only", "Baseline: national base rate"],
            ),
            "### Per-class recall (top-1), Alberta",
            recall_table(
                {k: v[ab] for k, v in preds.items()},
                y[ab],
                [FULL, "Baseline: area history only"],
            ),
            "### Confusion matrix (full model, Canada test, top-1)",
            confusion_table(full, y),
            "### By province (test)",
            md_table(
                ["province", "n", "model log loss", "national base log loss"],
                sorted(per_prov, key=lambda r: -r[1]),
            ),
            "### Sparse vs dense areas (test)",
            md_table(
                [
                    "area",
                    "n",
                    "model log loss",
                    "national base log loss",
                    "model top-1",
                ],
                rows_sparse,
            ),
        ]
    )


def section_washout(
    preds: dict[str, np.ndarray],
    y: np.ndarray,
    X_test: pd.DataFrame,
    ab: np.ndarray,
    df: pd.DataFrame,
    years: pd.Series,
) -> str:
    g = MODEL_TARGETS.index(GEOTECHNICAL)
    ab_all = df["is_alberta"].to_numpy(dtype=bool)
    target = df["hazard_group"].isin(MODEL_TARGETS).to_numpy()
    yr = df["event_date"].dt.year.to_numpy()
    shares = []
    for label, m in (("≤ 2021", yr <= TRAIN_END_YEAR), ("≥ 2022", yr > TRAIN_END_YEAR)):
        sel = ab_all & target & m
        geo = (df["hazard_group"] == GEOTECHNICAL).to_numpy() & sel
        precip = df.loc[geo, "precip_30d"]
        precip_other = df.loc[sel & ~geo, "precip_30d"]
        shares.append(
            [
                label,
                int(sel.sum()),
                f"{geo.sum() / max(sel.sum(), 1):.1%}",
                f"{precip.median():.1f} (n={precip.notna().sum()})",
                f"{precip_other.median():.1f} (n={precip_other.notna().sum()})",
            ]
        )
    is_geo = y == g
    rows = []
    for name, p in preds.items():
        rows.append(
            [
                name,
                f"{p[ab, g].mean():.1%}",
                f"{p[ab & is_geo, g].mean():.1%}" if (ab & is_geo).any() else "—",
                f"{p[ab & ~is_geo, g].mean():.1%}",
            ]
        )
    actual = (ab & is_geo).sum() / max(ab.sum(), 1)
    d, lo, hi = paired_difference(
        lambda p_, y_: float(np.mean(p_[y_ == g, g])) if (y_ == g).any() else 0.0,
        preds[FULL][ab],
        preds["Model − weather"][ab],
        y[ab],
    )
    return "\n\n".join(
        [
            "## 6. The post-2022 washout shift (Alberta)",
            (
                "Alberta's share of geotechnical incidents (mostly washout / erosion on NGTL and "
                "Trans Mountain lines) rose after 2021. Is it visible in the weather?"
            ),
            md_table(
                [
                    "period",
                    "AB target incidents",
                    "geotechnical share",
                    "median precip_30d, geotechnical (mm)",
                    "median precip_30d, other (mm)",
                ],
                shares,
            ),
            f"Actual geotechnical share in the Alberta test set: **{actual:.1%}**.",
            md_table(
                [
                    "predictor",
                    "mean p(geotech), all AB test",
                    "mean p(geotech) when it WAS geotech",
                    "mean p(geotech) otherwise",
                ],
                rows,
            ),
            (
                f"Weather's contribution to p(geotech) on actual Alberta geotechnical cases "
                f"(full − no-weather): **{d:+.1%}** [95% CI {lo:+.1%}, {hi:+.1%}]."
            ),
        ]
    )


def section_shap(model: HazardModel, X_test: pd.DataFrame) -> str:
    sv = model.shap_values(X_test)[:, :, :-1]  # drop bias column
    overall = np.abs(sv).mean(axis=(0, 1))
    order = np.argsort(-overall)[:15]
    group_of = {f: g for g, fs in FEATURE_GROUPS.items() for f in fs}
    rows = [
        [model.columns[i], group_of.get(model.columns[i], "—"), f"{overall[i]:.3f}"]
        for i in order
    ]
    return "\n\n".join(
        [
            "## 7. What drives the forecast (SHAP, full model, test set)",
            (
                "Mean |SHAP| over test incidents and classes (raw-margin scale). Per-forecast "
                "top drivers are returned by the API in plain words."
            ),
            md_table(["feature", "group", "mean |SHAP|"], rows),
        ]
    )


def plot_calibration(preds: dict[str, np.ndarray], y: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.plot([0, 1], [0, 1], color="#8CA0C3", lw=1, ls="--", label="perfect")
    for name, color in (
        (FULL, "#F5A524"),
        ("Baseline: area history only", "#2DD4BF"),
        ("Baseline: national base rate", "#6B7FA8"),
    ):
        bins = calibration_bins(preds[name], y)
        ax.plot(
            [b[0] for b in bins],
            [b[1] for b in bins],
            marker="o",
            color=color,
            label=name,
        )
    ax.set_xlabel("predicted probability (one-vs-rest)")
    ax.set_ylabel("observed frequency")
    ax.set_title("Calibration — Canada test (≥ 2022)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(CALIBRATION_PNG, dpi=130)
    plt.close(fig)


def section_data(df: pd.DataFrame, X: pd.DataFrame) -> str:
    wx = X[list(WEATHER_FEATURES)].notna().all(axis=1).mean()
    temp = X["temp_mean_7d"].notna().mean()
    return "\n\n".join(
        [
            "## 1. Data and features",
            (
                f"- Incidents in the database: {len(df):,}; forecast-target incidents: {len(X):,} "
                "(Other / unknown and Undetermined are excluded from the target)."
            ),
            f"- Features ({len(ALL_FEATURES)}): "
            + "; ".join(f"**{g}** ({len(fs)})" for g, fs in FEATURE_GROUPS.items())
            + ".",
            (
                f"- Weather coverage on target incidents: temperature {temp:.1%}, all weather "
                f"features {wx:.1%} (missing stays missing; LightGBM handles NaN)."
            ),
            (
                "- Area history: incidents strictly before the event date within 25 km; the "
                "hazard mix uses only incidents **closed** before the event date (cause known "
                "then), each site weighted once (sites = 1 km leader clusters)."
            ),
            "- Leakage guards are enforced in code and tested (`tests/test_features.py`).",
        ]
    )


def conclusion(preds: dict[str, np.ndarray], y: np.ndarray, ab: np.ndarray) -> str:
    lines = ["## 0. Conclusion (plain words)"]
    for label, mask in (("Canada", np.ones_like(ab)), ("Alberta", ab)):
        sub = {k: v[mask] for k, v in preds.items()}
        ref = best_baseline(sub, y[mask])
        d, lo, hi = paired_difference(METRICS["log_loss"], sub[FULL], sub[ref], y[mask])
        if hi < 0:
            verdict = "**beats** the best baseline"
        elif lo > 0:
            verdict = "is **worse than** the best baseline"
        else:
            verdict = "is **not distinguishable** from the best baseline"
        lines.append(
            f"- **{label}:** the full model {verdict} (*{ref}*) on log loss: "
            f"Δ = {d:+.3f}, 95% CI [{lo:+.3f}, {hi:+.3f}] (n = {int(mask.sum())})."
        )
    return "\n".join(lines)


def train_deployable(X: pd.DataFrame, y: pd.Series, years: pd.Series) -> HazardModel:
    model = train(X, y, years, list(ALL_FEATURES))
    model.meta.update(
        {
            "trained_through": str(int(years.max())),
            "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    )
    model.save(MODEL_PATH)
    return model


def main() -> None:
    load_dotenv()
    df = load_incidents()
    X, y = training_frame(df)
    meta = df.loc[X.index]
    years = meta["event_date"].dt.year
    ab = meta["is_alberta"].astype(bool)

    split_text, preds, models, test_mask = section_split(X, y, years, ab)
    yte = class_index(y[test_mask])
    ab_te = ab[test_mask].to_numpy()
    plot_calibration(preds, yte)
    body = [
        "# Flowline Hazard Forecast — Model Report",
        (
            f"Generated by `scripts/evaluate.py` on {datetime.now(UTC):%Y-%m-%d}. "
            "Forecasts are based on historical public incident data. Flowline supports "
            "engineering judgment; it does not certify any pipe as safe."
        ),
        conclusion(preds, yte, ab_te),
        section_data(df, X),
        split_text,
        section_rolling(X, y, years, ab),
        section_ablation(preds, yte, ab_te),
        section_failures(preds, yte, X[test_mask], ab_te),
        section_washout(preds, yte, X[test_mask], ab_te, df, years),
        section_shap(models[FULL], X[test_mask]),
        "## 8. Calibration\n\n![calibration](model_calibration.png)",
    ]
    REPORT_PATH.write_text("\n\n".join(body) + "\n", encoding="utf-8")
    print(f"wrote {REPORT_PATH.relative_to(ROOT)}")
    deployable = train_deployable(X, y, years)
    print(
        f"saved deployable model ({deployable.meta['rounds']} rounds) to "
        f"{MODEL_PATH.relative_to(ROOT)}.*"
    )


if __name__ == "__main__":
    main()
