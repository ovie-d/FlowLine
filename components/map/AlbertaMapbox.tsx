"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Map, {
  Layer,
  NavigationControl,
  Popup,
  Source,
  type MapMouseEvent,
  type MapRef,
} from "react-map-gl/mapbox";
import type { Map as MapboxMap } from "mapbox-gl";
import type { RankingRow } from "@/lib/types";
import type { FeatureCollection, Position } from "geojson";
import "mapbox-gl/dist/mapbox-gl.css";

const ALBERTA_BOUNDS: [[number, number], [number, number]] = [
  [-120, 49],
  [-110, 60],
];

const LOAD_TIMEOUT_MS = 8000;
const FIT_PADDING = 16;

type StyleKey = "light-plus" | "outdoors" | "streets";

const STYLE_URLS: Record<StyleKey, string> = {
  "light-plus": "mapbox://styles/mapbox/light-v11",
  outdoors: "mapbox://styles/mapbox/outdoors-v12",
  streets: "mapbox://styles/mapbox/streets-v12",
};

const STYLE_BUTTONS: { key: StyleKey; label: string }[] = [
  { key: "light-plus", label: "Light+" },
  { key: "outdoors", label: "Outdoors" },
  { key: "streets", label: "Streets" },
];

/**
 * Same outline as the SVG map (viewBox points → lon/lat via the SVG projection).
 * x = (lon+120)*10, y = (60-lat)*(100/11)
 */
const AB_OUTLINE_COORDS: Position[] = [
  [-120, 60],
  [-110, 60],
  [-110, 49],
  [-114.06, 49],
  [-114.7, 50],
  [-115.4, 50.8],
  [-116.3, 51.5],
  [-117.3, 52.2],
  [-118.3, 52.9],
  [-119.2, 53.5],
  [-120, 53.9],
  [-120, 60],
];

const AB_BORDER_GEOJSON: FeatureCollection = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: {},
      geometry: {
        type: "LineString",
        coordinates: AB_OUTLINE_COORDS,
      },
    },
  ],
};

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
      sort_key: number;
    };
    geometry: {
      type: "Point";
      coordinates: [number, number];
    };
  }>;
};

type HoverInfo = {
  longitude: number;
  latitude: number;
  corridor: string;
  rank: number;
  score: number;
};

function resolveDefaultStyle(): StyleKey {
  const raw = (process.env.NEXT_PUBLIC_MAP_STYLE ?? "light-plus")
    .trim()
    .toLowerCase();
  if (raw === "outdoors" || raw === "streets" || raw === "light-plus") {
    return raw;
  }
  return "light-plus";
}

function setPaintSafe(
  map: MapboxMap,
  layerId: string,
  prop: string,
  value: unknown,
) {
  if (!map.getLayer(layerId)) return;
  try {
    map.setPaintProperty(layerId, prop as never, value as never);
  } catch {
    /* skip */
  }
}

function applyLightPlusTint(map: MapboxMap) {
  setPaintSafe(map, "background", "background-color", "#F7F5F0");
  setPaintSafe(map, "land", "background-color", "#F7F5F0");

  setPaintSafe(map, "water", "fill-color", "#BFD8EE");
  setPaintSafe(map, "water-shadow", "fill-color", "#BFD8EE");

  setPaintSafe(map, "waterway", "line-color", "#9EC4E6");
  setPaintSafe(map, "waterway-label", "text-color", "#9EC4E6");

  for (const id of ["landcover", "landuse", "park", "national-park", "pitch"]) {
    setPaintSafe(map, id, "fill-color", "#E8EFE3");
    setPaintSafe(map, id, "fill-opacity", 0.35);
  }
}

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
        sort_key: -row.rank,
      },
      geometry: {
        type: "Point",
        coordinates: [row.lon, row.lat],
      },
    });
  }
  return { type: "FeatureCollection", features };
}

