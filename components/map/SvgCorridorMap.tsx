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

/** Offline SVG Alberta map (used when Mapbox is unavailable). */
export function SvgCorridorMap({
  ranking,
  selected,
  onSelect,
  offlineNote = false,
}: Props) {
  const clipId = useId().replace(/:/g, "");
  const [pipelinePaths, setPipelinePaths] = useState<string[]>([]);

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
  const dots = [...withCoords].reverse();

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-0 flex-1 items-center justify-center">
        <div
          className="relative rounded-lg bg-[#FAFAF8]"
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
            <polygon points={AB_POLYGON} fill="#EFEFEB" stroke="none" />
            <g clipPath={`url(#ab-clip-${clipId})`}>
              {pipelinePaths.map((d, i) => (
                <path
                  key={i}
                  d={d}
                  fill="none"
                  stroke="#B9A58F"
                  strokeWidth={1}
                  strokeOpacity={0.7}
                  vectorEffect="non-scaling-stroke"
                />
              ))}
            </g>
            <polygon
              points={AB_POLYGON}
              fill="none"
              stroke="#BDBDB6"
              strokeWidth="0.4"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
          <div className="absolute left-2.5 top-2.5 text-[11px] uppercase tracking-[0.1em] text-[#6B6F75]">
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
                aria-label={`${row.corridor}, rank ${row.rank}`}
                onClick={() => onSelect(row.corridor)}
                className="absolute p-0 font-mono text-[11px] font-semibold text-white"
                style={{
                  left: `${left.toFixed(2)}%`,
                  top: `${top.toFixed(2)}%`,
                  width: size,
                  height: size,
                  transform: "translate(-50%, -50%)",
                  borderRadius: "50%",
                  border: "2px solid #FFFFFF",
                  background: sevColor(row.n_high),
                  boxShadow: isSel
                    ? "0 0 0 3px #1D4ED8"
                    : "0 1px 3px rgba(0,0,0,0.25)",
                  cursor: "pointer",
                }}
              >
                {row.rank <= 5 ? row.rank : ""}
              </button>
            );
          })}
        </div>
      </div>
      {offlineNote && (
        <p className="mt-1 text-[11px] text-[#8A8E94]">Offline map view.</p>
      )}
    </div>
  );
}
