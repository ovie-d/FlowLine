import type {
  AgentResponse,
  CorridorDetail,
  Decision,
  Improvement,
  ImprovementFor,
  RankingRow,
  Triage,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} for ${path}`);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} for ${path}`);
  }
  return res.json() as Promise<T>;
}

export const getRanking = (high: number, top = 15) =>
  get<RankingRow[]>(`/ranking?high=${high}&top=${top}`);

export const getBaseline = () =>
  get<RankingRow[]>(`/ranking?high=1&top=112`);

export const getTriage = (high: number) =>
  get<Triage>(`/triage?high=${high}&top=15`);

export const getCorridor = (name: string, high: number) =>
  get<CorridorDetail>(
    `/corridor/${encodeURIComponent(name)}?high=${high}`,
  );

export const getImprovement = (high: number) =>
  get<ImprovementFor>(`/improvement?high=${high}`);

export const getImprovementRound = () => get<Improvement>(`/improvement`);

export const getDecisions = () => get<Decision[]>(`/decisions`);

export const askAgent = (
  session_id: string,
  question: string,
  high: number,
) => post<AgentResponse>(`/agent`, { session_id, question, high });

export const resetAgent = (session_id: string) =>
  post<{ ok: boolean }>(`/agent/reset`, { session_id });

export const csvUrl = (high: number) => `${BASE}/ranking.csv?high=${high}`;
