"use client";

import type { RankingRow, Triage } from "@/lib/types";

type Props = {
  topCorridor: string | null;
  topRow: RankingRow | null;
  seriousTop15: number | null;
  seriousTotal: number | null;
  seriousBaseline: number | null;
  incidentsTop15: number | null;
  incidentsBaseline: number | null;
  triage: Triage | undefined;
};

export function StatCards({
  topCorridor,
  topRow,
  seriousTop15,
  seriousTotal,
  seriousBaseline,
  incidentsTop15,
  incidentsBaseline,
  triage,
}: Props) {
  const escalate = triage?.counts?.Escalate ?? triage?.counts?.escalate ?? 0;
  const inspect = triage?.counts?.Inspect ?? triage?.counts?.inspect ?? 0;
  const defer = triage?.counts?.Defer ?? triage?.counts?.defer ?? 0;

  return (
    <section
      className="grid gap-3"
      style={{ gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}
    >
      <Card label="Top priority corridor">
        <div
          className="font-display text-[26px] leading-[1.1] text-[#15171A]"
          style={{ marginTop: 2 }}
        >
          {topCorridor ?? "—"}
        </div>
        <div className="mt-0.5 text-[13px] text-[#5A5F66]">
          {topRow
            ? `${topRow.n} incidents · ${topRow.n_high} high-consequence`
            : "waiting"}
        </div>
      </Card>

      <Card label="Serious events inside the top 15">
        <div
          className="font-mono text-[22px] font-semibold text-[#15171A]"
          style={{ marginTop: 2 }}
        >
          {seriousTop15 ?? "—"}
          <span className="text-[15px] font-medium text-[#5A5F66]">
            {" "}
            / {seriousTotal ?? "—"}
          </span>
        </div>
        <div className="mt-0.5 text-[13px] text-[#5A5F66]">
          Count-only baseline finds {seriousBaseline ?? "—"}
        </div>
      </Card>

      <Card label="Incidents crews would review">
        <div
          className="font-mono text-[22px] font-semibold text-[#15171A]"
          style={{ marginTop: 2 }}
        >
          {incidentsTop15 ?? "—"}
        </div>
        <div className="mt-0.5 text-[13px] text-[#5A5F66]">
          Count-only baseline: {incidentsBaseline ?? "—"}
        </div>
      </Card>

      <Card label="Agent drafts">
        <div
          className="font-mono text-[22px] font-semibold"
          style={{ marginTop: 2 }}
        >
          <span style={{ color: "#A8370A" }}>{escalate}</span>
          <span className="text-[15px] font-medium text-[#5A5F66]">
            {" "}
            escalate · {inspect} inspect · {defer} defer
          </span>
        </div>
        <div className="mt-0.5 text-[13px] text-[#5A5F66]">
          Awaiting planner approval
        </div>
      </Card>
    </section>
  );
}

function Card({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-xl border border-[#E3E3DE] bg-white"
      style={{ padding: "12px 16px" }}
    >
      <div className="text-[13px] text-[#5A5F66]">{label}</div>
      {children}
    </div>
  );
}
