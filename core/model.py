"""Hazard-mix forecast model: LightGBM multiclass + prior correction + SHAP.

Training uses balanced class weights so rare hazards are learned; the output is
then prior-corrected (Bayes: p(k|x) ∝ q(k|x) · π_k / π'_k with π' the weighted
prior, uniform under balanced weights) so percentages match real frequencies.

Hyper-parameters are fixed up front (small, explainable). The number of boosting
rounds is chosen by early stopping on the last year of the *training* window,
then the model is refit on the whole training window — the test set is never
used for any choice.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from core.features import CATEGORICAL_FEATURES
from core.taxonomy import MODEL_TARGETS

PARAMS: dict[str, object] = {
    "objective": "multiclass",
    "num_class": len(MODEL_TARGETS),
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "max_cat_to_onehot": 8,
    "verbose": -1,
    "seed": 7,
    "deterministic": True,
    "num_threads": 4,
}
MAX_ROUNDS = 1000
EARLY_STOPPING = 50
MIN_ROUNDS = 20
PRIOR_PSEUDOCOUNT = 1.0


def class_index(y: pd.Series) -> np.ndarray:
    idx = {c: i for i, c in enumerate(MODEL_TARGETS)}
    return y.map(idx).to_numpy(dtype=int)


def class_priors(y: pd.Series) -> np.ndarray:
    counts = (
        np.bincount(class_index(y), minlength=len(MODEL_TARGETS)) + PRIOR_PSEUDOCOUNT
    )
    return counts / counts.sum()


def balanced_weights(y: pd.Series) -> np.ndarray:
    idx = class_index(y)
    counts = np.bincount(idx, minlength=len(MODEL_TARGETS)).astype(float)
    per_class = len(idx) / (len(MODEL_TARGETS) * np.maximum(counts, 1.0))
    return per_class[idx]


def prepare(
    X: pd.DataFrame, columns: list[str], categories: dict[str, list[str]]
) -> pd.DataFrame:
    """Fix column order and categorical levels (unseen levels -> NaN)."""
    out = X.reindex(columns=columns).copy()
    for col in CATEGORICAL_FEATURES:
        if col in out:
            out[col] = pd.Categorical(out[col], categories=categories[col])
    return out


@dataclass
class HazardModel:
    booster: lgb.Booster
    columns: list[str]
    categories: dict[str, list[str]]
    priors: np.ndarray
    meta: dict[str, object] = field(default_factory=dict)

    def raw_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.booster.predict(prepare(X, self.columns, self.categories))

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Prior-corrected class probabilities, columns in MODEL_TARGETS order."""
        q = self.raw_proba(X) * self.priors  # weighted prior is uniform
        return q / q.sum(axis=1, keepdims=True)

    def shap_values(self, X: pd.DataFrame) -> np.ndarray:
        """SHAP contributions (raw-margin scale): array [n, n_classes, n_features + 1]."""
        contrib = self.booster.predict(
            prepare(X, self.columns, self.categories), pred_contrib=True
        )
        n_feat = len(self.columns) + 1
        return contrib.reshape(len(X), len(MODEL_TARGETS), n_feat)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.booster.save_model(str(path.with_suffix(".lgb.txt")))
        meta = {
            "columns": self.columns,
            "categories": self.categories,
            "priors": self.priors.tolist(),
            "classes": list(MODEL_TARGETS),
            **self.meta,
        }
        path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))

    @classmethod
    def load(cls, path: Path) -> HazardModel:
        meta = json.loads(path.with_suffix(".meta.json").read_text())
        if meta["classes"] != list(MODEL_TARGETS):
            raise ValueError("model classes differ from core.taxonomy.MODEL_TARGETS")
        booster = lgb.Booster(model_file=str(path.with_suffix(".lgb.txt")))
        extra = {
            k: v
            for k, v in meta.items()
            if k not in {"columns", "categories", "priors", "classes"}
        }
        return cls(
            booster,
            meta["columns"],
            meta["categories"],
            np.array(meta["priors"]),
            extra,
        )


def _dataset(
    X: pd.DataFrame, y: pd.Series, cols: list[str], cats: dict[str, list[str]]
) -> lgb.Dataset:
    return lgb.Dataset(
        prepare(X, cols, cats),
        label=class_index(y),
        weight=balanced_weights(y),
        categorical_feature=[c for c in CATEGORICAL_FEATURES if c in cols],
        free_raw_data=False,
    )


def choose_rounds(
    X: pd.DataFrame, y: pd.Series, years: pd.Series, columns: list[str]
) -> int:
    """Early-stop on the last training year (inner validation; test untouched)."""
    last = int(years.max())
    inner_train, inner_val = years < last, years == last
    cats = categories_of(X[inner_train], columns)
    booster = lgb.train(
        PARAMS,
        _dataset(X[inner_train], y[inner_train], columns, cats),
        num_boost_round=MAX_ROUNDS,
        valid_sets=[_dataset(X[inner_val], y[inner_val], columns, cats)],
        callbacks=[lgb.early_stopping(EARLY_STOPPING, verbose=False)],
    )
    return max(MIN_ROUNDS, booster.best_iteration or MIN_ROUNDS)


def categories_of(X: pd.DataFrame, columns: list[str]) -> dict[str, list[str]]:
    return {
        c: sorted(str(v) for v in X[c].dropna().unique())
        for c in CATEGORICAL_FEATURES
        if c in columns
    }


def train(
    X: pd.DataFrame, y: pd.Series, years: pd.Series, columns: list[str]
) -> HazardModel:
    rounds = choose_rounds(X, y, years, columns)
    cats = categories_of(X, columns)
    booster = lgb.train(PARAMS, _dataset(X, y, columns, cats), num_boost_round=rounds)
    return HazardModel(
        booster,
        list(columns),
        cats,
        class_priors(y),
        {"rounds": rounds, "n_train": len(y)},
    )
