export type Confidence = "ok" | "low";

export type Driver = {
  date?: string | null;
  type?: string;
  substance?: string;
  weight?: number;
};

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
  drivers?: Driver[];
  operator?: string;
  lat: number | null;
  lon: number | null;
  last_incident?: string | null;
};

export type TriageAction = "escalate" | "inspect" | "defer";

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
  drivers: Driver[];
  last_incident: string | null;
  lat?: number | null;
  lon?: number | null;
};

export type ImprovementStage = {
  stage: string;
  serious_captured?: number;
  serious_total?: number;
  incidents_covered?: number;
  [key: string]: unknown;
};

/** Legacy stages payload from GET /improvement (no high). */
export type ImprovementRound = {
  stages: ImprovementStage[];
  ours_heavy?: ImprovementStage;
  summary?: string;
  weights?: Record<string, number>;
};

/** Slider-scoped payload from GET /improvement?high=H. */
export type ImprovementFor = {
  policy: {
    high: number;
    medium?: number;
    low?: number;
    count_only?: boolean;
  };
  serious_total: number;
  current: {
    serious_captured: number;
    incidents_covered: number;
  };
  baseline: {
    serious_captured: number;
    incidents_covered: number;
  };
};

export type Improvement = ImprovementRound | ImprovementFor;

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
  policy: string | Record<string, unknown>;
  source: string;
};
