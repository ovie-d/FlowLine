import type { HazardGroup } from "@/lib/hazards";
import type { CrewBase, DispatchBase, LatLon, SimilarIncident } from "@/lib/forecastTypes";
import type { MapPrefs } from "@/lib/mapPrefs";
import type { Theme } from "@/lib/theme";

/** Fly to a point, or fit a bounding box ([[west, south], [east, north]]). */
export type MapFocus = LatLon & { zoom?: number; key: number; bounds?: [[number, number], [number, number]] };

/** What the page passes to the map (HazardMap adds the year filter, legend and controls). */
export type MapInputs = {
  incidents: GeoJSON.FeatureCollection<GeoJSON.Point> | null;
  pipelines: GeoJSON.FeatureCollection | null;
  bases: CrewBase[];
  selected: LatLon | null;
  similar: SimilarIncident[];
  routes: DispatchBase[] | null;
  activeRouteId: string | null;
  focus: MapFocus | null;
  pickMode: "forecast" | "dispatch";
  /** Hazard bar under the pointer: its past incidents are emphasised on the map. */
  highlightHazard?: HazardGroup | null;
  /** Simulated crew position (Dispatch page). */
  vehicle?: LatLon | null;
  onPick: (latitude: number, longitude: number) => void;
  /** Dispatch page: receives a function that returns the current map as a PNG data URL. */
  registerSnapshot?: (snap: (() => string | null) | null) => void;
};

/** What a renderer (Mapbox or offline SVG) receives. */
export type MapViewProps = MapInputs & {
  crossings: GeoJSON.FeatureCollection<GeoJSON.Point> | null;
  hiddenHazards: Set<HazardGroup>;
  prefs: MapPrefs;
  theme: Theme;
};
