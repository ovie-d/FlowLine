"use client";

import { maplibreLib } from "./maplibreSetup";
import AlbertaMapbox from "./AlbertaMapbox";
import type { RankingRow } from "@/lib/types";

/** Ranking map on the keyless open basemap (no Mapbox token). */
export default function AlbertaMaplibre(props: {
  ranking: RankingRow[];
  selected: string | null;
  onSelect: (corridor: string) => void;
  onFallback: () => void;
}) {
  return <AlbertaMapbox lib={maplibreLib} {...props} />;
}
