/** Move vs count-only baseline rank. Positive = moved up (better priority). */
export function moveDelta(
  baselineRank: number | undefined,
  currentRank: number,
): number | null {
  if (baselineRank == null) return null;
  return baselineRank - currentRank;
}

/** Mockup format: +n / −n / — */
export function formatMove(delta: number | null): string {
  if (delta == null || delta === 0) return "—";
  return delta > 0 ? `+${delta}` : `${delta}`;
}

export function moveColor(delta: number | null): string {
  if (delta == null || delta === 0) return "#6B6F75";
  return delta > 0 ? "#A8370A" : "#1D4ED8";
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-CA", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function policyLabel(high: number): string {
  if (high <= 1) return "count_only";
  return `high=${high}`;
}

/** Display string for the policy bar (mockup). */
export function policyText(high: number): string {
  if (high <= 1) return "Count-only · every incident = 1";
  return `high ${high}× · medium 1.5× · low 1×`;
}

export function sevColor(nHigh: number): string {
  if (nHigh >= 3) return "#A8370A";
  if (nHigh >= 1) return "#E0904A";
  return "#9C9FA5";
}

const TYPE_SHORT: Record<string, string> = {
  "Release of Substance": "Release",
  "Serious Injury (as defined in the OPR)": "Serious injury",
  "Operation Beyond Design Limits": "Limit breach",
  "Adverse Environmental Effects": "Environmental effect",
};

export function shortIncidentType(type: string): string {
  return TYPE_SHORT[type] ?? type;
}

export function formatSubstance(substance: string | null | undefined): string {
  if (!substance || substance === "Not Applicable") return "no release";
  return substance;
}

/** Driver row: `{type} · {substance} · {date}` */
export function formatDriverLabel(d: {
  type?: string;
  substance?: string;
  date?: string | null;
}): string {
  const type = shortIncidentType(d.type ?? "Incident");
  const substance = formatSubstance(d.substance);
  const date = formatDate(d.date);
  return `${type} · ${substance} · ${date}`;
}

/** Map driver weight to severity chip. */
export function driverSeverity(
  weight: number | undefined,
): "high" | "medium" | "low" {
  if (weight == null) return "low";
  if (weight >= 2.5) return "high";
  if (weight >= 1.25) return "medium";
  return "low";
}

export function capitalizeAction(action: string): string {
  if (!action) return "";
  return action.charAt(0).toUpperCase() + action.slice(1).toLowerCase();
}

function formatChipNumber(n: number): string {
  return Number.isInteger(n) || n === Math.trunc(n)
    ? String(Math.trunc(n))
    : String(n);
}

function formatChipScalar(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (typeof value === "number" && Number.isFinite(value)) {
    return formatChipNumber(value);
  }
  if (typeof value === "boolean") return value ? "true" : "false";
  return null;
}

/** Policy label for chips / decision log — never returns an object. */
export function formatPolicy(p: unknown): string {
  if (p == null) return "";
  if (typeof p === "string") return p;
  if (typeof p === "number" && Number.isFinite(p)) {
    if (p === 1) return "count_only";
    return `high=${formatChipNumber(p)}`;
  }
  if (typeof p !== "object" || Array.isArray(p)) return "";
  const o = p as Record<string, unknown>;
  if (o.count_only === true || o.high === 1) return "count_only";
  if (typeof o.high === "number" && Number.isFinite(o.high)) {
    return `high=${formatChipNumber(o.high)}`;
  }
  return "";
}

/** Coerce unknown values to a string safe for JSX text children. */
export function asDisplayText(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" && Number.isFinite(value)) {
    return formatChipNumber(value);
  }
  return formatPolicy(value);
}

function policyChipToken(input: Record<string, unknown>): string | null {
  for (const key of ["policy", "config", "config_overrides"] as const) {
    const token = formatPolicy(input[key]);
    if (token) return token;
  }
  if (input.count_only === true || input.high === 1) return "count_only";
  if (typeof input.high === "number" && Number.isFinite(input.high)) {
    return `high=${formatChipNumber(input.high)}`;
  }
  return null;
}

/** Agent tool chip label — never prints [object Object]. */
export function formatToolChip(
  name: string,
  input?: Record<string, unknown> | null,
): string {
  if (!input || Object.keys(input).length === 0) return `${name}()`;

  const parts: string[] = [];
  const used = new Set<string>();

  const corridor =
    typeof input.name === "string"
      ? input.name
      : typeof input.corridor === "string"
        ? input.corridor
        : null;
  if (corridor) {
    parts.push(corridor);
    used.add("name");
    used.add("corridor");
  }

  const policy = policyChipToken(input);
  if (policy) {
    parts.push(policy);
    used.add("policy");
    used.add("config");
    used.add("config_overrides");
    used.add("high");
    used.add("count_only");
  }

  if (typeof input.priority === "string" && input.priority) {
    parts.push(input.priority);
    used.add("priority");
  }
  if (typeof input.action === "string" && input.action) {
    parts.push(input.action);
    used.add("action");
  }

  for (const [key, value] of Object.entries(input)) {
    if (used.has(key)) continue;
    if (value !== null && typeof value === "object") continue;
    const scalar = formatChipScalar(value);
    if (scalar == null) continue;
    parts.push(`${key}=${scalar}`);
  }

  if (parts.length === 0) return `${name}()`;
  return `${name}(${parts.join(", ")})`;
}
