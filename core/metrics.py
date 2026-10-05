"""Probabilistic forecast metrics with bootstrap confidence intervals."""

from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise

import numpy as np

EPS = 1e-12
N_BOOTSTRAP = 1000
CI_LEVEL = 0.95
SEED = 20261005

Metric = Callable[[np.ndarray, np.ndarray], float]


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    return float(-np.mean(np.log(np.clip(p[np.arange(len(y)), y], EPS, 1.0))))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    onehot = np.zeros_like(p)
    onehot[np.arange(len(y)), y] = 1.0
    return float(np.mean(np.sum((p - onehot) ** 2, axis=1)))


def top_k_accuracy(p: np.ndarray, y: np.ndarray, k: int) -> float:
    top = np.argsort(-p, axis=1)[:, :k]
    return float(np.mean([y[i] in top[i] for i in range(len(y))]))


def top1(p: np.ndarray, y: np.ndarray) -> float:
    return top_k_accuracy(p, y, 1)


def top3(p: np.ndarray, y: np.ndarray) -> float:
    return top_k_accuracy(p, y, 3)


METRICS: dict[str, Metric] = {
    "log_loss": log_loss,
    "brier": brier,
    "top1": top1,
    "top3": top3,
}
LOWER_IS_BETTER = frozenset({"log_loss", "brier"})


def per_class_recall(p: np.ndarray, y: np.ndarray, n_classes: int) -> np.ndarray:
    pred = p.argmax(axis=1)
    out = np.full(n_classes, np.nan)
    for k in range(n_classes):
        mask = y == k
        if mask.any():
            out[k] = float(np.mean(pred[mask] == k))
    return out


def confusion(p: np.ndarray, y: np.ndarray, n_classes: int) -> np.ndarray:
    m = np.zeros((n_classes, n_classes), dtype=int)
    for t, q in zip(y, p.argmax(axis=1), strict=True):
        m[t, q] += 1
    return m


def _indices(n: int, n_boot: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, n, size=(n_boot, n))


def bootstrap(
    metric: Metric,
    p: np.ndarray,
    y: np.ndarray,
    n_boot: int = N_BOOTSTRAP,
    seed: int = SEED,
) -> tuple[float, float, float]:
    """(point, low, high) percentile CI by resampling test rows."""
    stats = [metric(p[i], y[i]) for i in _indices(len(y), n_boot, seed)]
    a = (1 - CI_LEVEL) / 2
    return metric(p, y), float(np.quantile(stats, a)), float(np.quantile(stats, 1 - a))


def paired_difference(
    metric: Metric,
    p_a: np.ndarray,
    p_b: np.ndarray,
    y: np.ndarray,
    n_boot: int = N_BOOTSTRAP,
    seed: int = SEED,
) -> tuple[float, float, float]:
    """metric(a) - metric(b) with a paired bootstrap CI (same resampled rows)."""
    diffs = [
        metric(p_a[i], y[i]) - metric(p_b[i], y[i])
        for i in _indices(len(y), n_boot, seed)
    ]
    a = (1 - CI_LEVEL) / 2
    point = metric(p_a, y) - metric(p_b, y)
    return point, float(np.quantile(diffs, a)), float(np.quantile(diffs, 1 - a))


def calibration_bins(
    p: np.ndarray, y: np.ndarray, n_bins: int = 10
) -> list[tuple[float, float, int]]:
    """One-vs-rest reliability over all (row, class) pairs: (mean p, observed rate, n)."""
    probs = p.ravel()
    hits = np.zeros_like(p)
    hits[np.arange(len(y)), y] = 1.0
    hits = hits.ravel()
    edges = np.linspace(0, 1, n_bins + 1)
    out = []
    for lo, hi in pairwise(edges):
        m = (probs >= lo) & ((probs < hi) if hi < 1 else (probs <= hi))
        if m.any():
            out.append((float(probs[m].mean()), float(hits[m].mean()), int(m.sum())))
    return out
