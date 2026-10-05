"use client";

import dynamic from "next/dynamic";
import { useCallback, useState } from "react";
import { HAZARD_ORDER, HAZARD_COLOR, HAZARD_SHORT, type HazardGroup } from "@/lib/hazards";
import { HazardSvgMap } from "./HazardSvgMap";
import type { MapViewProps } from "./mapTypes";

const HazardMapbox = dynamic(() => import("./HazardMapbox"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-panel" aria-label="Loading map" />,
});

/** Mapbox dark basemap when a token is set; SVG offline view otherwise (or on failure). */
export function HazardMap(
  props: MapViewProps & { onToggleHazard: (g: HazardGroup) => void },
) {
  const token = (process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "").trim();
  const [useMapbox, setUseMapbox] = useState(token.length > 0);
  const onFallback = useCallback(() => setUseMapbox(false), []);
  const { onToggleHazard, ...mapProps } = props;

  return (
    <div className="relative h-full w-full overflow-hidden">
      {useMapbox ? (
        <HazardMapbox token={token} onFallback={onFallback} {...mapProps} />
      ) : (
        <HazardSvgMap {...mapProps} />
      )}
      <MapLegend hidden={props.hiddenHazards} onToggle={onToggleHazard} />
      {props.pickMode === "dispatch" && (
        <div className="pointer-events-none absolute left-1/2 top-3 -translate-x-1/2 rounded-md border border-accent bg-panel px-3 py-1.5 text-[12px] text-fg shadow">
          Emergency dispatch: click the incident location on the map
        </div>
      )}
    </div>
  );
}

function MapLegend({
  hidden,
  onToggle,
}: {
  hidden: Set<HazardGroup>;
  onToggle: (g: HazardGroup) => void;
}) {
  return (
    <div className="absolute bottom-2 right-2 max-w-[230px] rounded-md border border-border bg-panel/90 p-2 text-[11px] backdrop-blur">
      <div className="mb-1 font-semibold text-muted">Past incidents by hazard</div>
      <ul className="grid gap-0.5">
        {HAZARD_ORDER.map((g) => (
          <li key={g}>
            <button
              type="button"
              aria-pressed={!hidden.has(g)}
              onClick={() => onToggle(g)}
              className={`flex w-full items-center gap-1.5 rounded px-1 text-left hover:bg-panel-2 ${hidden.has(g) ? "opacity-40" : ""}`}
            >
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: HAZARD_COLOR[g] }} />
              <span className="text-fg">{HAZARD_SHORT[g]}</span>
            </button>
          </li>
        ))}
        <li className="flex items-center gap-1.5 px-1 text-muted">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: HAZARD_COLOR.other_unknown }} />
          Other / unknown
        </li>
        <li className="flex items-center gap-1.5 px-1 text-muted">
          <span className="inline-block h-0.5 w-3" style={{ background: "#2DD4BF", opacity: 0.6 }} />
          CER pipeline systems
        </li>
        <li className="flex items-center gap-1.5 px-1 text-muted">
          <span className="inline-block h-2.5 w-2.5 rounded-sm border-2 border-fg" />
          Crew base (sample)
        </li>
      </ul>
    </div>
  );
}
