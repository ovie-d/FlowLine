"use client";

import "mapbox-gl/dist/mapbox-gl.css";
import type { GeoJSONSource } from "mapbox-gl";
import { useMemo } from "react";
import * as lib from "react-map-gl/mapbox";
import { STYLE_URL } from "@/lib/mapPrefs";
import { HazardGLMap, type GLEngine } from "./HazardGLMap";
import type { MapViewProps } from "./mapTypes";

const engine = (token: string): GLEngine => ({
  style: (key) => STYLE_URL[key],
  mapProps: { mapboxAccessToken: token },
  snapshotProps: { preserveDrawingBuffer: true },
  dem: { type: "raster-dem", url: "mapbox://mapbox.mapbox-terrain-dem-v1", tileSize: 512, maxzoom: 14 },
  clusterZoom: (source, id) =>
    new Promise((resolve, reject) =>
      (source as GeoJSONSource).getClusterExpansionZoom(id, (err, zoom) =>
        err || zoom == null ? reject(err) : resolve(zoom),
      ),
    ),
  timeoutMessage: "The Mapbox basemap did not load within 25 s (network or firewall?).",
  errorMessage: (err) =>
    err?.status
      ? `Mapbox refused the request (HTTP ${err.status}): check the token and its URL restrictions.`
      : `Mapbox failed to load: ${err?.message ?? "unknown error"}.`,
});

/** Mapbox GL with the project's token (Mapbox styles, terrain and satellite). */
export default function HazardMapbox({
  token,
  ...props
}: MapViewProps & { token: string; onFallback: (reason: string, noWebGL?: boolean) => void }) {
  // One engine object per token, so effects that depend on it don't re-run every render.
  const e = useMemo(() => engine(token), [token]);
  return <HazardGLMap lib={lib} engine={e} {...props} />;
}
