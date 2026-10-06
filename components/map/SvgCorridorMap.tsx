"use client";

import { useEffect, useId, useState } from "react";
import type { RankingRow } from "@/lib/types";
import { sevColor } from "@/lib/format";

const AB_POLYGON =
  "0.00,0.00 100.00,0.00 100.00,100.00 59.40,100.00 53.00,90.91 46.00,83.64 37.00,77.27 27.00,70.91 17.00,64.55 8.00,59.09 0.00,55.45";

function projectLonLat(lon: number, lat: number): [number, number] {
  const x = (lon + 120) * 10;
  const y = (60 - lat) * (100 / 11);
  return [x, y];
}

type GeoJsonGeometry =
  | { type: "LineString"; coordinates: number[][] }
  | { type: "MultiLineString"; coordinates: number[][][] };

type GeoJsonFeature = {
  geometry?: GeoJsonGeometry | null;
};

type GeoJsonFeatureCollection = {
  type: "FeatureCollection";
  features: GeoJsonFeature[];
};

function lineStringToPath(coords: number[][]): string | null {
  if (!coords.length) return null;
  const parts: string[] = [];
  for (let i = 0; i < coords.length; i++) {
    const [lon, lat] = coords[i];
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
    const [x, y] = projectLonLat(lon, lat);
    parts.push(
      `${parts.length === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`,
    );
  }
  return parts.length >= 2 ? parts.join(" ") : null;
}

function geometryToPaths(
  geometry: GeoJsonGeometry | null | undefined,
): string[] {
  if (!geometry) return [];
  if (geometry.type === "LineString") {
    const d = lineStringToPath(geometry.coordinates);
    return d ? [d] : [];
  }
  if (geometry.type === "MultiLineString") {
    const out: string[] = [];
    for (const line of geometry.coordinates) {
      const d = lineStringToPath(line);
      if (d) out.push(d);
    }
    return out;
  }
  return [];
}

function featureCollectionToPaths(fc: GeoJsonFeatureCollection): string[] {
  const paths: string[] = [];
  for (const feature of fc.features ?? []) {
    paths.push(...geometryToPaths(feature.geometry));
  }
  return paths;
}

type Props = {
  ranking: RankingRow[];
  selected: string | null;
  onSelect: (corridor: string) => void;
  offlineNote?: boolean;
};

type HoverTip = {
  corridor: string;
  rank: number;
  score: number;
  left: number;
  top: number;
};