function featureHoverInfo(feature: {
  geometry?: { coordinates?: number[] } | { type: string };
  properties?: Record<string, unknown> | null;
}): HoverInfo | null {
  const coords =
    feature.geometry && "coordinates" in feature.geometry
      ? feature.geometry.coordinates
      : undefined;
  const props = feature.properties;
  if (!coords || !Array.isArray(coords) || coords.length < 2 || !props) {
    return null;
  }
  const corridor = String(props.corridor ?? "");
  if (!corridor) return null;
  return {
    longitude: Number(coords[0]),
    latitude: Number(coords[1]),
    corridor,
    rank: Number(props.rank),
    score: Number(props.score),
  };
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
  const styleLoadCount = useRef(0);
  const prevSelected = useRef<string | null>(null);
  const [pipelines, setPipelines] = useState<FeatureCollection | null>(null);
  const [cursor, setCursor] = useState<string>("grab");
  const [styleKey, setStyleKey] = useState<StyleKey>(resolveDefaultStyle);
  const [devSwitcher, setDevSwitcher] = useState(false);
  // Mount overlay layers only after the basemap has loaded (avoids empty dots).
  const [mapReady, setMapReady] = useState(false);
  const [styleEpoch, setStyleEpoch] = useState(0);
  const [hover, setHover] = useState<HoverInfo | null>(null);

  const fallback = useCallback(() => {
    if (fellBack.current || loaded.current) return;
    fellBack.current = true;
    // Defer — Mapbox may fire onError during Layer render.
    queueMicrotask(() => onFallback());
  }, [onFallback]);

  useEffect(() => {
    try {
      setDevSwitcher(
        new URLSearchParams(window.location.search).get("mapstyle") === "dev",
      );
    } catch {
      setDevSwitcher(false);
    }
  }, []);

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
        /* skip */
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
    map.fitBounds(ALBERTA_BOUNDS, { padding: FIT_PADDING, duration: 0 });
  }, []);

  const onStyleReady = useCallback(
    (map: MapboxMap, remountOverlays: boolean) => {
      if (styleKey === "light-plus") applyLightPlusTint(map);
      fitAlberta();
      setHover(null);
      setMapReady(true);
      // Remount overlays only on later style swaps — not the first load —
      // so corridor dots aren't wiped by a remount race.
      if (remountOverlays) setStyleEpoch((n) => n + 1);
    },
    [styleKey, fitAlberta],
  );

  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    const handler = () => {
      styleLoadCount.current += 1;
      // First style.load = initial basemap; remount only on later style swaps.
      onStyleReady(map, styleLoadCount.current > 1);
    };
    map.on("style.load", handler);
    return () => {
      map.off("style.load", handler);
    };
  }, [onStyleReady]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    let first = true;
    const ro = new ResizeObserver(() => {
      mapRef.current?.resize();
      // Fit once after layout settles; later resizes only call resize()
      // so pan/zoom aren't snapped back to Alberta.
      if (first) {
        first = false;
        fitAlberta();
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [fitAlberta]);

  // Fly to selected corridor (list / dot / agent explain) — skip initial mount.
  useEffect(() => {
    if (!selected) {
      prevSelected.current = selected;
      return;
    }
    if (prevSelected.current === null) {
      prevSelected.current = selected;
      return;
    }
    if (selected === prevSelected.current) return;
    prevSelected.current = selected;

    const row = ranking.find((r) => r.corridor === selected);
    if (
      !row ||
      row.lat == null ||
      row.lon == null ||
      !Number.isFinite(row.lat) ||
      !Number.isFinite(row.lon)
    ) {
      return;
    }
    mapRef.current?.flyTo({
      center: [row.lon, row.lat],
      zoom: 7.5,
      duration: 900,
    });
  }, [selected, ranking]);

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

  const onMouseMove = useCallback((e: MapMouseEvent) => {
    const feature = e.features?.[0];
    if (!feature) {
      setHover(null);
      setCursor("grab");
      return;
    }
    const info = featureHoverInfo(feature);
    setHover(info);
    setCursor("pointer");
  }, []);

  const onMouseLeave = useCallback(() => {
    setHover(null);
    setCursor("grab");
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative h-full min-h-0 w-full overflow-hidden rounded-lg"
    >
      <div
        className="absolute z-10 flex flex-col gap-1"
        style={{ top: 8, left: 8 }}
      >
        <button
          type="button"
          onClick={fitAlberta}
          className="rounded border border-[#DCDCD7] bg-white px-2 text-[11px] font-semibold text-[#3A3E44]"
          style={{ minHeight: 26, width: "fit-content" }}
        >
          Reset view
        </button>
        {devSwitcher && (
          <div className="flex gap-1">
            {STYLE_BUTTONS.map(({ key, label }) => {
              const active = styleKey === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setStyleKey(key)}
                  className="rounded border px-2 text-[11px] font-semibold"
                  style={{
                    minHeight: 26,
                    background: active ? "#15171A" : "#FFFFFF",
                    color: active ? "#FFFFFF" : "#3A3E44",
                    borderColor: active ? "#15171A" : "#DCDCD7",
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <Map
        ref={mapRef}
        mapboxAccessToken={token}
        mapStyle={STYLE_URLS[styleKey]}
        initialViewState={{
          bounds: ALBERTA_BOUNDS,
          fitBoundsOptions: { padding: FIT_PADDING },
        }}
        style={{ width: "100%", height: "100%" }}
        minZoom={2.5}
        maxZoom={9}
        dragRotate={false}
        pitchWithRotate={false}
        touchPitch={false}
        attributionControl
        cursor={cursor}
        interactiveLayerIds={["corridors-circle"]}
        onLoad={(e) => {
          loaded.current = true;
          onStyleReady(e.target, false);
        }}
        onError={(e) => {
          // Ignore transient layer/source noise; only bail on auth/style load failure
          // before the map has successfully loaded.
          if (loaded.current) return;
          const msg = String(
            (e as { error?: { message?: string } })?.error?.message ?? "",
          ).toLowerCase();
          const fatal =
            msg.includes("unauthorized") ||
            msg.includes("401") ||
            msg.includes("403") ||
            msg.includes("not authorized") ||
            msg.includes("failed to fetch") ||
            msg.includes("failed to load style");
          if (fatal) fallback();
        }}
        onClick={onClick}
        onMouseMove={onMouseMove}
        onMouseLeave={onMouseLeave}
      >
        <NavigationControl
          position="top-right"
          showCompass={false}
          visualizePitch={false}
        />

        {mapReady && (
          <>
            {/* Alberta border — above basemap land, below pipelines */}
            <Source
              key={`ab-border-${styleEpoch}`}
              id="alberta-border"
              type="geojson"
              data={AB_BORDER_GEOJSON}
            >
              <Layer
                id="alberta-border-line"
                type="line"
                paint={{
                  "line-color": "#8F8A80",
                  "line-width": 1,
                  "line-dasharray": [3, 2],
                  "line-opacity": 0.9,
                }}
              />
            </Source>

            {pipelines && (
              <Source
                key={`pipelines-${styleEpoch}`}
                id="pipelines"
                type="geojson"
                data={pipelines}
              >
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

            <Source
              key={`corridors-${styleEpoch}`}
              id="corridors"
              type="geojson"
              data={corridors}
            >
              <Layer
                id="corridors-circle"
                type="circle"
                layout={
                  {
                    "circle-sort-key": ["get", "sort_key"],
                  } as never
                }
                paint={
                  {
                    "circle-radius": ["get", "radius"],
                    "circle-color": ["get", "color"],
                    "circle-stroke-width": 2,
                    "circle-stroke-color": "#FFFFFF",
                  } as never
                }
              />
              <Layer
                id="corridors-selected"
                type="circle"
                filter={["==", ["get", "selected"], 1]}
                paint={
                  {
                    "circle-radius": ["+", ["get", "radius"], 4],
                    "circle-opacity": 0,
                    "circle-stroke-width": 3,
                    "circle-stroke-color": "#1D4ED8",
                  } as never
                }
              />
              <Layer
                id="corridors-rank"
                type="symbol"
                filter={["<=", ["get", "rank"], 5]}
                layout={
                  {
                    "symbol-sort-key": ["get", "sort_key"],
                    "text-field": ["to-string", ["get", "rank"]],
                    "text-size": 11,
                    "text-font": ["DIN Pro Bold", "Arial Unicode MS Bold"],
                    "text-allow-overlap": true,
                    "text-ignore-placement": true,
                  } as never
                }
                paint={{
                  "text-color": "#FFFFFF",
                }}
              />
              {/* Selected corridor name only */}
              <Layer
                id="corridors-name-selected"
                type="symbol"
                filter={["==", ["get", "selected"], 1]}
                layout={
                  {
                    "symbol-sort-key": ["get", "sort_key"],
                    "text-field": ["get", "corridor"],
                    "text-size": 12,
                    "text-font": [
                      "DIN Pro Medium",
                      "Arial Unicode MS Regular",
                    ],
                    "text-offset": [1.2, 0],
                    "text-anchor": "left",
                    "text-allow-overlap": true,
                  } as never
                }
                paint={{
                  "text-color": "#15171A",
                  "text-halo-color": "#FFFFFF",
                  "text-halo-width": 1.5,
                }}
              />
            </Source>
          </>
        )}

        {hover && (
          <Popup
            longitude={hover.longitude}
            latitude={hover.latitude}
            closeButton={false}
            closeOnClick={false}
            offset={12}
            anchor="bottom"
            className="corridor-hover-popup"
          >
            <div style={{ padding: "2px 0" }}>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "#15171A",
                  lineHeight: 1.3,
                }}
              >
                {hover.corridor}
              </div>
              <div
                className="font-mono"
                style={{ fontSize: 12, color: "#5A5F66", marginTop: 2 }}
              >
                #{hover.rank} · {Number(hover.score).toFixed(1)}
              </div>
            </div>
          </Popup>
        )}
      </Map>
    </div>
  );
}
