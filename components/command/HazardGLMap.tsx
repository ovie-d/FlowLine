"use client";

/**
 * The interactive hazard map, shared by both WebGL engines: Mapbox GL (with a token)
 * and MapLibre GL on keyless open basemaps (without one). react-map-gl gives both the
 * same component API; the engine-specific parts (style, terrain source, cluster API,
 * snapshot option, error wording) come in through `engine`.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import type * as MapboxLib from "react-map-gl/mapbox";
import type { MapMouseEvent, MapProps, MapRef } from "react-map-gl/mapbox";
import type { ExpressionSpecification } from "mapbox-gl";
import { HAZARD_COLOR, HAZARD_SHORT, hazardHex, type HazardGroup } from "@/lib/hazards";
import { isDarkBasemap, resolveStyle, type StyleKey } from "@/lib/mapPrefs";
import { IncidentCard } from "./IncidentCard";
import type { MapViewProps } from "./mapTypes";

/** react-map-gl components (the Mapbox and MapLibre entry points share this shape). */
export type GLLib = Pick<
  typeof MapboxLib,
  "Map" | "Layer" | "Source" | "Marker" | "Popup" | "NavigationControl" | "ScaleControl"
>;

export type GLEngine = {
  /** Basemap style (URL or style object) for a resolved basemap key. */
  style: (key: Exclude<StyleKey, "auto">) => MapProps["mapStyle"];
  /** Extra Map props (e.g. the Mapbox token). */
  mapProps: Partial<MapProps>;
  /** Map props that keep the canvas readable for the printable snapshot. */
  snapshotProps: Partial<MapProps>;
  /** raster-dem source for 3D terrain. */
  dem: Record<string, unknown>;
  /** Zoom at which a cluster breaks apart (callback API in Mapbox, promise in MapLibre). */
  clusterZoom: (source: unknown, clusterId: number) => Promise<number>;
  /** Font for cluster counts, when the style's glyphs need a specific one. */
  textFont?: string[];
  timeoutMessage: string;
  errorMessage: (err: (Error & { status?: number }) | undefined) => string;
};

const ALBERTA_VIEW = { longitude: -114.8, latitude: 54.6, zoom: 4.4 };
const LOAD_TIMEOUT_MS = 25000;
const FLY_MS = 1800;
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

function hazardMatch(tone: "dark" | "light"): ExpressionSpecification {
  return [
    "match",
    ["get", "hazard_group"],
    ...Object.keys(HAZARD_COLOR).flatMap((g) => [g, hazardHex(g, tone)]),
    hazardHex("other_unknown", tone),
  ] as unknown as ExpressionSpecification;
}

/** Overlay colours per basemap brightness (literals: Mapbox paint cannot read CSS vars). */
function overlayInk(dark: boolean) {
  return dark
    ? { halo: "#0B1426", ring: "#E6EDF7", pipe: "#2DD4BF", water: "#7DD3FC", route: "#F5A524", routeIdle: "#8CA0C3", cluster: "#24365C", clusterText: "#E6EDF7" }
    : { halo: "#FFFFFF", ring: "#0B1F3A", pipe: "#0F766E", water: "#0369A1", route: "#CA8A04", routeIdle: "#4A5B78", cluster: "#1E3A8A", clusterText: "#FFFFFF" };
}

const vis = (on: boolean) => (on ? "visible" : "none") as "visible" | "none";

type Hover = { lon: number; lat: number; label: string; date: string; place: string };
type Clicked = { lon: number; lat: number; id: string; anchor: "top" | "bottom" };

