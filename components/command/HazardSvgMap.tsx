"use client";

import { useMemo, useRef, useState } from "react";
import { HAZARD_SHORT, hazardColor, type HazardGroup } from "@/lib/hazards";
import { IncidentCard } from "./IncidentCard";
import type { MapViewProps } from "./mapTypes";

/** Offline Alberta map: x = (lon + 120) * 10, y = (60 − lat) * 100 / 11 (viewBox 0–100). */
const AB_POLYGON =
  "0,0 100,0 100,100 59.4,100 53,90.91 46,83.64 37,77.27 27,70.91 17,64.55 8,59.09 0,55.45";

function project(lon: number, lat: number): [number, number] {
  return [(lon + 120) * 10, (60 - lat) * (100 / 11)];
}

function unproject(x: number, y: number): [number, number] {
  return [60 - (y * 11) / 100, x / 10 - 120];
}

function inView([x, y]: [number, number]): boolean {
  return x >= -2 && x <= 102 && y >= -2 && y <= 102;
}

function linePath(coords: GeoJSON.Position[]): string {
  return coords
    .map(([lon, lat], i) => {
      const [x, y] = project(lon, lat);
      return `${i ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function geometryPaths(g: GeoJSON.Geometry | null): string[] {
  if (!g) return [];
  if (g.type === "LineString") return [linePath(g.coordinates)];
  if (g.type === "MultiLineString") return g.coordinates.map(linePath);
  return [];
}

export function HazardSvgMap({
  incidents,
  pipelines,
  bases,
  selected,
  similar,
  routes,
  activeRouteId,
  pickMode,
  hiddenHazards,
  highlightHazard,
  crossings,
  prefs,
  vehicle,
  onPick,
  offlineReason,
  onRetry,
}: MapViewProps & { offlineReason?: string | null; onRetry?: () => void }) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [clicked, setClicked] = useState<string | null>(null);
  const layers = prefs.layers;

  const pipePaths = useMemo(
    () => (layers.pipelines ? (pipelines?.features ?? []).flatMap((f) => geometryPaths(f.geometry)) : []),
    [pipelines, layers.pipelines],
  );

  const crossingDots = useMemo(
    () =>
      layers.crossings
        ? (crossings?.features ?? []).map((f) => project(f.geometry.coordinates[0], f.geometry.coordinates[1])).filter(inView)
        : [],
    [crossings, layers.crossings],
  );

  const dots = useMemo(
    () =>
      (layers.incidents ? (incidents?.features ?? []) : [])
        .filter((f) => !hiddenHazards.has(f.properties?.hazard_group as HazardGroup))
        .map((f) => {
          const [lon, lat] = f.geometry.coordinates;
          return { xy: project(lon, lat), p: f.properties ?? {} };
        })
        .filter((d) => inView(d.xy)),
    [incidents, hiddenHazards, layers.incidents],
  );

  function handleClick(e: React.MouseEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    const ctm = svg?.getScreenCTM();
    if (!svg || !ctm) return;
    const pt = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse());
    const [lat, lon] = unproject(pt.x, pt.y);
    if (lat < 49 || lat > 60 || lon < -120 || lon > -110) return;
    setClicked(null);
    onPick(lat, lon);
  }

  return (
    <div className="relative h-full w-full">
      <svg
        ref={svgRef}
        viewBox="-2 -2 104 104"
        preserveAspectRatio="xMidYMid meet"
        className={`h-full w-full ${pickMode === "dispatch" ? "cursor-crosshair" : "cursor-pointer"}`}
        onClick={handleClick}
        role="img"
        aria-label="Alberta map (offline view). Click to forecast a location."
      >
        <polygon points={AB_POLYGON} fill="var(--panel)" stroke="var(--border)" strokeWidth={0.4} />
        {pipePaths.map((d, i) => (
          <path key={i} d={d} fill="none" stroke="var(--safe)" strokeOpacity={0.45} strokeWidth={0.35} />
        ))}
        {crossingDots.map(([x, y], i) => (
          <circle key={`x${i}`} cx={x} cy={y} r={0.3} fill="#0369A1" fillOpacity={0.8} />
        ))}
        {dots.map((d, i) => {
          const hl = highlightHazard ? d.p.hazard_group === highlightHazard : null;
          return (
            <circle
              key={i}
              cx={d.xy[0]}
              cy={d.xy[1]}
              r={hl ? 0.95 : 0.55}
              fill={hazardColor(String(d.p.hazard_group))}
              fillOpacity={hl === false ? 0.2 : 0.85}
              stroke={hl ? "var(--text)" : undefined}
              strokeWidth={hl ? 0.2 : undefined}
              className={pickMode === "dispatch" ? undefined : "cursor-pointer"}
              onClick={(e) => {
                if (pickMode === "dispatch") return;
                e.stopPropagation();
                setClicked(String(d.p.id));
              }}
            >
              <title>
                {`${HAZARD_SHORT[d.p.hazard_group as HazardGroup] ?? d.p.hazard_label} · ${d.p.place} · ${d.p.date} (click for details)`}
              </title>
            </circle>
          );
        })}
        {(routes ?? []).map((b) => {
          const active = b.base_id === activeRouteId;
          return (
            <g key={b.base_id}>
              {geometryPaths(b.route.geometry).map((d, i) => (
                <path key={i} d={d} fill="none" stroke={active ? "var(--highlight)" : "var(--muted)"}
                  strokeWidth={active ? 0.8 : 0.4} strokeOpacity={active ? 0.95 : 0.5}
                  strokeDasharray={b.route.provider === "straight_line" ? "1 1" : undefined} />
              ))}
              {b.route.last_mile &&
                geometryPaths(b.route.last_mile.geometry).map((d, i) => (
                  <path key={`lm${i}`} d={d} fill="none" stroke="var(--highlight)" strokeWidth={0.4}
                    strokeDasharray="0.8 0.8" />
                ))}
            </g>
          );
        })}
        {similar.map((s) => {
          const [x, y] = project(s.longitude, s.latitude);
          return inView([x, y]) ? (
            <circle key={s.incident_number} cx={x} cy={y} r={1.6} fill="none" stroke="var(--text)" strokeWidth={0.35} />
          ) : null;
        })}
        {(layers.bases ? bases : []).map((b) => {
          const [x, y] = project(b.longitude, b.latitude);
          return (
            <g key={b.id}>
              <rect x={x - 1} y={y - 1} width={2} height={2} rx={0.3} fill="var(--panel-2)"
                stroke="var(--text)" strokeWidth={0.35} />
              <circle cx={x} cy={y} r={0.4} fill="#2DD4BF" />
              <text x={x + 1.6} y={y + 0.8} fontSize={2.2} fill="var(--muted)">
                {b.name}
              </text>
              <title>{`${b.name} crew base (sample — to be validated)`}</title>
            </g>
          );
        })}
        {selected &&
          (() => {
            const [x, y] = project(selected.longitude, selected.latitude);
            const c = routes ? "var(--critical-strong)" : "var(--accent)";
            return (
              <g>
                <circle cx={x} cy={y} r={2.2} fill={c} fillOpacity={0.25} />
                <circle cx={x} cy={y} r={1} fill={c} stroke="var(--bg)" strokeWidth={0.3} />
              </g>
            );
          })()}
        {vehicle &&
          (() => {
            const [x, y] = project(vehicle.longitude, vehicle.latitude);
            return (
              <g aria-label="Simulated crew position">
                <circle cx={x} cy={y} r={1.3} fill="#0B1F3A" stroke="#fff" strokeWidth={0.35} />
                <circle cx={x} cy={y} r={0.55} fill="#FACC15" />
              </g>
            );
          })()}
      </svg>
      {clicked && (
        <div className="absolute left-2 top-12 z-10 rounded-md border border-border bg-panel p-2.5 shadow-lg">
          <button type="button" onClick={() => setClicked(null)} aria-label="Close incident details"
            className="float-right ml-2 text-muted hover:text-fg">
            ×
          </button>
          <IncidentCard id={clicked} />
        </div>
      )}
      <div role="status" className="absolute bottom-2 left-2 max-w-[70%] rounded bg-panel/90 px-2 py-1 text-[11px] text-muted">
        <span className="font-semibold text-fg">Offline map view (Alberta).</span>{" "}
        {offlineReason ?? "Mapbox basemap unavailable."}
        {onRetry && (
          <button type="button" onClick={onRetry} className="ml-2 rounded border border-border px-1.5 text-fg hover:border-accent">
            Retry Mapbox
          </button>
        )}
      </div>
    </div>
  );
}
