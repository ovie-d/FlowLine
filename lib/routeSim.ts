/** Position along a route polyline by fraction of its length (simulation display only). */

import type { LatLon } from "./forecastTypes";

const R_KM = 6371;

function haversineKm(a: GeoJSON.Position, b: GeoJSON.Position): number {
  const rad = Math.PI / 180;
  const dLat = (b[1] - a[1]) * rad;
  const dLon = (b[0] - a[0]) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * rad) * Math.cos(b[1] * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R_KM * Math.asin(Math.sqrt(h));
}

export type Polyline = { coords: GeoJSON.Position[]; cumulative: number[]; total: number };

export function polyline(coords: GeoJSON.Position[]): Polyline {
  const cumulative = [0];
  for (let i = 1; i < coords.length; i++) cumulative.push(cumulative[i - 1] + haversineKm(coords[i - 1], coords[i]));
  return { coords, cumulative, total: cumulative[cumulative.length - 1] ?? 0 };
}

/** Point at fraction t (0..1) of the line's length. */
export function pointAt(line: Polyline, t: number): LatLon | null {
  const { coords, cumulative, total } = line;
  if (!coords.length) return null;
  const target = Math.min(1, Math.max(0, t)) * total;
  let i = 1;
  while (i < coords.length - 1 && cumulative[i] < target) i++;
  const seg = cumulative[i] - cumulative[i - 1] || 1;
  const f = Math.min(1, Math.max(0, (target - cumulative[i - 1]) / seg));
  const a = coords[i - 1];
  const b = coords[i] ?? a;
  return { longitude: a[0] + (b[0] - a[0]) * f, latitude: a[1] + (b[1] - a[1]) * f };
}

export function formatMinutes(m: number | null | undefined): string {
  if (m == null) return "no drive time";
  if (m < 60) return `${Math.round(m)} min`;
  const h = Math.floor(m / 60);
  const r = Math.round(m % 60);
  return r ? `${h} h ${r} min` : `${h} h`;
}

export function clock(d: Date): string {
  return d.toLocaleTimeString("en-CA", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "America/Edmonton" });
}
