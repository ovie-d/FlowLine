"use client";

import "mapbox-gl/dist/mapbox-gl.css";
import { useEffect, useMemo, useRef, useState } from "react";
import Map, {
  Layer,
  Marker,
  NavigationControl,
  Popup,
  Source,
  type MapMouseEvent,
  type MapRef,
} from "react-map-gl/mapbox";
import type { ExpressionSpecification } from "mapbox-gl";
import { HAZARD_COLOR, HAZARD_SHORT, type HazardGroup } from "@/lib/hazards";
import type { MapViewProps } from "./mapTypes";

const DARK_STYLE = "mapbox://styles/mapbox/dark-v11";
const ALBERTA_VIEW = { longitude: -114.8, latitude: 54.6, zoom: 4.4 };
const LOAD_TIMEOUT_MS = 25000;

const HAZARD_MATCH = [
  "match",
  ["get", "hazard_group"],
  ...Object.entries(HAZARD_COLOR).flat(),
  HAZARD_COLOR.other_unknown,
] as unknown as ExpressionSpecification;

type Hover = { lon: number; lat: number; label: string; date: string; place: string };

export default function HazardMapbox({
  token,
  incidents,
  pipelines,
  bases,
  selected,
  similar,
  routes,
  activeRouteId,
  focus,
  pickMode,
  hiddenHazards,
  onPick,
  onFallback,
}: MapViewProps & { token: string; onFallback: (reason: string) => void }) {
  const mapRef = useRef<MapRef | null>(null);
  const [hover, setHover] = useState<Hover | null>(null);
  const loaded = useRef(false);

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
      onFallback("WebGL is unavailable in this browser (turn on hardware acceleration; see chrome://gpu).");
      return;
    }
    const t = window.setTimeout(() => {
      if (!loaded.current) onFallback(`The Mapbox basemap did not load within ${LOAD_TIMEOUT_MS / 1000} s (network or firewall?).`);
    }, LOAD_TIMEOUT_MS);
    return () => window.clearTimeout(t);
  }, [webgl, onFallback]);

  useEffect(() => {
    if (!focus) return;
    mapRef.current?.flyTo({
      center: [focus.longitude, focus.latitude],
      zoom: focus.zoom ?? 8,
      duration: 900,
      essential: true,
    });
  }, [focus]);

  const filteredIncidents = useMemo(() => {
    if (!incidents) return null;
    if (!hiddenHazards.size) return incidents;
    return {
      ...incidents,
      features: incidents.features.filter(
        (f) => !hiddenHazards.has(f.properties?.hazard_group as HazardGroup),
      ),
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
      if (b.route.geometry) {
        features.push({
          type: "Feature",
          geometry: b.route.geometry,
          properties: { id: b.base_id, active: b.base_id === activeRouteId ? 1 : 0, kind: "road" },
        });
      }
      if (b.route.last_mile) {
        features.push({
          type: "Feature",
          geometry: b.route.last_mile.geometry,
          properties: { id: b.base_id, active: b.base_id === activeRouteId ? 1 : 0, kind: "offroad" },
        });
      }
    }
    return { type: "FeatureCollection", features };
  }, [routes, activeRouteId]);

  function handleClick(e: MapMouseEvent) {
    onPick(e.lngLat.lat, e.lngLat.lng);
  }

  function handleMove(e: MapMouseEvent) {
    const f = e.features?.[0];
    if (!f || f.geometry.type !== "Point") {
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
      mapboxAccessToken={token}
      mapStyle={DARK_STYLE}
      initialViewState={ALBERTA_VIEW}
      minZoom={2.5}
      style={{ width: "100%", height: "100%" }}
      cursor={pickMode === "dispatch" ? "crosshair" : "pointer"}
      interactiveLayerIds={["incidents"]}
      onClick={handleClick}
      onMouseMove={handleMove}
      onMouseLeave={() => setHover(null)}
      onLoad={() => {
        loaded.current = true;
      }}
      onError={(e) => {
        if (loaded.current) return;
        const err = e.error as (Error & { status?: number }) | undefined;
        onFallback(
          err?.status
            ? `Mapbox refused the request (HTTP ${err.status}): check the token and its URL restrictions.`
            : `Mapbox failed to load: ${err?.message ?? "unknown error"}.`,
        );
      }}
      attributionControl
    >
      <NavigationControl position="top-left" showCompass={false} />
      {pipelines && (
        <Source id="pipelines" type="geojson" data={pipelines}>
          <Layer
            id="pipelines"
            type="line"
            paint={{ "line-color": "#2DD4BF", "line-opacity": 0.35, "line-width": 1.4 }}
          />
        </Source>
      )}
      {filteredIncidents && (
        <Source id="incidents" type="geojson" data={filteredIncidents}>
          <Layer
            id="incidents"
            type="circle"
            paint={{
              "circle-color": HAZARD_MATCH,
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 2.5, 8, 5, 12, 8],
              "circle-opacity": 0.85,
              "circle-stroke-color": "#0B1426",
              "circle-stroke-width": 1,
            }}
          />
        </Source>
      )}
      <Source id="similar" type="geojson" data={similarGeo}>
        <Layer
          id="similar"
          type="circle"
          paint={{
            "circle-radius": 11,
            "circle-color": "rgba(0,0,0,0)",
            "circle-stroke-color": "#E6EDF7",
            "circle-stroke-width": 2,
          }}
        />
      </Source>
      <Source id="routes" type="geojson" data={routeGeo}>
        <Layer
          id="routes-road"
          type="line"
          filter={["==", ["get", "kind"], "road"]}
          layout={{ "line-cap": "round", "line-join": "round" }}
          paint={{
            "line-color": ["case", ["==", ["get", "active"], 1], "#F5A524", "#8CA0C3"],
            "line-width": ["case", ["==", ["get", "active"], 1], 4, 2],
            "line-opacity": ["case", ["==", ["get", "active"], 1], 0.95, 0.5],
          }}
        />
        <Layer
          id="routes-offroad"
          type="line"
          filter={["==", ["get", "kind"], "offroad"]}
          paint={{ "line-color": "#F5A524", "line-width": 2, "line-dasharray": [1.5, 1.5] }}
        />
      </Source>
      {bases.map((b) => (
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
          <span className="relative flex h-5 w-5 items-center justify-center" aria-label="Selected point">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-50" />
            <span className="relative h-3 w-3 rounded-full border-2 border-bg bg-accent" />
          </span>
        </Marker>
      )}
      {hover && (
        <Popup
          longitude={hover.lon}
          latitude={hover.lat}
          closeButton={false}
          closeOnClick={false}
          offset={10}
          className="fl-popup"
        >
          <div className="text-[12px] leading-snug">
            <div className="font-semibold">{hover.label}</div>
            <div className="text-muted">
              {hover.place} · {hover.date}
            </div>
          </div>
        </Popup>
      )}
    </Map>
  );
}
