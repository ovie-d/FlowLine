"""Print the five Case 10 required deliverable steps."""

from __future__ import annotations

from core.compare import compare
from core.config import (
    BASELINE_COUNT,
    CONSEQUENCE_HEAVY,
    DEFAULT,
    LOW_CONSEQUENCE,
)
from core.data import load_incidents
from core.scoring import score


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
    print(f"Overlap count-only vs weighted (high=3): {vs_count['overlap']}/15")
    vs_heavy = compare(DEFAULT, CONSEQUENCE_HEAVY, top=15)
    print(f"Overlap weighted (high=3) vs heavy (high=6): {vs_heavy['overlap']}/15")
    low = score(LOW_CONSEQUENCE, top=1)[0]
    heavy = score(CONSEQUENCE_HEAVY, top=1)[0]
    print(
        f"Flip check: low-consequence #1={low['corridor']}; "
        f"heavy #1={heavy['corridor']}"
    )

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
