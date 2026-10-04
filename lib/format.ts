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
