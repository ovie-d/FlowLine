"""Operator grouping, commodity from the CER systems layer, leakage diagnostics."""

from __future__ import annotations

import pandas as pd

from core.leakage import cramers_v, leakage_row, leakage_verdict
from core.operators import (
    OPERATOR_ALIASES,
    OTHER_OPERATOR,
    UNKNOWN,
    commodity_carried,
    operator_group,
    system_commodities,
)


def test_ngtl_spellings_share_one_group_and_gas() -> None:
    names = [
        "NOVA Gas Transmission Ltd.",
        "NGTL GP Ltd., as general partner on behalf of NGTL Limited Partnership",
        "NGTL GP Ltd., as general partner, on behalf of NGTL Limited Partnership",
    ]
    assert {operator_group(n) for n in names} == {"NGTL"}
    assert {commodity_carried(n) for n in names} == {"gas"}


def test_liquids_operators() -> None:
    assert commodity_carried("Trans Mountain Pipeline ULC") == "liquid"
    assert commodity_carried("Enbridge Pipelines Inc.") == "liquid"
    assert commodity_carried("TransCanada Keystone Pipeline GP Ltd.") == "liquid"


def test_whitespace_is_normalized() -> None:
    assert operator_group("  Alliance Pipeline   Ltd. ") == "Alliance"


def test_unknown_operator() -> None:
    assert operator_group("Twin Rivers Paper Company Inc.") == OTHER_OPERATOR
    assert commodity_carried("Twin Rivers Paper Company Inc.") == UNKNOWN
    assert commodity_carried(None) == UNKNOWN


def test_every_alias_points_at_a_layer_company() -> None:
    layer = system_commodities()
    for _, layer_company in OPERATOR_ALIASES.values():
        assert layer_company in layer


def test_cramers_v_bounds() -> None:
    y = pd.Series(list("aabbccaabbcc") * 10)
    assert cramers_v(y, y) > 0.95
    noise = pd.Series([0, 1] * 60)
    assert cramers_v(noise, y) < 0.05


def test_missingness_that_tracks_class_is_flagged() -> None:
    y = pd.Series(["corrosion"] * 50 + ["fire"] * 50)
    leaky = pd.Series([1.0] * 50 + [None] * 50)
    clean = pd.Series([1.0, None] * 50)
    assert leakage_row(leaky, y)["verdict"] == "LEAKS via missingness"
    assert leakage_row(clean, y)["verdict"] == "ok"


def test_always_filled_verdict() -> None:
    assert leakage_verdict(0.0, 0.0) == "ok (always filled)"
