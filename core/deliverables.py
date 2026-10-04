"""Print the five Case 10 required deliverable steps."""

from __future__ import annotations

from core.compare import compare, improvement_round
from core.config import (
    BASELINE_COUNT,
    CONSEQUENCE_HEAVY,
    DEFAULT,
    LOW_CONSEQUENCE,
)
from core.data import load_incidents
from core.labels import LOW_CONFIDENCE_LABEL
from core.scoring import score


def _print_overlap(label: str, result: dict) -> None:
    print(f"Overlap {label}: {result['overlap']}/15")
    print(f"  entered={result['entered']}")
    print(f"  dropped={result['dropped']}")


def _jenner_line() -> str:
    count_rows = score(BASELINE_COUNT, top=100)
    weighted_rows = score(DEFAULT, top=100)
    count = next(r for r in count_rows if r["corridor"] == "Jenner")
    weighted = next(r for r in weighted_rows if r["corridor"] == "Jenner")
    return (
        f"Jenner: count-only #{count['rank']} -> weighted #{weighted['rank']} "
        f"({weighted['n']} incidents, both high; "
        f"{LOW_CONFIDENCE_LABEL})"
    )


def _print_improvement_round() -> None:
    round_ = improvement_round(top=15)
    print("\n=== Improvement round (same weights, label-independent yardstick) ===")
    for stage in round_["stages"]:
        top5 = ", ".join(stage["top5"])
        print(
            f"  {stage['stage']:<10} serious {stage['serious_captured']}/"
            f"{stage['serious_total']}  incidents {stage['incidents_covered']}  "
            f"top5: {top5}"
        )
    heavy = round_["ours_heavy"]
    top5 = ", ".join(heavy["top5"])
    print(
        f"  {heavy['stage']:<10} serious {heavy['serious_captured']}/"
        f"{heavy['serious_total']}  incidents {heavy['incidents_covered']}  "
        f"top5: {top5}"
    )
    print(f"  -> {round_['summary']}")


def run() -> None:
    df, report = load_incidents(DEFAULT)

    # Step 1 — rows loaded / dropped (no date)
    print("=== Step 1: Load ===")
    print(
        f"Loaded {report['rows_loaded']} rows. "
        f"Dropped {report['rows_dropped_no_date']} rows with no date. "
        f"Scoring {report['rows_scored']} incidents."
    )
    print(
        f"(Upstream seed already excluded {report['upstream_dropped_no_date']} "
        "Alberta filings with no usable date — mostly serious-injury records.)"
    )

    # Step 2 — corridors before/after cleaning; incident counts
    print("\n=== Step 2: Clean + group ===")
    print(
        f"Corridors before cleaning: {report['corridors_before']}. "
        f"After aliases + junk snaps: {report['corridors_after']}."
    )
    if report["alias_merges"]:
        print("Alias merges:")
        for k, v in sorted(report["alias_merges"].items()):
            print(f"  {k}: {v}")
    if report["snaps"]:
        print("Junk snaps:")
        for s in report["snaps"]:
            print(
                f"  {s['corridor_raw']!r} -> {s['snapped_to']!r} "
                f"({s['distance_km']} km)"
            )
    counts = df.groupby("corridor").size().sort_values(ascending=False).head(10)
    print("Top corridors by incident count:")
    for name, n in counts.items():
        print(f"  {name}: {int(n)}")

    # Step 3 — Top 15 by count × consequence (our default weighted ranking)
    print("\n=== Step 3: Top 15 (count x consequence, severity_v2) ===")
    ranked = score(DEFAULT, top=15)
    for r in ranked:
        print(
            f"  #{r['rank']:2d} {r['corridor']:24s}  score={r['score']:5.1f}  "
            f"n={r['n']:2d}  n_high={r['n_high']}  "
            f"L={r['likelihood']:.1f}  C={r['consequence']:.2f}  "
            f"conf={r['confidence']}"
        )

    # Step 4 — vs count-only; raise high weight; overlap again
    print("\n=== Step 4: Overlap vs count-only; heavier high weight ===")
    vs_count = compare(BASELINE_COUNT, DEFAULT, top=15)
    _print_overlap("count-only vs weighted (high=3)", vs_count)
    vs_heavy = compare(DEFAULT, CONSEQUENCE_HEAVY, top=15)
    _print_overlap("weighted (high=3) vs heavy (high=6)", vs_heavy)
    low = score(LOW_CONSEQUENCE, top=1)[0]
    heavy = score(CONSEQUENCE_HEAVY, top=1)[0]
    print(
        f"Flip check: low-consequence #1={low['corridor']}; "
        f"heavy #1={heavy['corridor']}"
    )
    print(_jenner_line())

    _print_improvement_round()

    # Step 5 — three corridors that rose or fell, with reasons
    print("\n=== Step 5: Three corridors that moved (count-only -> heavy) ===")
    moved = compare(BASELINE_COUNT, CONSEQUENCE_HEAVY, top=15)
    shown = 0
    for m in moved["movers"]:
        if m["from"] is None or m["to"] is None:
            continue
        direction = "rose" if (m["delta"] or 0) > 0 else "fell"
        print(
            f"  {m['corridor']}: #{m['from']} -> #{m['to']} "
            f"({direction}, reason={m['reason']})"
        )
        shown += 1
        if shown >= 3:
            break

    print(
        "\nHonesty: we rank historic incident hotspots under an explicit "
        "risk policy. We do not certify any pipe as safe."
    )


def main() -> None:
    run()


if __name__ == "__main__":
    main()
