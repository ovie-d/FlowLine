"use client";

import { useMemo, useRef } from "react";
import { HAZARD_SHORT, hazardColor, type HazardGroup } from "@/lib/hazards";
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
  onPick,
}: MapViewProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);

  const pipePaths = useMemo(
    () => (pipelines?.features ?? []).flatMap((f) => geometryPaths(f.geometry)),
    [pipelines],
  );

  const dots = useMemo(
    () =>
      (incidents?.features ?? [])
        .filter((f) => !hiddenHazards.has(f.properties?.hazard_group as HazardGroup))
        .map((f) => {
          const [lon, lat] = f.geometry.coordinates;
          return { xy: project(lon, lat), p: f.properties ?? {} };
        })
        .filter((d) => inView(d.xy)),
    [incidents, hiddenHazards],
  );

  function handleClick(e: React.MouseEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    const ctm = svg?.getScreenCTM();
    if (!svg || !ctm) return;
    const pt = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse());
    const [lat, lon] = unproject(pt.x, pt.y);
    if (lat < 49 || lat > 60 || lon < -120 || lon > -110) return;
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
          <path key={i} d={d} fill="none" stroke="#2DD4BF" strokeOpacity={0.35} strokeWidth={0.35} />
        ))}
        {dots.map((d, i) => (
          <circle key={i} cx={d.xy[0]} cy={d.xy[1]} r={0.55} fill={hazardColor(String(d.p.hazard_group))}
            fillOpacity={0.85}>
            <title>
              {`${HAZARD_SHORT[d.p.hazard_group as HazardGroup] ?? d.p.hazard_label} · ${d.p.place} · ${d.p.date}`}
            </title>
          </circle>
        ))}
        {(routes ?? []).map((b) => {
          const active = b.base_id === activeRouteId;
          return (
            <g key={b.base_id}>
              {geometryPaths(b.route.geometry).map((d, i) => (
                <path key={i} d={d} fill="none" stroke={active ? "#F5A524" : "#8CA0C3"}
                  strokeWidth={active ? 0.8 : 0.4} strokeOpacity={active ? 0.95 : 0.5}
                  strokeDasharray={b.route.provider === "straight_line" ? "1 1" : undefined} />
              ))}
              {b.route.last_mile &&
                geometryPaths(b.route.last_mile.geometry).map((d, i) => (
                  <path key={`lm${i}`} d={d} fill="none" stroke="#F5A524" strokeWidth={0.4}
                    strokeDasharray="0.8 0.8" />
                ))}
            </g>
          );
        })}
        {similar.map((s) => {
          const [x, y] = project(s.longitude, s.latitude);
          return inView([x, y]) ? (
            <circle key={s.incident_number} cx={x} cy={y} r={1.6} fill="none" stroke="#E6EDF7" strokeWidth={0.35} />
          ) : null;
        })}
        {bases.map((b) => {
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
            return (
              <g>
                <circle cx={x} cy={y} r={2.2} fill="#F5A524" fillOpacity={0.25} />
                <circle cx={x} cy={y} r={1} fill="#F5A524" stroke="var(--bg)" strokeWidth={0.3} />
              </g>
            );
          })()}
      </svg>
      <span className="pointer-events-none absolute bottom-2 left-2 rounded bg-panel/80 px-2 py-0.5 text-[11px] text-muted">
        Offline map view (Alberta) · set NEXT_PUBLIC_MAPBOX_TOKEN for the basemap
      </span>
    </div>
  );
}
