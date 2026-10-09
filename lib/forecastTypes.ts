/** Response types for the Hazard Forecast API (mirror api/routes.py + core/*). */

import type { HazardGroup } from "./hazards";

export type LatLon = { latitude: number; longitude: number };

export type ForecastDriver = {
  feature: string;
  text: string;
  effect: "raises" | "lowers";
  weight: number;
};

export type ForecastHazard = {
  hazard_group: HazardGroup;
  label: string;
  probability: number;
  display: string;
  lower_certainty: boolean;
  alberta_share: number | null;
  vs_alberta: number | null;
  low_evidence_group: boolean;
  drivers: ForecastDriver[];
};

export type OperatorOption = { operator_group: string; commodity: string };

export type ForecastContext = {
  province: string | null;
  province_source_km: number | null;
  nearest_system: string | null;
  nearest_system_km: number | null;
  operator_group: string | null;
  commodity: string | null;
  operator_source: string;
  operator_options: OperatorOption[];
};

export type Forecast = {
  location: LatLon;
  date: string;
  corridor?: string;
  context: ForecastContext;
  hazards: ForecastHazard[];
  evidence: {
    radius_km: number;
    prior_incidents: number;
    prior_sites: number;
    prior_with_known_cause: number;
    same_site_incidents: number;
  };
  low_evidence: boolean;
  low_evidence_rule: string;
  weather_in_model: boolean;
  model: { trained_through?: string; trained_at?: string; rounds?: number };
  disclaimer: string;
};

export type SimilarIncident = {
  incident_number: string;
  date: string;
  place: string;
  province: string;
  latitude: number;
  longitude: number;
  distance_km: number;
  hazard_group: HazardGroup;
  hazard_label: string;
  is_model_target: boolean;
  similarity: number;
  weather_known: boolean;
  snippet: string;
};

export type SimilarResult = {
  reference_date: string;
  query_weather_known?: boolean;
  incidents: SimilarIncident[];
};

export type RouteResult = {
  provider: "osrm" | "mapbox" | "straight_line" | string;
  duration_min: number | null;
  distance_km: number;
  geometry: GeoJSON.LineString | null;
  last_mile: { label: string; distance_km: number; geometry: GeoJSON.LineString } | null;
  warning: string | null;
  fallbacks: string[];
};

export type CrewEntry = {
  crew_type_id: string;
  crew_name: string;
  equipment: string[];
  priority: number;
  is_sample: boolean;
  updated_at: string;
};

export type CrewBase = {
  id: string;
  name: string;
  province: string;
  latitude: number;
  longitude: number;
  crew_types: string[];
  is_sample: boolean;
};

export type CrewsPayload = {
  sample_label: string;
  has_sample_data: boolean;
  crew_types: { id: string; name: string; description: string; is_sample: boolean }[];
  hazard_map: {
    hazard_group: HazardGroup;
    hazard_label: string;
    low_evidence: boolean;
    crews: CrewEntry[];
  }[];
  bases: CrewBase[];
};

export type DispatchBase = {
  base_id: string;
  base_name: string;
  is_sample: boolean;
  latitude: number;
  longitude: number;
  matching_crews: { crew_type_id: string; crew_name: string }[];
  route: RouteResult;
};

export type DispatchResult = {
  incident: LatLon;
  hazard_group: HazardGroup;
  hazard_label: string;
  sample_label: string;
  bases: DispatchBase[];
  message: string | null;
};

export type WeatherSummary = {
  source: string;
  next_7_days: {
    date: string;
    t_min: number | null;
    t_max: number | null;
    precip_mm: number | null;
    snowfall_cm: number | null;
  }[];
  outlook: {
    min_temp: number | null;
    max_temp: number | null;
    precip_total_mm: number;
    snowfall_total_cm: number;
  };
  prior_30_days: {
    precip_mm: number | null;
    freeze_thaw_days: number | null;
    mean_temp_last_7_days: number | null;
  };
};

export type NearestBase = {
  base_id: string;
  base_name: string;
  is_sample: boolean;
  duration_min: number | null;
  distance_km: number;
  provider: string;
  warning: string | null;
};

