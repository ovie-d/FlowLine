"""Profile the national CER incident file -> docs/DATA_PROFILE.md.

Usage: python -m scripts.profile_cer
Reads data/raw/pipeline-incidents-comprehensive-data.csv (+ data dictionary).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from core.leakage import CAUTION_V, LEAK_V, leakage_row
from core.operators import UNKNOWN, commodity_carried, operator_group
from core.taxonomy import (
    HAZARD_GROUPS,
    HAZARD_LABELS,
    LOW_EVIDENCE_GROUPS,
    MODEL_TARGETS,
    UNDETERMINED,
    all_hazards,
    assign_hazard_groups,
    classify_code,
)

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CSV_PATH = RAW / "pipeline-incidents-comprehensive-data.csv"
DICT_PATH = RAW / "pipeline-incidents-data-dictionary.csv"
OUT_PATH = ROOT / "docs" / "DATA_PROFILE.md"
ENCODING = "cp1252"

TRAIN_END_YEAR = 2021
SPARSE_NATIONAL = 100
SPARSE_ALBERTA_TRAIN = 30
SPARSE_ALBERTA_TEST = 10

PLACEHOLDER_RE = re.compile(
    r"^(not applicable|not provided|unknown|n/?a|to be determined|"
    r"under investigation or unknown)$",
    re.IGNORECASE,
)
TZ_RE = r"\s+(Mountain|Eastern|Pacific|Central|Atlantic|Newfoundland)\s*$"

NARRATIVE_CANDIDATES = (
    "Detailed what happened",
    "Detailed why it happened",
    "What happened category",
    "Why it happened category",
)

PIPE_ATTRIBUTES: dict[str, str] = {
    "Material": "material",
    "Material grade": "material",
    "Pipeline outside diameter (NPS)": "diameter",
    "Nominal pipe size": "diameter",
    "Design wall thickness (mm)": "wall thickness",
    "Actual wall thickness (mm)": "wall thickness",
    "Year of installation": "install year",
    "Year when put into service": "install year",
    "Year of manufacture": "install year",
    "Coating type": "coating",
    "Coating condition": "coating",
    "Licensed maximum operating pressure (kPa)": "pressure",
    "Actual operating pressure at time of failure (kPa)": "pressure",
    "Substance carried": "substance carried",
    "Pipeline or Facility Type": "pipeline / facility type",
}

# Hand-assigned role of each column for the forecast (Phase 6 leakage rules).
# Anything not listed is treated as "outcome / post-event" (never a feature).
COLUMN_ROLES: dict[str, str] = {
    "Incident Number": "id",
    "Reported Date": "time (reporting)",
    "Year": "time (reporting)",
    "Occurrence Date and Time": "time",
    "Discovered Date and Time": "time",
    "Nearest Populated Centre": "location",
    "Province": "location",
    "Latitude": "location",
    "Longitude": "location",
    "Country": "location",
    "Facility latitude": "location",
    "Facility longitude": "location",
    "Land Use": "location",
    "Population Density": "location",
    "Company": "asset / context",
    "Pipeline Name": "asset / context",
    "Pipeline outside diameter (NPS)": "asset (fill depends on incident)",
    "Pipeline length (km)": "asset (fill depends on incident)",
    "Substance carried": "asset (fill depends on incident)",
    "Facility Name": "asset (fill depends on incident)",
    "Facility Type": "asset (fill depends on incident)",
    "Pipeline or Facility Type": "asset (fill depends on incident)",
    "Regulation": "asset / context",
    "Kilometre post": "asset (fill depends on incident)",
    "Design standard": "asset (fill depends on incident)",
    "Nominal pipe size": "asset (fill depends on incident)",
    "Material": "asset (fill depends on incident)",
    "Material grade": "asset (fill depends on incident)",
    "Schedule": "asset (fill depends on incident)",
    "Design wall thickness (mm)": "asset (fill depends on incident)",
    "Custom design wall thickness (mm)": "asset (fill depends on incident)",
    "Licensed maximum operating pressure (kPa)": "asset (fill depends on incident)",
    "Restricted operating pressure (kPa)": "asset (fill depends on incident)",
    "Designed depth of cover (m)": "asset (fill depends on incident)",
    "Year of manufacture": "asset (fill depends on incident)",
    "Year of installation": "asset (fill depends on incident)",
    "Year when put into service": "asset (fill depends on incident)",
    "Insulation installed": "asset (fill depends on incident)",
    "What happened category": "TARGET (cause)",
    "Detailed what happened": "TARGET (cause)",
    "Why it happened category": "cause (leak)",
    "Detailed why it happened": "cause (leak)",
}


def load_raw() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(CSV_PATH, encoding=ENCODING, low_memory=False)
    dd = pd.read_csv(DICT_PATH, encoding=ENCODING)
    dd.columns = ["column", "kind", "description"]
    return df, dd


def parse_datetime(s: pd.Series) -> pd.Series:
    cleaned = s.astype("string").str.replace(TZ_RE, "", regex=True)
    return pd.to_datetime(cleaned, format="%Y/%m/%d %I:%M:%S %p", errors="coerce")


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
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
    return out


def norm_name(name: str) -> str:
    n = re.sub(r"\s+", " ", str(name)).strip().lower()
    return n.replace("center", "centre")


def dictionary_lookup(dd: pd.DataFrame) -> dict[str, str]:
    cols = dd[dd["kind"].astype(str).str.contains("Name of the Column")]
    return {
        norm_name(r.column): re.sub(r"\s+", " ", str(r.description)).strip()
        for r in cols.itertuples()
    }


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def md_table(rows: list[list[object]], header: list[str]) -> str:
    def cell(v: object) -> str:
        return str(v).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]
    return "\n".join(lines)


def counts_table(s: pd.Series, header: str) -> str:
    vc = s.value_counts()
    return md_table([[k, v] for k, v in vc.items()], [header, "count"])


def explode_list(s: pd.Series, sep: str) -> pd.Series:
    out = s.dropna().astype(str).str.split(sep).explode().str.strip()
    return out[out != ""]


def section_overview(df: pd.DataFrame, n_cols: int) -> str:
    ab = df[df["is_alberta"]]
    years = df["event_date"].dt.year.value_counts().sort_index()
    ab_years = ab["event_date"].dt.year.value_counts().sort_index()
    year_rows = [[int(y), int(n), int(ab_years.get(y, 0))] for y, n in years.items()]
    status = ", ".join(f"{k}: {v}" for k, v in df["Status"].value_counts().items())
    return "\n\n".join(
        [
            "## 1. Overview",
            (
                f"- **Rows:** {len(df):,} incidents ({df['Incident Number'].nunique():,} unique "
                f"incident numbers), **{n_cols} columns** in the raw file."
            ),
            (
                f"- **Reported date range:** {df['reported'].min():%Y-%m-%d} → "
                f"{df['reported'].max():%Y-%m-%d}."
            ),
            (
                f"- **Event date range** (occurrence → discovered → reported fallback): "
                f"{df['event_date'].min():%Y-%m-%d} → {df['event_date'].max():%Y-%m-%d}."
            ),
            f"- **Alberta rows:** {len(ab):,} ({pct(len(ab) / len(df))}).",
            f"- **Status:** {status}.",
            "### Rows per province",
            counts_table(df["Province"], "province"),
            "### Rows per event year",
            md_table(year_rows, ["year", "national", "alberta"]),
        ]
    )


def section_dates(df: pd.DataFrame) -> str:
    occ = df["occurred"].notna()
    disc = ~occ & df["discovered"].notna()
    rep = ~occ & ~disc & df["reported"].notna()
    gap = (df["reported"] - df["event_date"]).dt.days
    return "\n\n".join(
        [
            "## 2. Dates",
            md_table(
                [
                    ["Occurrence date and time", int(occ.sum()), pct(occ.mean())],
                    ["→ fallback: Discovered date", int(disc.sum()), pct(disc.mean())],
                    ["→ fallback: Reported date", int(rep.sum()), pct(rep.mean())],
                    ["No usable date", int(df["event_date"].isna().sum()), ""],
                ],
                ["event_date source", "rows", "share"],
            ),
            (
                f"Occurrence time carries a local time-zone word (Mountain, Pacific, …); it is "
                f"stripped and the date treated as local. Median reporting lag (reported − event): "
                f"**{gap.median():.0f} days** (90th pct {gap.quantile(0.9):.0f})."
            ),
        ]
    )


def placeholder_share(s: pd.Series) -> float:
    st = s.dropna().astype(str).str.strip()
    return float(st.str.match(PLACEHOLDER_RE).sum()) / len(s) if len(s) else 0.0


def examples(s: pd.Series, k: int = 3) -> str:
    vals = s.dropna().astype(str).str.strip()
    vals = vals[~vals.str.match(PLACEHOLDER_RE) & (vals != "")]
    top = vals.value_counts().index[:k]
    return "; ".join(v[:40] + ("…" if len(v) > 40 else "") for v in top)


def section_columns(raw: pd.DataFrame, dd: pd.DataFrame) -> str:
    lookup = dictionary_lookup(dd)
    rows, unmatched = [], []
    for col in raw.columns:
        desc = lookup.get(norm_name(col))
        if desc is None:
            unmatched.append(col)
        s = raw[col]
        rows.append(
            [
                col.strip(),
                str(s.dtype),
                pct(s.isna().mean()),
                pct(placeholder_share(s)),
                s.nunique(),
                COLUMN_ROLES.get(col, "outcome / post-event"),
                examples(s),
                (desc or "— not in dictionary —")[:140],
            ]
        )
    header = [
        "column",
        "dtype",
        "% missing",
        "% placeholder",
        "distinct",
        "forecast role",
        "examples",
        "dictionary description",
    ]
    notes = (
        "`% placeholder` counts strings such as *Not Applicable*, *Not Provided*, *Unknown*, "
        "*To be determined* that are effectively missing. `forecast role` is our hand "
        "classification for Phase 6: only `time`, `location` and `asset / context` columns "
        "are candidate features; `asset (fill depends on incident)` columns are mostly "
        "filled only when the pipe body was involved (see §5), so their *presence* leaks the "
        "cause."
    )
    missing_note = (
        f"Columns not matched in the data dictionary ({len(unmatched)}): "
        + ", ".join(f"`{c}`" for c in unmatched)
        if unmatched
        else "Every column matched a data-dictionary entry."
    )
    return "\n\n".join(["## 3. Columns", notes, md_table(rows, header), missing_note])


def section_narrative(raw: pd.DataFrame) -> str:
    rows = []
    for col in NARRATIVE_CANDIDATES:
        s = raw[col].dropna().astype(str)
        rows.append(
            [
                col,
                pct(raw[col].notna().mean()),
                f"{s.str.len().mean():.0f}",
                s.nunique(),
                s.iloc[0][:90],
            ]
        )
    sample = explode_list(raw["Detailed what happened"], ";")
    return "\n\n".join(
        [
            "## 4. Narrative text — **none in this file**",
            (
                "**Finding:** the file has **no free-text narrative**. The longest text columns "
                "are `Detailed what happened` / `Detailed why it happened`, which are "
                "`;`-separated lists of **fixed CER cause codes** (hierarchical: "
                "`<level 1>, <level 2>[, <level 3>]`), chosen from a closed vocabulary of "
                f"{sample.nunique()} distinct codes. They are the cause labels themselves, not "
                "descriptions written by a person."
            ),
            md_table(
                rows,
                [
                    "column",
                    "% filled",
                    "avg length (chars)",
                    "distinct values",
                    "example",
                ],
            ),
            (
                "Impact on the plan: Phase 5 (narrative embeddings) has no narrative to embed. "
                "Embedding these code strings would only re-encode the target label. See the "
                "report for options."
            ),
        ]
    )


def section_pipe(df: pd.DataFrame) -> str:
    ab = df["is_alberta"]
    rows = []
    for col, attr in PIPE_ATTRIBUTES.items():
        filled = df[col].notna() & ~df[col].astype(str).str.match(PLACEHOLDER_RE)
        rows.append([attr, col, pct(filled.mean()), pct(filled[ab].mean())])
    by_group = []
    known = df["hazard_group"] != UNDETERMINED
    for g in HAZARD_GROUPS:
        m = known & df["hazard_group"].eq(g)
        by_group.append(
            [
                HAZARD_LABELS[g],
                int(m.sum()),
                pct(df.loc[m, "Material"].notna().mean()),
                pct(df.loc[m, "Year of installation"].notna().mean()),
                pct(df.loc[m, "Pipeline or Facility Type"].notna().mean()),
            ]
        )
    return "\n\n".join(
        [
            "## 5. Pipe attributes",
            md_table(
                rows,
                ["attribute", "column", "% filled (national)", "% filled (Alberta)"],
            ),
            "### Fill rate depends on the cause (leakage risk)",
            md_table(
                by_group,
                [
                    "hazard group",
                    "n",
                    "Material filled",
                    "Install year filled",
                    "Pipeline/Facility type filled",
                ],
            ),
            (
                "Pipe attributes are recorded mainly when the pipe body failed. Using them — or "
                "their missingness — as forecast features would leak the answer. They can only be "
                "used if we join them from an **independent asset source** (e.g. the CER pipeline "
                "systems layer), not from the incident record."
            ),
        ]
    )


def section_cer_taxonomy(raw: pd.DataFrame) -> str:
    detailed = explode_list(raw["Detailed what happened"], ";")
    level2 = detailed.str.split(", ").str[:2].str.join(" › ")
    multi_what = raw["What happened category"].fillna("").str.contains(",").sum()
    return "\n\n".join(
        [
            "## 6. CER taxonomy",
            (
                "Category columns are **multi-valued** (comma-separated). Counts below are "
                f"per mention, so they sum to more than the row count. Rows with more than one "
                f"`What happened category`: {multi_what}."
            ),
            "### Incident Types (what kind of event — an outcome, not a cause)",
            counts_table(explode_list(raw["Incident Types"], ","), "incident type"),
            "### What happened category (CER top-level cause)",
            counts_table(explode_list(raw["What happened category"], ","), "category"),
            "### Why it happened category (root / basic cause)",
            counts_table(
                explode_list(raw["Why it happened category"], ","), "category"
            ),
            "### Detailed what happened — level 1 › level 2",
            counts_table(level2, "detailed code"),
        ]
    )


def section_coordinates(df: pd.DataFrame) -> str:
    lat, lon = df["Latitude"], df["Longitude"]
    missing = lat.isna() | lon.isna()
    zero = (lat == 0) | (lon == 0)
    outside_ca = ~missing & ~(lat.between(41, 84) & lon.between(-141, -52))
    ab = df["is_alberta"]
    ab_out = ab & ~missing & ~(lat.between(49, 60) & lon.between(-120.1, -109.9))
    dup = df.duplicated(["Latitude", "Longitude"], keep=False)
    rows = [
        ["missing lat or lon", int(missing.sum())],
        ["exactly 0", int(zero.sum())],
        ["outside Canada bounding box", int(outside_ca.sum())],
        ["Alberta rows outside Alberta bounding box", int(ab_out.sum())],
        ["rows sharing exact coordinates with another row", int(dup.sum())],
        ["facility lat/lon present", int(df["Facility latitude"].notna().sum())],
    ]
    return "\n\n".join(
        [
            "## 7. Coordinates",
            md_table(rows, ["check", "rows"]),
            (
                "Many rows share exact coordinates (facilities such as compressor stations "
                "report the station location), so area-history features will cluster strongly."
            ),
        ]
    )


def taxonomy_mapping_rows(df: pd.DataFrame) -> list[list[object]]:
    codes = explode_list(df["Detailed what happened"], ";")
    mapped = codes.map(lambda c: classify_code(c))
    key = codes.str.replace(
        "Damage or deterioration mechanism, ", "DDM › ", regex=False
    )
    key = key.str.split(", ").str[:3].str.join(" › ")
    frame = pd.DataFrame(
        {
            "code": key,
            "group": mapped.map(lambda h: h[0] if h else "—"),
            "tier": mapped.map(lambda h: h[1] if h else "—"),
        }
    )
    agg = frame.groupby(["group", "tier", "code"]).size().reset_index(name="mentions")
    agg = agg.sort_values(["group", "mentions"], ascending=[True, False])
    return [
        [HAZARD_LABELS.get(r.group, r.group), r.tier, r.code, r.mentions]
        for r in agg.itertuples()
    ]


def group_counts(df: pd.DataFrame) -> list[list[object]]:
    year = df["event_date"].dt.year
    ab = df["is_alberta"]
    rows = []
    for g in HAZARD_GROUPS:
        m = df["hazard_group"].eq(g)
        nat, ab_n = int(m.sum()), int((m & ab).sum())
        ab_tr = int((m & ab & (year <= TRAIN_END_YEAR)).sum())
        ab_te = int((m & ab & (year > TRAIN_END_YEAR)).sum())
        flags = []
        if g in LOW_EVIDENCE_GROUPS:
            flags.append("low-evidence (flagged in UI)")
        if g in MODEL_TARGETS:
            if nat < SPARSE_NATIONAL:
                flags.append(f"<{SPARSE_NATIONAL} national")
            if ab_tr < SPARSE_ALBERTA_TRAIN:
                flags.append(f"<{SPARSE_ALBERTA_TRAIN} AB train")
            if ab_te < SPARSE_ALBERTA_TEST:
                flags.append(f"<{SPARSE_ALBERTA_TEST} AB test")
        else:
            flags.append("not a forecast target (evidence only)")
        rows.append(
            [
                HAZARD_LABELS[g],
                f"`{g}`",
                nat,
                pct(nat / len(df)),
                ab_n,
                pct(ab_n / ab.sum()),
                ab_tr,
                ab_te,
                ", ".join(flags) or "ok",
            ]
        )
    return rows


def section_proposed_taxonomy(df: pd.DataFrame) -> str:
    multi = df["Detailed what happened"].map(
        lambda d: len(all_hazards(d if isinstance(d, str) else None)) > 1
    )
    from_fallback = df["Detailed what happened"].isna()
    return "\n\n".join(
        [
            "## 8. Flowline hazard taxonomy (approved 2026-10-05)",
            (
                "Built from `Detailed what happened` codes, because the CER top-level "
                "`External Interference` category (807 mentions) is mostly *not* third-party "
                "damage — it also holds fire hazards, floods, defective tools and planning "
                "failures. Rule per incident: **tier 1** physical damage mechanism › **tier 2** "
                "specific condition (weather, fire/explosion hazard, defective tools) › **tier 3** "
                "human acts / other substandard conditions › **tier 4** unknown; first-listed code "
                "wins within a tier. Rows with no detailed code fall back to the top-level "
                f"category ({int(from_fallback.sum())} rows). Incidents whose codes span more than "
                f"one group: **{int(multi.sum())}** ({pct(multi.mean())}) — the primary group is "
                "kept, the full list is stored for display."
            ),
            (
                "Approved decisions: Corrosion and Cracking merged; ground movement and "
                "washout combined (slope / frost heave / subsidence alone is ~50 cases); fire "
                "comes only from the *Fire and explosion hazards* cause code (the *Fire* "
                "incident type is an outcome); *Frozen components* = weather; *Defective "
                "tools* = equipment failure. **Other / unknown** and **Undetermined** stay in "
                "the database and the evidence panel but are **not forecast targets**. "
                "Third-party damage stays its own group (distinct crew) and is flagged "
                "low-evidence."
            ),
            "### Group counts",
            md_table(
                group_counts(df),
                [
                    "hazard group",
                    "key",
                    "national",
                    "share",
                    "Alberta",
                    "AB share",
                    f"AB train ≤{TRAIN_END_YEAR}",
                    f"AB test ≥{TRAIN_END_YEAR + 1}",
                    "flags",
                ],
            ),
            "### Mapping: CER detailed code → hazard group",
            (
                "`DDM` = *Damage or deterioration mechanism*. Counts are code mentions (an "
                "incident can mention several codes)."
            ),
            md_table(
                taxonomy_mapping_rows(df),
                ["hazard group", "tier", "CER detailed code", "mentions"],
            ),
        ]
    )


# Candidate forecast features: (label, how to build it, available at forecast time?)
# "Available" = derivable from lat/lon + date + an independent source or user input.
CANDIDATE_FEATURES: tuple[tuple[str, str, str], ...] = (
    ("Latitude (binned)", "Latitude", "yes — map click"),
    ("Longitude (binned)", "Longitude", "yes — map click"),
    ("Province", "Province", "yes — from lat/lon"),
    ("Month of event", "_month", "yes — forecast date"),
    (
        "Occurrence date present (else discovered date)",
        "_occurred",
        "n/a — data quality",
    ),
    ("Operator group", "_operator", "yes — nearest system / user"),
    ("Commodity carried (CER systems layer)", "_commodity", "yes — systems layer"),
    ("Substance carried (incident record)", "Substance carried", "no"),
    ("Pipeline or Facility Type (incident record)", "Pipeline or Facility Type", "no"),
    ("Facility Name", "Facility Name", "no"),
    ("Facility Type", "Facility Type", "no"),
    ("Facility latitude", "Facility latitude", "no"),
    ("Pipeline Name", "Pipeline Name", "no"),
    ("Kilometre post", "Kilometre post", "no"),
    ("Pipeline outside diameter (NPS)", "Pipeline outside diameter (NPS)", "no"),
    ("Regulation (OPR / PPR)", "Regulation", "partly — by operator"),
    ("Land Use", "Land Use", "only via land-cover layer"),
    ("Population Density", "Population Density", "only via census layer"),
)


def candidate_values(df: pd.DataFrame, source: str) -> pd.Series:
    """Feature values with placeholders as NaN; numeric columns binned."""
    if source == "_month":
        return df["event_date"].dt.month.astype("float")
    if source == "_occurred":
        return df["occurred"].dt.month.astype("float")
    if source == "_operator":
        return df["Company"].map(operator_group)
    if source == "_commodity":
        return df["Company"].map(commodity_carried).replace(UNKNOWN, pd.NA)
    s = df[source]
    if pd.api.types.is_numeric_dtype(s) and s.nunique() > 20:
        return pd.qcut(s, 10, duplicates="drop").astype("string")
    s = s.astype("string").str.strip()
    return s.mask(s.str.match(PLACEHOLDER_RE) | s.eq(""))


def feature_decision(verdict: str, available: str) -> str:
    if available.startswith("n/a"):
        return "never a feature (see note)"
    if verdict.startswith("LEAKS"):
        return "**exclude**"
    if available.startswith("no"):
        return "exclude (not known at forecast time)"
    if available.startswith(("only via", "partly")):
        return "only if joined from that source"
    return "candidate" + (" (watch)" if verdict == "caution" else "")


def section_leakage(df: pd.DataFrame) -> str:
    model = df[df["hazard_group"].isin(MODEL_TARGETS)]
    y = model["hazard_group"]
    rows = []
    for label, source, available in CANDIDATE_FEATURES:
        r = leakage_row(candidate_values(model, source), y)
        rows.append(
            [
                label,
                pct(r["missing"]),
                f"{pct(r['missing_min'])} – {pct(r['missing_max'])}",
                HAZARD_LABELS.get(r["missing_max_class"], "—")
                if r["missing"] > 0
                else "—",
                r["missing_v"],
                r["value_v"],
                r["verdict"],
                available,
                feature_decision(str(r["verdict"]), available),
            ]
        )
    header = [
        "candidate feature",
        "% missing",
        "missing range across classes",
        "most-missing class",
        "V(missing, class)",
        "V(value, class)",
        "leakage verdict",
        "available at forecast time",
        "decision",
    ]
    return "\n\n".join(
        [
            "## 9. Leakage check — every candidate feature",
            (
                f"Rows: the {len(model):,} incidents whose hazard group is a forecast "
                "target. `V(missing, class)` is bias-corrected Cramér's V between the "
                "feature's missing-indicator and the hazard class: if *whether a field is "
                "filled* depends on what went wrong, the field was recorded because of the "
                f"outcome. Verdict: ≥ {LEAK_V} = leaks, ≥ {CAUTION_V} = caution. "
                "`V(value, class)` is the association of the filled values with the class "
                "(signal, or leakage if the field is post-event). Placeholders (*Not "
                "Applicable*, *Unknown*…) count as missing; numeric columns are binned "
                "into deciles."
            ),
            md_table(rows, header),
            (
                "**Commodity carried** is derived from the incident's operator via the CER "
                "Pipeline Systems layer (`data/cer_pipeline_systems.csv`, "
                "`core/operators.py`), not from any release field. Where the incident's own "
                "*Substance carried* is filled, the two agree on gas vs liquid in all but "
                "one row. Its missingness is low and not class-dependent; it is a candidate "
                "feature."
            ),
            (
                "**Facility vs pipeline:** every facility indicator in the incident record "
                "(*Facility Name*, *Facility Type*, *Pipeline or Facility Type*, *Pipeline "
                "Name*) is filled conditional on the cause, so none may be a feature. At "
                "forecast time a facility/line-pipe choice can only come from user input "
                "or an independent facility list; it is not trained from these columns."
            ),
            (
                "**Event date source:** the occurrence date is missing for most "
                "geotechnical incidents (washouts are *discovered*, not seen happening), so "
                "their event date is the discovery date. Weather windows are anchored on "
                "`event_date` for every incident; the date-source flag itself is never a "
                "feature, because it alone would reveal the class. Consequence for "
                'interpretation: for washouts, "prior 7/30 days" means before discovery.'
            ),
            (
                "**Weather (Phase 3), distance to pipeline and area history (Phase 6)** are "
                "computed from independent sources; their missingness vs class is checked "
                "in `docs/MODEL_REPORT.md` once built."
            ),
        ]
    )


def build_report(raw: pd.DataFrame, dd: pd.DataFrame) -> str:
    df = add_derived(raw)
    header = (
        "# CER Pipeline Incident Data — Profile\n\n"
        f"Generated by `scripts/profile_cer.py` on {datetime.now(UTC):%Y-%m-%d} from "
        "`data/raw/pipeline-incidents-comprehensive-data.csv` (Canada Energy Regulator, "
        "Open Government Licence – Canada). File encoding: cp1252."
    )
    sections = [
        header,
        section_overview(df, raw.shape[1]),
        section_dates(df),
        section_columns(raw, dd),
        section_narrative(raw),
        section_pipe(df),
        section_cer_taxonomy(raw),
        section_coordinates(df),
        section_proposed_taxonomy(df),
        section_leakage(df),
    ]
    return "\n\n".join(sections) + "\n"


def main() -> None:
    raw, dd = load_raw()
    OUT_PATH.write_text(build_report(raw, dd), encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(ROOT)} ({len(raw):,} rows profiled)")


if __name__ == "__main__":
    main()
