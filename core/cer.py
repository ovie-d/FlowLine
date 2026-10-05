"""Load the national CER incident file and derive per-incident fields.

Raw columns are kept untouched; derived columns are added alongside.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from core.operators import commodity_carried, operator_group
from core.taxonomy import assign_hazard_groups

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
CSV_PATH = RAW_DIR / "pipeline-incidents-comprehensive-data.csv"
DICT_PATH = RAW_DIR / "pipeline-incidents-data-dictionary.csv"
ENCODING = "cp1252"

PLACEHOLDER_RE = re.compile(
    r"^(not applicable|not provided|unknown|n/?a|to be determined|"
    r"under investigation or unknown)$",
    re.IGNORECASE,
)
TZ_RE = r"\s+(Mountain|Eastern|Pacific|Central|Atlantic|Newfoundland)\s*$"


def read_raw(path: Path = CSV_PATH) -> pd.DataFrame:
    return pd.read_csv(path, encoding=ENCODING, low_memory=False)


def read_dictionary(path: Path = DICT_PATH) -> pd.DataFrame:
    dd = pd.read_csv(path, encoding=ENCODING)
    dd.columns = ["column", "kind", "description"]
    return dd


def parse_datetime(s: pd.Series) -> pd.Series:
    """Parse '2017/02/21 05:00:00 PM Mountain' (local time; zone word dropped)."""
    cleaned = s.astype("string").str.replace(TZ_RE, "", regex=True)
    return pd.to_datetime(cleaned, format="%Y/%m/%d %I:%M:%S %p", errors="coerce")


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Add event dates, Alberta flag, hazard group, operator group, commodity."""
    out = df.copy()
    out["occurred"] = parse_datetime(out["Occurrence Date and Time"])
    out["discovered"] = parse_datetime(out["Discovered Date and Time"])
    out["reported"] = pd.to_datetime(
        out["Reported Date"], format="%m/%d/%Y", errors="coerce"
    )
    out["event_date"] = (
        out["occurred"].fillna(out["discovered"]).fillna(out["reported"])
    )
    out["is_alberta"] = out["Province"].eq("Alberta")
    out["hazard_group"] = assign_hazard_groups(out)
    out["operator_group"] = out["Company"].map(operator_group)
    out["commodity"] = out["Company"].map(commodity_carried)
    return out


@lru_cache(maxsize=1)
def _load_cached(path: str) -> pd.DataFrame:
    return add_derived(read_raw(Path(path)))


def load_cer(path: Path = CSV_PATH) -> pd.DataFrame:
    """Cached load + derive. Returns a copy; never mutate the cache."""
    return _load_cached(str(path)).copy()
