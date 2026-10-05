"use client";

/** Map display preferences (basemap, 3D, globe, layers): per browser, display only. */

import { useSyncExternalStore } from "react";
import type { Theme } from "./theme";

export type StyleKey = "auto" | "dark" | "light" | "streets" | "satellite";
export type LayerKey = "incidents" | "heatmap" | "pipelines" | "bases" | "crossings";

export type MapPrefs = {
  style: StyleKey;
  terrain: boolean;
  globe: boolean;
  layers: Record<LayerKey, boolean>;
};

export const STYLE_URL: Record<Exclude<StyleKey, "auto">, string> = {
  dark: "mapbox://styles/mapbox/dark-v11",
  light: "mapbox://styles/mapbox/light-v11",
  streets: "mapbox://styles/mapbox/streets-v12",
  satellite: "mapbox://styles/mapbox/satellite-streets-v12",
};

export const STYLE_LABEL: Record<StyleKey, string> = {
  auto: "Auto",
  dark: "Dark",
  light: "Light",
  streets: "Streets",
  satellite: "Satellite",
};

export const LAYER_LABEL: Record<LayerKey, string> = {
  incidents: "Past incidents",
  heatmap: "Incident heatmap",
  pipelines: "Pipeline systems",
  bases: "Crew bases (sample)",
  crossings: "River crossings",
};

/** "Auto" follows the app theme; an explicit pick sticks. */
export function resolveStyle(style: StyleKey, theme: Theme): Exclude<StyleKey, "auto"> {
  return style === "auto" ? theme : style;
}

/** Basemaps with a dark background (map overlays use light strokes on these). */
export function isDarkBasemap(style: Exclude<StyleKey, "auto">): boolean {
  return style === "dark" || style === "satellite";
}

const KEY = "flowline.map";
const DEFAULT: MapPrefs = {
  style: "auto",
  terrain: false,
  globe: true,
  layers: { incidents: true, heatmap: false, pipelines: true, bases: true, crossings: false },
};

let current: MapPrefs | null = null;
const listeners = new Set<() => void>();

function load(): MapPrefs {
  if (current) return current;
  current = DEFAULT;
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const saved = JSON.parse(raw) as Partial<MapPrefs>;
      current = {
        ...DEFAULT,
        ...saved,
        layers: { ...DEFAULT.layers, ...(saved.layers ?? {}) },
      };
    }
  } catch {
    /* blocked or corrupt storage: defaults */
  }
  return current;
}

export function setMapPrefs(update: (p: MapPrefs) => MapPrefs): void {
  current = update(load());
  try {
    localStorage.setItem(KEY, JSON.stringify(current));
  } catch {
    /* storage blocked: still applies for this page */
  }
  listeners.forEach((l) => l());
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useMapPrefs(): MapPrefs {
  return useSyncExternalStore(subscribe, load, () => DEFAULT);
}
