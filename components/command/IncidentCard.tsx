"use client";

import { useQuery } from "@tanstack/react-query";
import { getIncidentDetail } from "@/lib/forecastApi";
import { hazardColor } from "@/lib/hazards";

/** Incident detail for a clicked map point: CER fields only, cause codes in plain English. */
export function IncidentCard({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["incident", id], queryFn: () => getIncidentDetail(id), staleTime: Infinity });
  if (q.error) return <p className="text-[12px] text-critical">Could not load {id}: {String((q.error as Error).message)}</p>;
  const d = q.data;
  if (!d) {
    return (
      <div className="grid w-60 gap-1.5" aria-busy aria-label="Loading incident">
        <div className="h-3 w-2/3 animate-pulse rounded bg-panel-2" />
        <div className="h-3 animate-pulse rounded bg-panel-2" />
        <div className="h-3 w-1/2 animate-pulse rounded bg-panel-2" />
      </div>
    );
  }
  const what = [...d.what_happened, ...d.what_detail];
  const why = [...d.why, ...d.why_detail];
  return (
    <div className="grid w-64 gap-1 text-[12px] leading-snug">
      <div className="flex items-center gap-1.5 font-semibold text-fg">
        <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: hazardColor(d.hazard_group) }} />
        {d.hazard_label}
      </div>
      <div className="text-muted">
        {d.place}, {d.province} · {d.date}
        {d.date_source !== "occurred" && <> ({d.date_source} date)</>}
      </div>
      <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5">
        <dt className="text-muted">Operator</dt>
        <dd className="text-fg">{d.operator}</dd>
        {d.incident_types.length > 0 && (
          <>
            <dt className="text-muted">Type</dt>
            <dd className="text-fg">{d.incident_types.join(", ")}</dd>
          </>
        )}
        <dt className="text-muted">What</dt>
        <dd className="text-fg">{what.length ? what.join(" · ") : "Not yet determined"}</dd>
        <dt className="text-muted">Why</dt>
        <dd className="text-fg">{why.length ? why.join(" · ") : "Not yet determined"}</dd>
      </dl>
      <div className="mt-1 text-[11px] text-muted">
        {d.incident_number} · {d.status ?? "status not given"} · {d.source}
      </div>
    </div>
  );
}
