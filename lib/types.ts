export type Confidence = "ok" | "low";

export type RankingRow = {
  rank: number;
  corridor: string;
  score: number;
  likelihood?: number;
  consequence?: number;
  n: number;
  n_high: number;
  n_medium?: number;
  n_low?: number;
  confidence: Confidence;
  drivers?: string[];
  operator?: string;
  lat: number | null;
  lon: number | null;
  last_incident?: string | null;
};

export type TriageAction = "Escalate" | "Inspect" | "Defer";

export type TriageDraft = {
  rank: number;
  corridor: string;
  action: TriageAction;
  priority: string | null;
  rule?: string;
  reason: string;
  n: number;
  n_high: number;
  confidence: Confidence;
};

export type Triage = {
  counts: Record<string, number>;
  drafts: TriageDraft[];
  policy?: string;
};

export type OperatorCount = {
  company: string;
  n: number;
};

export type CorridorDetail = {
  rank: number;
  corridor: string;
  score: number;
  likelihood: number;
  consequence: number;
  n: number;
  n_high: number;
  n_medium: number;
  n_low: number;
  confidence: Confidence;
  confidence_label?: string | null;
  operators: OperatorCount[];
  score_explanation: string;
  drivers: string[];
  last_incident: string | null;
  lat?: number | null;
  lon?: number | null;
};

export type ImprovementStage = {
  name: string;
  serious?: number;
  [key: string]: unknown;
};

export type Improvement = {
  stages: ImprovementStage[];
  ours_heavy?: ImprovementStage;
};

export type AgentToolCall = {
  name: string;
  input?: Record<string, unknown>;
};

export type AgentResponse = {
  answer: string;
  tool_calls: AgentToolCall[];
  error?: boolean;
};

export type Decision = {
  id?: string;
  ts: string;
  corridor: string;
  action: string;
  priority: string | null;
  reason: string;
  policy: string;
  source: string;
};
