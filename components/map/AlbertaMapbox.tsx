"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Map, {
  Layer,
  NavigationControl,
  Source,
  type MapMouseEvent,
  type MapRef,
} from "react-map-gl/mapbox";
import type { RankingRow } from "@/lib/types";
import type { FeatureCollection } from "geojson";
import "mapbox-gl/dist/mapbox-gl.css";

const ALBERTA_BOUNDS: [[number, number], [number, number]] = [
  [-120, 49],
  [-110, 60],
];

const LOAD_TIMEOUT_MS = 8000;

type Props = {
  token: string;
  ranking: RankingRow[];
  selected: string | null;
  onSelect: (corridor: string) => void;
  onFallback: () => void;
};

type CorridorFeatureCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    properties: {
      corridor: string;
      rank: number;
      score: number;
      n_high: number;
      selected: number;
      color: string;
      radius: number;
    };
    geometry: {
      type: "Point";
      coordinates: [number, number];
    };
  }>;
};

function corridorColor(nHigh: number): string {
  if (nHigh >= 3) return "#A8370A";
  if (nHigh >= 1) return "#E0904A";
  return "#9C9FA5";
}

function buildCorridors(
  ranking: RankingRow[],
  selected: string | null,
): CorridorFeatureCollection {
  const maxScore = ranking[0]?.score || 1;
  const features: CorridorFeatureCollection["features"] = [];
  for (const row of ranking) {
    if (
      row.lat == null ||
      row.lon == null ||
      !Number.isFinite(row.lat) ||
      !Number.isFinite(row.lon)
    ) {
      continue;
    }
    features.push({
      type: "Feature",
      properties: {
        corridor: row.corridor,
        rank: row.rank,
        score: row.score,
        n_high: row.n_high,
        selected: row.corridor === selected ? 1 : 0,
        color: corridorColor(row.n_high),
        radius: 6 + (14 * row.score) / maxScore,
      },
      geometry: {
        type: "Point",
        coordinates: [row.lon, row.lat],
      },
    });
  }
  return { type: "FeatureCollection", features };
}

export default function AlbertaMapbox({
  token,
  ranking,
  selected,
  onSelect,
  onFallback,
}: Props) {
  const mapRef = useRef<MapRef | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const fellBack = useRef(false);
  const loaded = useRef(false);
  const [pipelines, setPipelines] = useState<FeatureCollection | null>(null);
  const [cursor, setCursor] = useState<string>("grab");

  const fallback = useCallback(() => {
    if (fellBack.current || loaded.current) return;
    fellBack.current = true;
    onFallback();
  }, [onFallback]);

  useEffect(() => {
    let cancelled = false;
    fetch("/pipelines_ab.geojson")
      .then((res) => {
        if (!res.ok) throw new Error(String(res.status));
        return res.json();
      })
      .then((data: FeatureCollection) => {
        if (!cancelled) setPipelines(data);
      })
      .catch(() => {
        /* skip pipeline layer silently */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const id = window.setTimeout(() => {
      if (!loaded.current) fallback();
    }, LOAD_TIMEOUT_MS);
    return () => window.clearTimeout(id);
  }, [fallback]);

  const fitAlberta = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    map.fitBounds(ALBERTA_BOUNDS, { padding: 20, duration: 0 });
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => {
      mapRef.current?.resize();
      fitAlberta();
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [fitAlberta]);

  const corridors = useMemo(
    () => buildCorridors(ranking, selected),
    [ranking, selected],
  );

  const onClick = useCallback(
    (e: MapMouseEvent) => {
      const feature = e.features?.[0];
      const name = feature?.properties?.corridor;
      if (typeof name === "string" && name) onSelect(name);
    },
    [onSelect],
  );

  return (
    <div ref={containerRef} className="h-full min-h-0 w-full overflow-hidden rounded-lg">
      <Map
        ref={mapRef}
        mapboxAccessToken={token}
        mapStyle="mapbox://styles/mapbox/light-v11"
        initialViewState={{
          bounds: ALBERTA_BOUNDS,
          fitBoundsOptions: { padding: 20 },
        }}
        style={{ width: "100%", height: "100%" }}
        minZoom={3.5}
        maxZoom={9}
        scrollZoom={false}
        dragRotate={false}
        pitchWithRotate={false}
        touchPitch={false}
        attributionControl
        cursor={cursor}
        interactiveLayerIds={["corridors-circle"]}
        onLoad={() => {
          loaded.current = true;
          fitAlberta();
        }}
        onError={() => {
          if (!loaded.current) fallback();
        }}
        onClick={onClick}
        onMouseEnter={() => setCursor("pointer")}
        onMouseLeave={() => setCursor("grab")}
      >
        <NavigationControl
          position="top-right"
          showCompass={false}
          visualizePitch={false}
        />

        {pipelines && (
          <Source id="pipelines" type="geojson" data={pipelines}>
            <Layer
              id="pipelines-line"
              type="line"
              paint={{
                "line-color": "#B9A58F",
                "line-opacity": 0.8,
                "line-width": [
                  "interpolate",
                  ["linear"],
                  ["zoom"],
                  3.5,
                  1,
                  7,
                  1.5,
                ],
              }}
            />
          </Source>
        )}

        <Source id="corridors" type="geojson" data={corridors}>
          <Layer
            id="corridors-circle"
            type="circle"
            paint={{
              "circle-radius": ["get", "radius"],
              "circle-color": ["get", "color"],
              "circle-stroke-width": 2,
              "circle-stroke-color": "#FFFFFF",
            }}
          />
          <Layer
            id="corridors-selected"
            type="circle"
            filter={["==", ["get", "selected"], 1]}
            paint={{
              "circle-radius": ["+", ["get", "radius"], 4],
              "circle-opacity": 0,
              "circle-stroke-width": 3,
              "circle-stroke-color": "#1D4ED8",
            }}
          />
          <Layer
            id="corridors-rank"
            type="symbol"
            filter={["<=", ["get", "rank"], 5]}
            layout={{
              "text-field": ["to-string", ["get", "rank"]],
              "text-size": 11,
              "text-font": ["DIN Pro Bold", "Arial Unicode MS Bold"],
              "text-allow-overlap": true,
              "text-ignore-placement": true,
            }}
            paint={{
              "text-color": "#FFFFFF",
            }}
          />
          <Layer
            id="corridors-name"
            type="symbol"
            filter={["<=", ["get", "rank"], 5]}
            layout={{
              "text-field": ["get", "corridor"],
              "text-size": 12,
              "text-font": ["DIN Pro Medium", "Arial Unicode MS Regular"],
              "text-offset": [1.2, 0],
              "text-anchor": "left",
              "text-allow-overlap": false,
            }}
            paint={{
              "text-color": "#15171A",
              "text-halo-color": "#FFFFFF",
              "text-halo-width": 1.5,
            }}
          />
        </Source>
      </Map>
    </div>
  );
}