export type Readiness = {
  location: LatLon;
  week: { start: string; end: string; forecast_date: string };
  forecast: Forecast;
  recommended: {
    hazard_group: HazardGroup;
    label: string;
    probability: number;
    display: string;
    low_evidence_group: boolean;
    crews: (CrewEntry & { nearest_base: NearestBase | null })[];
  }[];
  recommend_rule: string;
  sample_label: string;
  weather: WeatherSummary | null;
  weather_note: string | null;
  weather_in_model: boolean;
  similar: SimilarResult;
};

export type WashoutPeriod = {
  period: string;
  incidents: number;
  geotechnical: number;
  geotechnical_share: number | null;
  median_precip_30d_geotechnical_mm: number | null;
  n_geotechnical_with_precip: number;
  median_precip_30d_other_mm: number | null;
  n_other_with_precip: number;
};

export type WashoutInsight = {
  headline: string | null;
  before: WashoutPeriod;
  after: WashoutPeriod;
  share_ratio: number | null;
  note: string;
  is_forecast: false;
};

export type CiTriple = [number, number, number];

export type RegionSummary = {
  n_test: number;
  model: Record<"log_loss" | "brier" | "top1" | "top3", CiTriple>;
  best_baseline: { name: string } & Record<"log_loss" | "brier" | "top1" | "top3", CiTriple>;
  delta_log_loss_vs_best_baseline: CiTriple;
  beats_best_baseline: boolean;
};

export type ModelInfo = {
  generated_at: string;
  split: { train: string; test: string; training_scope: string };
  canada: RegionSummary;
  alberta: RegionSummary;
  rolling_origin: {
    year: number;
    n: number;
    model_log_loss: number;
    national_base_log_loss: number;
    delta_vs_national: CiTriple;
  }[];
  calibration_above_threshold: {
    threshold: number;
    n_forecasts_above: number;
    mean_predicted: number | null;
    observed_rate: number | null;
  };
  low_evidence_rule: string;
  deployed_model: { trained_through: string; n_train: number; rounds: number };
  plain_words: { canada: string; alberta: string; weather: string; calibration: string };
  disclaimer: string;
};

export type AgentStatus = {
  available: boolean;
  provider: string | null;
  model: string | null;
  fallback: string | null;
  reason: string | null;
  /** Spend counter (local installs only; hidden on the online demo). */
  usage?: AgentUsage;
  /** Online demo: this visitor's AI prompts left today. */
  quota?: DemoQuota | null;
  /** Local install using the online demo's AI (no local key). */
  via_online_demo?: boolean;
};

export type DemoQuota = {
  demo: true;
  limit: number;
  remaining: number;
  daily_budget_reached: boolean;
  note: string;
};

export type DemoStatus = DemoQuota | { demo: false };

export type AgentUsage = {
  calls: number;
  cached_calls: number;
  prompt_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  budget_usd: number;
  remaining_usd: number;
};

export type BriefingResult = {
  answer: string;
  error?: boolean;
  reason?: string;
  budget_exceeded?: boolean;
  numbers_verified?: boolean;
  unsupported_numbers?: string[];
  provider?: { provider: string; model: string };
  usage?: { model_calls: number; cached_calls: number; prompt_tokens: number; output_tokens: number };
  tool_calls?: { name: string; input?: Record<string, unknown> }[];
  quota?: DemoQuota;
  via_online_demo?: boolean;
};

export type Corridor = {
  name: string;
  n_incidents: number;
  latitude: number;
  longitude: number;
};

export type IncidentDetail = {
  incident_number: string;
  date: string;
  date_source: "occurred" | "discovered" | "reported";
  place: string;
  province: string;
  latitude: number;
  longitude: number;
  hazard_group: HazardGroup;
  hazard_label: string;
  operator: string;
  operator_group: string;
  commodity: string;
  status: string | null;
  incident_types: string[];
  what_happened: string[];
  what_detail: string[];
  why: string[];
  why_detail: string[];
  cause_determined: boolean;
  source: string;
};

export type CrossingsLayer = GeoJSON.FeatureCollection<GeoJSON.Point> & {
  available: boolean;
  note: string;
};
