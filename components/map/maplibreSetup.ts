"use client";

/**
 * MapLibre GL set-up shared by the keyless maps (client-only modules). MapLibre 6
 * loads its tile worker by URL; the bundler doesn't emit those files, so they are
 * served by app/maplibre/[file]/route.ts from the installed package.
 */
import "maplibre-gl/dist/maplibre-gl.css";
import { setWorkerUrl } from "maplibre-gl";
import * as maplibre from "react-map-gl/maplibre";
import type { GLLib } from "@/components/command/HazardGLMap";

setWorkerUrl(new URL("/maplibre/maplibre-gl-worker.mjs", window.location.origin).href);

/** react-map-gl's MapLibre components: same API as the Mapbox ones, other prop types. */
export const maplibreLib = maplibre as unknown as GLLib;
