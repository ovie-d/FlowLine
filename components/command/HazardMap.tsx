"use client";

import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useCallback, useMemo, useState } from "react";
import { getCrossings } from "@/lib/forecastApi";
import { HAZARD_ORDER, HAZARD_SHORT, hazardHex, type HazardGroup } from "@/lib/hazards";
import { isDarkBasemap, resolveStyle, useMapPrefs } from "@/lib/mapPrefs";
import { useTheme } from "@/lib/theme";
import { HazardSvgMap } from "./HazardSvgMap";
import { MapControls } from "./MapControls";
import type { MapInputs } from "./mapTypes";
import { YearSlider } from "./YearSlider";

const loading = () => <div className="h-full w-full animate-pulse bg-panel" aria-label="Loading map" />;
const HazardMapbox = dynamic(() => import("./HazardMapbox"), { ssr: false, loading });
const HazardMaplibre = dynamic(() => import("./HazardMaplibre"), { ssr: false, loading });

/**
 * mapbox: Mapbox GL with NEXT_PUBLIC_MAPBOX_TOKEN.
 * open: MapLibre GL on keyless open basemaps (no token, or Mapbox failed).
 * offline: SVG Alberta map (no WebGL, or the open basemap failed too).
 */
type Engine = "mapbox" | "open" | "offline";
type MapMode = { mode: Engine; reason: string | null; attempt: number };

function yearOf(f: GeoJSON.Feature): number {
  return Number(f.properties?.year ?? String(f.properties?.date ?? "").slice(0, 4));
}

/**
 * Interactive WebGL map (Mapbox with a token, open basemaps without), falling back to
 * the SVG Alberta map with the real reason. Owns the display-only filters: hazard
 * legend, year range, layers.
 */
export function HazardMap({ banner, ...props }: MapInputs & { banner?: React.ReactNode }) {
  const token = (process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "").trim();
  const theme = useTheme();
  const prefs = useMapPrefs();
  const first: Engine = token ? "mapbox" : "open";
  const [state, setState] = useState<MapMode>({ mode: first, reason: null, attempt: 0 });
  const [hidden, setHidden] = useState<Set<HazardGroup>>(new Set());
  const [years, setYears] = useState<[number, number] | null>(null);

  const crossingsQ = useQuery({
    queryKey: ["map-crossings"],
    queryFn: getCrossings,
    staleTime: Infinity,
    enabled: prefs.layers.crossings,
  });

  // Mapbox failing (bad token, blocked) drops to the open basemaps; no WebGL or the open
  // basemaps failing too drops to the SVG map. Each step says why.
  const onFallback = useCallback((reason: string, noWebGL?: boolean) => {
    setState((s) => {
      const mode: Engine = s.mode === "mapbox" && !noWebGL ? "open" : "offline";
      console.warn(`[Flowline] ${s.mode === "mapbox" ? "Mapbox" : "Open basemap"} unavailable, using the ${mode === "open" ? "open basemap" : "offline"} map: ${reason}`);
      return { ...s, mode, reason };
    });
  }, []);
  const retry = useCallback(() => setState((s) => ({ mode: first, reason: null, attempt: s.attempt + 1 })), [first]);

  const bounds = useMemo<[number, number] | null>(() => {
    const ys = (props.incidents?.features ?? []).map(yearOf).filter(Number.isFinite);
    return ys.length ? [Math.min(...ys), Math.max(...ys)] : null;
  }, [props.incidents]);
  const range = years ?? bounds;

  const incidents = useMemo(() => {
    if (!props.incidents || !range) return props.incidents;
    const [a, b] = range;
    return { ...props.incidents, features: props.incidents.features.filter((f) => { const y = yearOf(f); return y >= a && y <= b; }) };
  }, [props.incidents, range]);

  const shown = useMemo(
    () => (incidents?.features ?? []).filter((f) => !hidden.has(f.properties?.hazard_group as HazardGroup)).length,
    [incidents, hidden],
  );

  const toggle = (g: HazardGroup) =>
    setHidden((s) => {
      const next = new Set(s);
      if (next.has(g)) next.delete(g);
      else next.add(g);
      return next;
    });

  const offline = state.mode === "offline";
  // The Dispatch page passes no incidents: its map shows bases, routes and the pin.
  const incidentLayers = props.pickMode !== "dispatch";
  const crossings = crossingsQ.data ?? null;
  const crossingsNote = crossingsQ.error
    ? "Could not load river crossings."
    : crossings && !crossings.available
      ? `River crossings are not built yet. ${crossings.note}`
      : null;
  const darkBase = offline ? theme === "dark" : isDarkBasemap(resolveStyle(prefs.style, theme));

  const view = {
    ...props,
    incidents,
    crossings,
    hiddenHazards: hidden,
    prefs,
    theme,
  };

  return (
    <div className="relative h-full w-full overflow-hidden">
      {state.mode === "mapbox" ? (
        <HazardMapbox key={state.attempt} token={token} onFallback={onFallback} {...view} />
      ) : state.mode === "open" ? (
        <HazardMaplibre key={`open-${state.attempt}`} onFallback={onFallback} {...view} />
      ) : (
        <HazardSvgMap {...view} offlineReason={state.reason} onRetry={retry} />
      )}
      {state.mode === "open" && state.reason && (
        <div role="status" className="absolute bottom-2 left-2 max-w-[45%] rounded bg-panel/90 px-2 py-1 text-[11px] text-muted">
          <span className="font-semibold text-fg">Open basemap.</span> {state.reason}
          <button type="button" onClick={retry} className="ml-2 rounded border border-border px-1.5 text-fg hover:border-accent">
            Retry Mapbox
          </button>
        </div>
      )}
      <div className={`absolute top-2 ${offline ? "left-2" : "left-12"}`}>
        <MapControls prefs={prefs} offline={offline} crossingsNote={crossingsNote} incidentLayers={incidentLayers}
          openBasemap={state.mode === "open"} />
      </div>
      <MapLegend hidden={hidden} onToggle={toggle} darkBase={darkBase} prefs={prefs} incidentLayers={incidentLayers}
        routes={!!props.routes?.length} clusters={!offline} />
      {props.highlightHazard && (
        <div role="status" className="pointer-events-none absolute left-1/2 top-2 -translate-x-1/2 rounded-full border border-border bg-panel/95 px-3 py-1 text-[12px] text-fg shadow">
          <span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full align-middle" style={{ background: hazardHex(props.highlightHazard, darkBase ? "dark" : "light") }} />
          Showing past {HAZARD_SHORT[props.highlightHazard]} incidents
        </div>
      )}
      {banner}
      {incidentLayers && bounds && range && prefs.layers.incidents && (
        <div className={`absolute left-1/2 w-[min(560px,calc(100%-1rem))] -translate-x-1/2 ${offline || state.reason ? "bottom-12" : "bottom-9"}`}>
          <YearSlider min={bounds[0]} max={bounds[1]} value={range} onChange={setYears} shown={shown} />
        </div>
      )}
    </div>
  );
}

