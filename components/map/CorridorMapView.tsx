"use client";

import dynamic from "next/dynamic";
import { useCallback, useState } from "react";
import type { RankingRow } from "@/lib/types";
import { SvgCorridorMap } from "./SvgCorridorMap";

const AlbertaMapbox = dynamic(() => import("./AlbertaMapbox"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full min-h-0 items-center justify-center rounded-lg bg-[#FAFAF8] text-[12px] text-[#8A8E94]">
      Loading map…
    </div>
  ),
});

type Props = {
  ranking: RankingRow[];
  selected: string | null;
  onSelect: (corridor: string) => void;
};

function MapLegend() {
  return (
    <>
      <div
        className="mt-3 flex flex-wrap gap-3.5 text-[12px] text-[#5A5F66]"
        style={{ flex: "0 0 auto" }}
      >
        <LegendDot color="#A8370A" label="3+ serious" />
        <LegendDot color="#E0904A" label="1–2 serious" />
        <LegendDot color="#9C9FA5" label="minor only" />
        <LegendLine label="CER-regulated pipelines" />
      </div>
      <p className="mt-1.5 text-[11px] text-[#8A8E94]">
        Pipeline routes: Canada Energy Regulator.
      </p>
    </>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block rounded-full"
        style={{ width: 10, height: 10, background: color }}
      />
      {label}
    </span>
  );
}

function LegendLine({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block"
        style={{
          width: 14,
          height: 2,
          background: "#B9A58F",
          opacity: 0.85,
          borderRadius: 1,
        }}
      />
      {label}
    </span>
  );
}

/**
 * Map tab content: Mapbox when a public token is present, SVG offline fallback otherwise.
 */
export function CorridorMapView({ ranking, selected, onSelect }: Props) {
  const token = (process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "").trim();
  const [useMapbox, setUseMapbox] = useState(() => token.length > 0);

  const onFallback = useCallback(() => {
    setUseMapbox(false);
  }, []);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1" style={{ minHeight: 0 }}>
        {useMapbox && token ? (
          <AlbertaMapbox
            token={token}
            ranking={ranking}
            selected={selected}
            onSelect={onSelect}
            onFallback={onFallback}
          />
        ) : (
          <SvgCorridorMap
            ranking={ranking}
            selected={selected}
            onSelect={onSelect}
            offlineNote
          />
        )}
      </div>
      <MapLegend />
    </div>
  );
}
