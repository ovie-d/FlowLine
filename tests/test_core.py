"""Core tests — lock cleaning facts and the Edson → Sherwood Park flip."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from core.compare import compare, improvement_round
from core.config import (
    BASELINE_COUNT,
    CONSEQUENCE_HEAVY,
    DEFAULT,
    LOW_CONSEQUENCE,
    RiskConfig,
)
from core.data import clear_load_cache, load_incidents
from core.scoring import explain_corridor, score

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "cer_pipeline_incidents_alberta_2015.csv"


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_load_cache()
    yield
    clear_load_cache()


def test_seed_md5():
    import hashlib

    digest = hashlib.md5(SEED.read_bytes()).hexdigest()
    assert digest == "192d962494ed791c26225fccd20a5e28"


def test_corridor_count_after_cleaning():
    _df, report = load_incidents()
    # "Edmonton & Sherwood Park" kept as its own corridor on purpose.
    assert report["corridors_after"] == 112
    assert report["corridors_before"] == 128


def test_no_province_suffixes():
    df, _ = load_incidents()
    for name in df["corridor"].unique():
        assert not name.endswith(" AB"), name
        assert not name.endswith(" Ab"), name
        assert not name.endswith(" Alberta"), name


def test_default_edson_rank_1():
    ranked = score(DEFAULT, top=15)
    assert ranked[0]["corridor"] == "Edson"
    assert ranked[0]["rank"] == 1
    assert ranked[0]["n"] == 33


def test_heavy_sherwood_park_rank_1():
    ranked = score(CONSEQUENCE_HEAVY, top=15)
    assert ranked[0]["corridor"] == "Sherwood Park"
    assert ranked[0]["rank"] == 1


def test_low_consequence_edson_still_first():
    ranked = score(LOW_CONSEQUENCE, top=1)
    assert ranked[0]["corridor"] == "Edson"


def _starter_count_only_top15() -> list[str]:
    """Organizer baseline: group by raw corridor, rank by count only."""
    df = pd.read_csv(SEED, parse_dates=["date"]).dropna(subset=["date"])
    g = df.groupby("corridor").agg(n=("date", "size"))
    ranked = g.sort_values("n", ascending=False).head(15)
    return list(ranked.index)


def test_count_only_matches_starter_top15_set():
    """After cleaning, count-only top names should cover the noisy baseline set's intent.

    Starter uses dirty names (Edson AB separate). Our cleaned count-only merges
    aliases, so we check Edson still leads and overlap with starter's canonized set.
    """
    ours = [r["corridor"] for r in score(BASELINE_COUNT, top=15)]
    assert ours[0] == "Edson"

    starter = _starter_count_only_top15()
    # Canonize starter names with the same alias map.
    from core.data import CORRIDOR_ALIASES

    starter_clean = {CORRIDOR_ALIASES.get(c, c) for c in starter}
    overlap = len(set(ours) & starter_clean)
    assert overlap >= 12, f"overlap={overlap}, ours={ours}, starter={starter_clean}"


def test_determinism():
    a = score(DEFAULT, top=15)
    b = score(DEFAULT, top=15)
    assert a == b


def test_json_serializable_rows():
    for row in score(DEFAULT, top=15):
        json.dumps(row)


def test_explain_unknown_corridor():
    out = explain_corridor("Not A Real Place")
    assert "error" in out


def test_compare_overlap_shape():
    result = compare(BASELINE_COUNT, CONSEQUENCE_HEAVY, top=15)
    assert "overlap" in result
    assert "movers" in result
    assert isinstance(result["overlap"], int)
    assert result["overlap"] <= 15


def test_jenner_rises_under_weighted():
    count_ranks = {r["corridor"]: r["rank"] for r in score(BASELINE_COUNT, top=50)}
    weighted = {r["corridor"]: r["rank"] for r in score(DEFAULT, top=50)}
    assert "Jenner" in count_ranks and "Jenner" in weighted
    assert count_ranks["Jenner"] > weighted["Jenner"]
    assert count_ranks["Jenner"] == 26
    assert weighted["Jenner"] == 12


def test_improvement_round_stages_and_yardstick():
    result = improvement_round(top=15)
    json.dumps(result)
    names = [s["stage"] for s in result["stages"]]
    assert names == ["baseline", "lab", "ours"]

    totals = {s["serious_total"] for s in result["stages"]}
    assert len(totals) == 1

    by_stage = {s["stage"]: s for s in result["stages"]}
    assert (
        by_stage["ours"]["serious_captured"] >= by_stage["baseline"]["serious_captured"]
    )
    assert "ours_heavy" in result
    assert result["ours_heavy"]["stage"] == "ours_heavy"


def test_bad_config_raises():
    with pytest.raises(ValueError):
        RiskConfig(label="nope")
    with pytest.raises(ValueError):
        RiskConfig(weights={"high": -1, "medium": 1, "low": 1})