export function HazardGLMap({
  lib,
  engine,
  incidents,
  pipelines,
  crossings,
  bases,
  selected,
  similar,
  routes,
  activeRouteId,
  focus,
  pickMode,
  hiddenHazards,
  highlightHazard,
  vehicle,
  prefs,
  theme,
  onPick,
  registerSnapshot,
  onFallback,
}: MapViewProps & { lib: GLLib; engine: GLEngine; onFallback: (reason: string, noWebGL?: boolean) => void }) {
  const { Map, Layer, Marker, NavigationControl, Popup, ScaleControl, Source } = lib;
  const mapRef = useRef<MapRef | null>(null);
  const [hover, setHover] = useState<Hover | null>(null);
  const [clicked, setClicked] = useState<Clicked | null>(null);
  const loaded = useRef(false);

  const styleKey = resolveStyle(prefs.style, theme);
  const darkBase = isDarkBasemap(styleKey);
  const ink = overlayInk(darkBase);
  const colors = hazardMatch(darkBase ? "dark" : "light");
  const layers = prefs.layers;

  // Client-only component (dynamic, ssr: false): window and document exist here.
  const [webgl] = useState(() => {
    try {
      const c = document.createElement("canvas");
      return !!(c.getContext("webgl2") || c.getContext("webgl"));
    } catch {
      return false;
    }
  });

  // Fall back only on real failures, and say which one.
  useEffect(() => {
    if (!webgl) {
      onFallback("WebGL is unavailable in this browser (turn on hardware acceleration; see chrome://gpu).", true);
      return;
    }
    const t = window.setTimeout(() => {
      if (!loaded.current) onFallback(engine.timeoutMessage);
    }, LOAD_TIMEOUT_MS);
    return () => window.clearTimeout(t);
  }, [webgl, onFallback, engine]);

  const [ready, setReady] = useState(false);
  useEffect(() => {
    const map = mapRef.current;
    if (!focus || !map || !ready) return;
    if (focus.bounds) {
      map.fitBounds(focus.bounds, {
        padding: { top: 70, bottom: 130, left: 70, right: 250 },
        maxZoom: 10,
        duration: FLY_MS,
        essential: true,
      });
      return;
    }
    map.flyTo({
      center: [focus.longitude, focus.latitude],
      zoom: focus.zoom ?? 8,
      duration: FLY_MS,
      curve: 1.5,
      essential: true,
    });
  }, [focus, ready]);

  // 3D terrain (the engine's DEM), re-applied after every basemap change; the camera tilts
  // when it is on and levels again when it is off.
  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map || !ready) return;
    const apply = () => {
      if (prefs.terrain) {
        if (!map.getSource("terrain-dem")) {
          map.addSource("terrain-dem", engine.dem as Parameters<typeof map.addSource>[1]);
        }
        map.setTerrain({ source: "terrain-dem", exaggeration: 1.4 });
      } else {
        map.setTerrain(null);
      }
    };
    apply();
    map.on("style.load", apply);
    return () => {
      map.off("style.load", apply);
    };
  }, [prefs.terrain, ready, engine]);
  useEffect(() => {
    const map = mapRef.current;
    const pitch = prefs.terrain ? 55 : 0;
    // Only when it changes: an easeTo would cancel a fly/fit that is in progress.
    if (ready && map && Math.abs(map.getPitch() - pitch) > 1) map.easeTo({ pitch, duration: 900 });
  }, [prefs.terrain, ready]);

  useEffect(() => {
    if (!registerSnapshot) return;
    registerSnapshot(() => {
      try {
        return mapRef.current?.getCanvas().toDataURL("image/png") ?? null;
      } catch {
        return null;
      }
    });
    return () => registerSnapshot(null);
  }, [registerSnapshot]);

  const visibleIncidents = useMemo(() => {
    if (!incidents) return EMPTY;
    if (!hiddenHazards.size) return incidents;
    return {
      ...incidents,
      features: incidents.features.filter((f) => !hiddenHazards.has(f.properties?.hazard_group as HazardGroup)),
    };
  }, [incidents, hiddenHazards]);

  const similarGeo = useMemo<GeoJSON.FeatureCollection>(
    () => ({
      type: "FeatureCollection",
      features: similar.map((s) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [s.longitude, s.latitude] },
        properties: { id: s.incident_number },
      })),
    }),
    [similar],
  );

  const routeGeo = useMemo<GeoJSON.FeatureCollection>(() => {
    const features: GeoJSON.Feature[] = [];
    for (const b of routes ?? []) {
      const active = b.base_id === activeRouteId ? 1 : 0;
      if (b.route.geometry) {
        features.push({ type: "Feature", geometry: b.route.geometry, properties: { id: b.base_id, active, kind: "road" } });
      }
      if (b.route.last_mile) {
        features.push({ type: "Feature", geometry: b.route.last_mile.geometry, properties: { id: b.base_id, active, kind: "offroad" } });
      }
    }
    // Draw the selected route last so it sits on top.
    features.sort((a, b) => Number(a.properties?.active) - Number(b.properties?.active));
    return { type: "FeatureCollection", features };
  }, [routes, activeRouteId]);

  const interactive = useMemo(() => {
    if (pickMode === "dispatch" || !layers.incidents) return [];
    return ["incidents", "clusters"];
  }, [pickMode, layers.incidents]);

  function handleClick(e: MapMouseEvent) {
    const f = e.features?.[0];
    if (f && f.layer?.id === "clusters") {
      const clusterId = f.properties?.cluster_id as number;
      const src = mapRef.current?.getSource("incident-clusters");
      const [lon, lat] = (f.geometry as GeoJSON.Point).coordinates;
      if (src) {
        engine
          .clusterZoom(src, clusterId)
          .then((zoom) => mapRef.current?.easeTo({ center: [lon, lat], zoom: zoom + 0.3, duration: 700 }))
          .catch(() => undefined);
      }
      return;
    }
    if (f && f.layer?.id === "incidents" && f.geometry.type === "Point") {
      const [lon, lat] = f.geometry.coordinates as [number, number];
      setHover(null);
      // Open towards the roomier side: the card is taller than the hover label.
      const h = mapRef.current?.getContainer().clientHeight ?? 0;
      setClicked({ lon, lat, id: String(f.properties?.id), anchor: e.point.y < h / 2 ? "top" : "bottom" });
      return;
    }
    setClicked(null);
    onPick(e.lngLat.lat, e.lngLat.lng);
  }

  function handleMove(e: MapMouseEvent) {
    const f = e.features?.[0];
    if (!f || f.layer?.id !== "incidents" || f.geometry.type !== "Point" || clicked) {
      setHover(null);
      return;
    }
    const [lon, lat] = f.geometry.coordinates as [number, number];
    const p = f.properties ?? {};
    setHover({
      lon,
      lat,
      label: HAZARD_SHORT[p.hazard_group as HazardGroup] ?? String(p.hazard_label),
      date: String(p.date),
      place: String(p.place),
    });
  }

  if (!webgl) return null;

  return (
    <Map
      ref={mapRef}
      {...engine.mapProps}
      {...(registerSnapshot ? engine.snapshotProps : {})}
      mapStyle={engine.style(styleKey)}
      projection={prefs.globe ? "globe" : "mercator"}
      initialViewState={ALBERTA_VIEW}
      minZoom={1.5}
      maxPitch={70}
      style={{ width: "100%", height: "100%" }}
      cursor={pickMode === "dispatch" ? "crosshair" : "pointer"}
      interactiveLayerIds={interactive}
      onClick={handleClick}
      onMouseMove={handleMove}
      onMouseLeave={() => setHover(null)}
      onLoad={() => {
        loaded.current = true;
        setReady(true);
      }}
      onError={(e) => {
        if (loaded.current) return;
        onFallback(engine.errorMessage(e.error as (Error & { status?: number }) | undefined));
      }}
      attributionControl
    >
      <NavigationControl position="top-left" visualizePitch />
      <ScaleControl position="bottom-right" unit="metric" />
      {/* Every layer is always mounted and toggled by visibility, so the draw order
          (heatmap < pipelines < crossings < incidents < highlight) never changes. */}
      <Source id="incident-all" type="geojson" data={visibleIncidents}>
        <Layer
          id="heatmap"
          type="heatmap"
          maxzoom={11}
          layout={{ visibility: vis(layers.heatmap) }}
          paint={{
            "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 3, 8, 8, 22, 11, 30],
            "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 3, 0.6, 10, 1.6],
            "heatmap-opacity": 0.75,
            "heatmap-color": [
              "interpolate",
              ["linear"],
              ["heatmap-density"],
              0, "rgba(0,0,0,0)",
              0.2, darkBase ? "#1E3A8A" : "#BFDBFE",
              0.45, darkBase ? "#3987E5" : "#60A5FA",
              0.7, "#F5A524",
              1, "#DC2626",
            ],
          }}
        />
      </Source>
      <Source id="pipelines" type="geojson" data={pipelines ?? EMPTY}>
        <Layer
          id="pipelines"
          type="line"
          layout={{ visibility: vis(layers.pipelines) }}
          paint={{ "line-color": ink.pipe, "line-opacity": darkBase ? 0.4 : 0.6, "line-width": 1.4 }}
        />
      </Source>
      <Source id="crossings" type="geojson" data={crossings ?? EMPTY}>
        <Layer
          id="crossings"
          type="circle"
          minzoom={5}
          layout={{ visibility: vis(layers.crossings) }}
          paint={{
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 1.5, 9, 3.5, 12, 5],
            "circle-color": ink.water,
            "circle-opacity": 0.85,
            "circle-stroke-color": ink.halo,
            "circle-stroke-width": 0.5,
          }}
        />
      </Source>
      <Source id="incident-clusters" type="geojson" data={visibleIncidents} cluster clusterMaxZoom={6} clusterRadius={36}>
        <Layer
          id="clusters"
          type="circle"
          filter={["has", "point_count"]}
          layout={{ visibility: vis(layers.incidents) }}
          paint={{
            "circle-color": ink.cluster,
            "circle-opacity": highlightHazard ? 0.35 : 0.9,
            "circle-stroke-color": ink.ring,
            "circle-stroke-width": 1,
            "circle-stroke-opacity": 0.6,
            "circle-radius": ["step", ["get", "point_count"], 11, 25, 15, 100, 20, 300, 26],
          }}
        />
        <Layer
          id="cluster-count"
          type="symbol"
          filter={["has", "point_count"]}
          layout={{
            visibility: vis(layers.incidents),
            "text-field": ["get", "point_count_abbreviated"],
            ...(engine.textFont ? { "text-font": engine.textFont } : {}),
            "text-size": 11,
            "text-allow-overlap": true,
          }}
          paint={{ "text-color": ink.clusterText, "text-opacity": highlightHazard ? 0.4 : 1 }}
        />
        <Layer
          id="incidents"
          type="circle"
          filter={["!", ["has", "point_count"]]}
          layout={{ visibility: vis(layers.incidents) }}
          paint={{
            "circle-color": colors,
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 2.5, 8, 5, 12, 8],
            "circle-opacity": highlightHazard ? 0.25 : 0.85,
            "circle-stroke-color": ink.halo,
            "circle-stroke-width": 1,
          }}
        />
      </Source>
      {/* Hovered forecast bar: that hazard's past incidents, unclustered, on top. */}
      <Layer
        id="incidents-hl"
        type="circle"
        source="incident-all"
        filter={["==", ["get", "hazard_group"], highlightHazard ?? "__none__"]}
        layout={{ visibility: vis(!!highlightHazard && layers.incidents) }}
        paint={{
          "circle-color": hazardHex(highlightHazard ?? "other_unknown", darkBase ? "dark" : "light"),
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 4, 8, 7, 12, 10],
          "circle-stroke-color": ink.ring,
          "circle-stroke-width": 1.5,
        }}
      />
      <Source id="similar" type="geojson" data={similarGeo}>
        <Layer
          id="similar"
          type="circle"
          paint={{ "circle-radius": 11, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": ink.ring, "circle-stroke-width": 2 }}
        />
      </Source>
      <Source id="routes" type="geojson" data={routeGeo}>
        <Layer
          id="routes-casing"
          type="line"
          filter={["all", ["==", ["get", "kind"], "road"], ["==", ["get", "active"], 1]]}
          layout={{ "line-cap": "round", "line-join": "round" }}
          paint={{ "line-color": darkBase ? "#0B1426" : "#0B1F3A", "line-width": 7, "line-opacity": 0.8 }}
        />
        <Layer
          id="routes-road"
          type="line"
          filter={["==", ["get", "kind"], "road"]}
          layout={{ "line-cap": "round", "line-join": "round" }}
          paint={{
            "line-color": ["case", ["==", ["get", "active"], 1], ink.route, ink.routeIdle],
            "line-width": ["case", ["==", ["get", "active"], 1], 4, 2.5],
            "line-opacity": ["case", ["==", ["get", "active"], 1], 1, 0.7],
          }}
        />
        <Layer
          id="routes-offroad"
          type="line"
          filter={["==", ["get", "kind"], "offroad"]}
          paint={{
            "line-color": ["case", ["==", ["get", "active"], 1], ink.route, ink.routeIdle],
            "line-width": 2.5,
            "line-dasharray": [1.5, 1.5],
          }}
        />
      </Source>
      {layers.bases &&
        bases.map((b) => (
          <Marker key={b.id} longitude={b.longitude} latitude={b.latitude} anchor="center">
            <span
              title={`${b.name} crew base (sample — to be validated)`}
              className="flex h-4 w-4 items-center justify-center rounded-sm border-2 border-fg bg-panel-2"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-safe" />
            </span>
          </Marker>
        ))}
      {selected && (
        <Marker longitude={selected.longitude} latitude={selected.latitude} anchor="center">
          <span
            className="relative flex h-5 w-5 items-center justify-center"
            aria-label={pickMode === "dispatch" || routes ? "Incident location" : "Selected point"}
          >
            <span
              className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-50 motion-reduce:animate-none ${routes ? "bg-critical-strong" : "bg-accent"}`}
            />
            <span className={`relative h-3 w-3 rounded-full border-2 border-white ${routes ? "bg-critical-strong" : "bg-accent"}`} />
          </span>
        </Marker>
      )}
      {vehicle && (
        <Marker longitude={vehicle.longitude} latitude={vehicle.latitude} anchor="center">
          <span
            aria-label="Simulated crew position"
            className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-white bg-[#0B1F3A] text-[12px] shadow-lg"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="#FACC15" aria-hidden>
              <path d="M3 6h11v9H3zM14 9h4l3 3v3h-7zM6.5 18.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zm11 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z" />
            </svg>
          </span>
        </Marker>
      )}
      {hover && !clicked && (
        <Popup longitude={hover.lon} latitude={hover.lat} closeButton={false} closeOnClick={false} offset={10} className="fl-popup">
          <div className="text-[12px] leading-snug">
            <div className="font-semibold">{hover.label}</div>
            <div className="text-muted">
              {hover.place} · {hover.date}
            </div>
            <div className="text-[11px] text-muted">Click for details</div>
          </div>
        </Popup>
      )}
      {clicked && (
        <Popup
          longitude={clicked.lon}
          latitude={clicked.lat}
          closeOnClick={false}
          onClose={() => setClicked(null)}
          anchor={clicked.anchor}
          offset={10}
          maxWidth="300px"
          className="fl-popup fl-popup-click"
        >
          <IncidentCard id={clicked.id} />
        </Popup>
      )}
    </Map>
  );
}
