"use client";

import { hazardColor } from "@/lib/hazards";
import type { SimilarIncident } from "@/lib/forecastTypes";
import { PanelMessage } from "./ForecastPanel";

type Props = {
  incidents: SimilarIncident[] | null;
  referenceDate: string | null;
  loading: boolean;
  onFocus: (s: SimilarIncident) => void;
};

export function EvidencePanel({ incidents, referenceDate, loading, onFocus }: Props) {
  return (
    <section aria-labelledby="evidence-h" className="flex shrink-0 flex-col">
      <h2 id="evidence-h" className="mb-1 text-[13px] font-semibold uppercase tracking-[0.08em] text-muted">
        Similar past incidents
      </h2>
      <p className="mb-2 text-[11px] text-muted">
        Matched on place, season, weather and commodity — only incidents before{" "}
        {referenceDate ?? "the forecast date"}. Narrative search is ready for operator incident
        narratives in a pilot; public CER data only has cause codes.
      </p>
      {!incidents && loading ? (
        <div className="grid gap-2" aria-busy aria-label="Loading similar incidents">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="h-14 animate-pulse rounded bg-panel-2" />
          ))}
        </div>
      ) : !incidents ? (
        <PanelMessage text="Similar incidents appear after a forecast." />
      ) : incidents.length === 0 ? (
        <PanelMessage text="No earlier incidents to compare with." />
      ) : (
        <ol className={`grid gap-1.5 ${loading ? "opacity-60" : ""}`}>
          {incidents.map((s) => (
            <li key={s.incident_number}>
              <button
                type="button"
                onClick={() => onFocus(s)}
                className="w-full rounded-md border border-border bg-panel-2/40 px-2 py-1.5 text-left hover:border-accent focus-visible:border-accent"
                title="Show on map"
              >
                <div className="flex items-center justify-between gap-2 text-[12px]">
                  <span className="flex min-w-0 items-center gap-1.5">
                    <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ background: hazardColor(s.hazard_group) }} />
                    <span className="truncate text-fg">{s.hazard_label}</span>
                  </span>
                  <span className="shrink-0 font-mono text-[11px] text-muted"
                    title="Similarity score (0–1) from distance in place, season, weather and commodity — not a probability">
                    similarity {s.similarity.toFixed(2)}
                  </span>
                </div>
                <div className="text-[11px] text-muted">
                  {s.date} · {s.place} · {s.distance_km} km away
                  {!s.weather_known && " · weather unknown"}
                </div>
                <div className="mt-0.5 line-clamp-2 text-[11px] text-fg/80">{s.snippet}</div>
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