function MapLegend({
  hidden,
  onToggle,
  darkBase,
  prefs,
  incidentLayers,
  routes,
  clusters,
}: {
  hidden: Set<HazardGroup>;
  onToggle: (g: HazardGroup) => void;
  darkBase: boolean;
  prefs: ReturnType<typeof useMapPrefs>;
  incidentLayers: boolean;
  routes: boolean;
  clusters: boolean;
}) {
  const [open, setOpen] = useState(true);
  const tone = darkBase ? "dark" : "light";
  const ink = darkBase ? { route: "#F5A524", idle: "#8CA0C3" } : { route: "#CA8A04", idle: "#4A5B78" };
  return (
    <div className="absolute right-2 top-2 w-[210px] max-w-[45%] rounded-md border border-border bg-panel/95 p-2 text-[11px] shadow backdrop-blur">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 font-semibold text-muted hover:text-fg"
      >
        {incidentLayers ? "Past incidents by hazard" : "Map key"} <span aria-hidden>{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <ul className="mt-1 grid gap-0.5">
          {incidentLayers && HAZARD_ORDER.map((g) => (
            <li key={g}>
              <button
                type="button"
                aria-pressed={!hidden.has(g)}
                onClick={() => onToggle(g)}
                title={hidden.has(g) ? "Show on map" : "Hide on map"}
                className={`flex w-full items-center gap-1.5 rounded px-1 text-left hover:bg-panel-2 ${hidden.has(g) ? "opacity-40" : ""}`}
              >
                <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: hazardHex(g, tone) }} />
                <span className="text-fg">{HAZARD_SHORT[g]}</span>
              </button>
            </li>
          ))}
          {incidentLayers && (
            <li className="flex items-center gap-1.5 px-1 text-muted">
              <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: hazardHex("other_unknown", tone) }} />
              Other / unknown
            </li>
          )}
          {routes && (
            <>
              <li className="flex items-center gap-1.5 px-1 text-muted">
                <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full border-2 border-white bg-critical-strong" />
                Incident pin
              </li>
              <li className="flex items-center gap-1.5 px-1 text-muted">
                <span className="inline-block h-1 w-3 shrink-0 rounded" style={{ background: ink.route }} />
                Selected route
              </li>
              <li className="flex items-center gap-1.5 px-1 text-muted">
                <span className="inline-block h-0.5 w-3 shrink-0" style={{ background: ink.idle }} />
                Other ranked routes
              </li>
              <li className="flex items-center gap-1.5 px-1 text-muted">
                <span className="inline-block w-3 shrink-0 border-t-2 border-dashed" style={{ borderColor: ink.route }} />
                Off-road last mile
              </li>
            </>
          )}
          {clusters && incidentLayers && prefs.layers.incidents && (
            <li className="flex items-center gap-1.5 px-1 text-muted">
              <span
                className="inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full text-[8px] font-bold text-white"
                style={{ background: darkBase ? "#24365C" : "#1E3A8A" }}
              >
                n
              </span>
              Cluster of n incidents
            </li>
          )}
          {prefs.layers.pipelines && (
            <li className="flex items-center gap-1.5 px-1 text-muted">
              <span className="inline-block h-0.5 w-3 shrink-0" style={{ background: darkBase ? "#2DD4BF" : "#0F766E" }} />
              CER pipeline systems
            </li>
          )}
          {prefs.layers.crossings && (
            <li className="flex items-center gap-1.5 px-1 text-muted">
              <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: darkBase ? "#7DD3FC" : "#0369A1" }} />
              River / stream crossing
            </li>
          )}
          {prefs.layers.bases && (
            <li className="flex items-center gap-1.5 px-1 text-muted">
              <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm border-2 border-fg" />
              Crew base (sample)
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
