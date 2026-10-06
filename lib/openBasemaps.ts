/**
 * Keyless basemaps for the MapLibre map (used when there is no Mapbox token).
 *   Dark / Light / Streets: OpenFreeMap vector styles (OpenStreetMap data; free, no key,
 *     no registration; https://openfreemap.org)
 *   Satellite: Esri World Imagery with Esri place labels (raster, no key; Esri's terms
 *     ask for attribution and limit heavy commercial use)
 *   3D terrain: AWS Terrain Tiles (Terrarium encoding, open data)
 * Check the providers' terms before a production deployment.
 */

import type { StyleKey } from "./mapPrefs";

type Basemap = Exclude<StyleKey, "auto">;

const OFM = "https://tiles.openfreemap.org/styles";
const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services";

/** Glyphs and font for cluster counts: OpenFreeMap serves Noto Sans for every style. */
export const OPEN_GLYPHS = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";
export const OPEN_TEXT_FONT = ["Noto Sans Bold"];

export const OPEN_DEM_SOURCE = {
  type: "raster-dem" as const,
  tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
  encoding: "terrarium" as const,
  tileSize: 256,
  maxzoom: 15,
  attribution: 'Terrain: <a href="https://registry.opendata.aws/terrain-tiles/">AWS Terrain Tiles</a>',
};

const SATELLITE = {
  version: 8 as const,
  glyphs: OPEN_GLYPHS,
  sources: {
    imagery: {
      type: "raster" as const,
      tiles: [`${ESRI}/World_Imagery/MapServer/tile/{z}/{y}/{x}`],
      tileSize: 256,
      maxzoom: 19,
      attribution: "Imagery © Esri, Maxar, Earthstar Geographics and the GIS User Community",
    },
    labels: {
      type: "raster" as const,
      tiles: [`${ESRI}/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}`],
      tileSize: 256,
      maxzoom: 19,
      attribution: "Labels © Esri",
    },
  },
  layers: [
    { id: "background", type: "background" as const, paint: { "background-color": "#0b1426" } },
    { id: "imagery", type: "raster" as const, source: "imagery" },
    { id: "labels", type: "raster" as const, source: "labels" },
  ],
};

/** MapLibre style (URL or object) for one basemap. */
export function openStyle(key: Basemap): string | typeof SATELLITE {
  switch (key) {
    case "dark":
      return `${OFM}/dark`;
    case "light":
      return `${OFM}/positron`;
    case "streets":
      return `${OFM}/liberty`;
    case "satellite":
      return SATELLITE;
  }
}