/** Offline SVG Alberta map (used when Mapbox is unavailable). */
export function SvgCorridorMap({
  ranking,
  selected,
  onSelect,
  offlineNote = false,
}: Props) {
  const clipId = useId().replace(/:/g, "");
  const [pipelinePaths, setPipelinePaths] = useState<string[]>([]);
  const [hover, setHover] = useState<HoverTip | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/pipelines_ab.geojson")
      .then((res) => {
        if (!res.ok) throw new Error(String(res.status));
        return res.json() as Promise<GeoJsonFeatureCollection>;
      })
      .then((fc) => {
        if (cancelled) return;
        setPipelinePaths(featureCollectionToPaths(fc));
      })
      .catch(() => {
        /* show map without lines */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const maxScore = ranking[0]?.score || 1;
  const withCoords = ranking.filter(
    (r) =>
      r.lat != null &&
      r.lon != null &&
      Number.isFinite(r.lat) &&
      Number.isFinite(r.lon),
  );
  // Higher ranks drawn first so lower ranks (better priority) sit on top.
  const dots = [...withCoords].sort((a, b) => b.rank - a.rank);
  const selectedRow = withCoords.find((r) => r.corridor === selected);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-0 flex-1 items-center justify-center">
        <div
          className="relative rounded-lg bg-panel-2"
          style={{
            aspectRatio: "10 / 15",
            height: "100%",
            maxWidth: "100%",
            width: "auto",
          }}
        >
          <svg
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            className="absolute inset-0 h-full w-full"
            aria-hidden
          >
            <defs>
              <clipPath id={`ab-clip-${clipId}`}>
                <polygon points={AB_POLYGON} />
              </clipPath>
            </defs>
            <polygon points={AB_POLYGON} fill="var(--border)" stroke="none" />
            <g clipPath={`url(#ab-clip-${clipId})`}>
              {pipelinePaths.map((d, i) => (
                <path
                  key={i}
                  d={d}
                  fill="none"
                  stroke="#2DD4BF"
                  strokeWidth={1}
                  strokeOpacity={0.7}
                  vectorEffect="non-scaling-stroke"
                />
              ))}
            </g>
            <polygon
              points={AB_POLYGON}
              fill="none"
              stroke="var(--muted)"
              strokeWidth="0.6"
              strokeOpacity={0.9}
              strokeDasharray="3 2"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
          <div className="absolute left-2.5 top-2.5 text-[11px] uppercase tracking-[0.1em] text-muted">
            Alberta
          </div>
          {dots.map((row) => {
            const size = Math.round(14 + (26 * row.score) / maxScore);
            const left = (((row.lon as number) + 120) / 10) * 100;
            const top = ((60 - (row.lat as number)) / 11) * 100;
            const isSel = selected === row.corridor;
            return (
              <button
                key={row.corridor}
                type="button"
                aria-label={`${row.corridor}, rank ${row.rank}, score ${row.score.toFixed(1)}`}
                title={`${row.corridor} · #${row.rank} · ${row.score.toFixed(1)}`}
                onClick={() => onSelect(row.corridor)}
                onMouseEnter={() =>
                  setHover({
                    corridor: row.corridor,
                    rank: row.rank,
                    score: row.score,
                    left,
                    top,
                  })
                }
                onMouseLeave={() => setHover(null)}
                onFocus={() =>
                  setHover({
                    corridor: row.corridor,
                    rank: row.rank,
                    score: row.score,
                    left,
                    top,
                  })
                }
                onBlur={() => setHover(null)}
                className="absolute p-0 font-mono text-[11px] font-semibold text-bg"
                style={{
                  left: `${left.toFixed(2)}%`,
                  top: `${top.toFixed(2)}%`,
                  width: size,
                  height: size,
                  transform: "translate(-50%, -50%)",
                  borderRadius: "50%",
                  border: "2px solid var(--panel)",
                  background: sevColor(row.n_high),
                  boxShadow: isSel
                    ? "0 0 0 3px var(--accent)"
                    : "0 1px 3px rgba(0,0,0,0.25)",
                  cursor: "pointer",
                  zIndex: 100 - row.rank,
                }}
              >
                {row.rank <= 5 ? row.rank : ""}
              </button>
            );
          })}
          {selectedRow && (
            <div
              className="pointer-events-none absolute whitespace-nowrap text-[12px] font-medium text-fg"
              style={{
                left: `calc(${((((selectedRow.lon as number) + 120) / 10) * 100).toFixed(2)}% + 14px)`,
                top: `${(((60 - (selectedRow.lat as number)) / 11) * 100).toFixed(2)}%`,
                transform: "translateY(-50%)",
                textShadow:
                  "0 0 2px var(--panel), 0 0 2px var(--panel), 1px 0 0 var(--panel), -1px 0 0 var(--panel), 0 1px 0 var(--panel), 0 -1px 0 var(--panel)",
                zIndex: 200,
              }}
            >
              {selectedRow.corridor}
            </div>
          )}
          {hover && (
            <div
              className="pointer-events-none absolute rounded bg-panel px-2 py-1 shadow"
              style={{
                left: `${hover.left.toFixed(2)}%`,
                top: `${hover.top.toFixed(2)}%`,
                transform: "translate(-50%, calc(-100% - 12px))",
                zIndex: 300,
                border: "1px solid var(--border)",
              }}
            >
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--text)",
                  lineHeight: 1.3,
                }}
              >
                {hover.corridor}
              </div>
              <div
                className="font-mono"
                style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}
              >
                #{hover.rank} · {hover.score.toFixed(1)}
              </div>
            </div>
          )}
        </div>
      </div>
      {offlineNote && (
        <p className="mt-1 text-[11px] text-muted">Offline map view.</p>
      )}
    </div>
  );
}
