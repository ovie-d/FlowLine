"use client";

import type { GeoJSONSource } from "maplibre-gl";
import { maplibreLib as lib } from "@/components/map/maplibreSetup";
import { OPEN_DEM_SOURCE, OPEN_TEXT_FONT, openStyle } from "@/lib/openBasemaps";
import { HazardGLMap, type GLEngine } from "./HazardGLMap";
import type { MapViewProps } from "./mapTypes";


const engine: GLEngine = {
  style: (key) => openStyle(key) as GLEngineStyle,
  mapProps: {},
  snapshotProps: { canvasContextAttributes: { preserveDrawingBuffer: true } } as GLEngine["snapshotProps"],
  dem: OPEN_DEM_SOURCE,
  clusterZoom: (source, id) => (source as GeoJSONSource).getClusterExpansionZoom(id),
  textFont: OPEN_TEXT_FONT,
  timeoutMessage: "The open basemap tiles did not load within 25 s (network or firewall?).",
  errorMessage: (err) => `The open basemap failed to load: ${err?.message ?? "unknown error"}.`,
};
type GLEngineStyle = ReturnType<GLEngine["style"]>;

/** MapLibre GL on keyless open basemaps (OpenFreeMap, Esri imagery): used without a Mapbox token. */
export default function HazardMaplibre(props: MapViewProps & { onFallback: (reason: string, noWebGL?: boolean) => void }) {
  return <HazardGLMap lib={lib} engine={engine} {...props} />;
}
