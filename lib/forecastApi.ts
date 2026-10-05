/** Typed client for the Hazard Forecast endpoints. All numbers come from the API. */

import type {
  AgentStatus,
  AgentUsage,
  BriefingResult,
  Corridor,
  CrewsPayload,
  CrossingsLayer,
  DispatchResult,
  Forecast,
  IncidentDetail,
  ModelInfo,
  Readiness,
  SimilarResult,
  WashoutInsight,
} from "./forecastTypes";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(`Backend unreachable at ${BASE}`, 0);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export type Where = { latitude: number; longitude: number } | { corridor: string };

function whereQuery(where: Where): string {
  return "corridor" in where
    ? `corridor=${encodeURIComponent(where.corridor)}`
    : `lat=${where.latitude}&lon=${where.longitude}`;
}

export const getForecast = (where: Where, date: string, operatorGroup?: string | null) =>
  request<Forecast>(
    "/forecast",
    json("POST", { ...where, date, ...(operatorGroup ? { operator_group: operatorGroup } : {}) }),
  );

export const getSimilar = (lat: number, lon: number, date: string, k = 5) =>
  request<SimilarResult>(`/similar?lat=${lat}&lon=${lon}&date=${date}&k=${k}`);

export const getReadiness = (where: Where, start: string, operatorGroup?: string | null) =>
  request<Readiness>(
    `/readiness?${whereQuery(where)}&start=${start}` +
      (operatorGroup ? `&operator_group=${encodeURIComponent(operatorGroup)}` : ""),
  );

export const getCrews = () => request<CrewsPayload>("/crews");

export const putCrewMap = (
  hazard_group: string,
  crews: { crew_type_id: string; equipment: string[]; priority?: number }[],
) => request<{ hazard_group: string }>("/crews/map", json("PUT", { hazard_group, crews }));

export const dispatchRoute = (latitude: number, longitude: number, hazard_group: string, k = 3) =>
  request<DispatchResult>("/dispatch/route", json("POST", { latitude, longitude, hazard_group, k }));

export const getModelInfo = () => request<ModelInfo>("/model/info");
export const getWashout = () => request<WashoutInsight>("/insights/washout");
export const getAgentStatus = () => request<AgentStatus>("/agent/status");
export const getAgentUsage = () => request<AgentUsage>("/agent/usage");
export const getCorridors = () => request<Corridor[]>("/corridors");
export const getIncidentPoints = () =>
  request<GeoJSON.FeatureCollection<GeoJSON.Point>>("/map/incidents");
export const getPipelines = () => request<GeoJSON.FeatureCollection>("/map/pipelines");
export const getCrossings = () => request<CrossingsLayer>("/map/crossings");
export const getIncidentDetail = (id: string) =>
  request<IncidentDetail>(`/map/incidents/${encodeURIComponent(id)}`);

export const getBriefing = (where: Where, start: string, operatorGroup?: string | null) =>
  request<BriefingResult>(
    "/briefing",
    json("POST", { ...where, start, ...(operatorGroup ? { operator_group: operatorGroup } : {}) }),
  );

/** Dev-console usage counter (Phase 9 budget guard). */
export async function logAgentUsage(label = "AI usage"): Promise<void> {
  try {
    const u = await getAgentUsage();
    console.info(
      `[Flowline] ${label}: ${u.calls} calls (${u.cached_calls} cached), ` +
        `${u.prompt_tokens + u.output_tokens} tokens, est. $${u.estimated_cost_usd.toFixed(4)} ` +
        `of $${u.budget_usd} budget`,
    );
  } catch {
    /* API down: nothing to report */
  }
}
