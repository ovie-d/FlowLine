import type { HazardGroup } from "@/lib/hazards";
import type { CrewBase, DispatchBase, LatLon, SimilarIncident } from "@/lib/forecastTypes";

export type MapFocus = LatLon & { zoom?: number; key: number };

export type MapViewProps = {
  incidents: GeoJSON.FeatureCollection<GeoJSON.Point> | null;
  pipelines: GeoJSON.FeatureCollection | null;
  bases: CrewBase[];
  selected: LatLon | null;
  similar: SimilarIncident[];
  routes: DispatchBase[] | null;
  activeRouteId: string | null;
  focus: MapFocus | null;
  pickMode: "forecast" | "dispatch";
  hiddenHazards: Set<HazardGroup>;
  onPick: (latitude: number, longitude: number) => void;
};
