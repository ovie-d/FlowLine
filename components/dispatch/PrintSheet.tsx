"use client";

import type { CrewEntry, DispatchBase, DispatchResult } from "@/lib/forecastTypes";
import { HAZARD_SHORT, type HazardGroup } from "@/lib/hazards";
import { clock, formatMinutes } from "@/lib/routeSim";
import type { DispatchPoint, Sim } from "./DispatchView";

type Props = {
  at: DispatchPoint;
  hazard: HazardGroup;
  hazardSource: string;
  result: DispatchResult;
  active: DispatchBase;
  checklist: CrewEntry[];
  checked: Record<string, boolean>;
  sim: Sim;
  mapImage: string | null;
};

const PHASE_TEXT: Record<Sim["phase"], string> = {
  idle: "Not started",
  reported: "Reported",
  notified: "Crew notified",
  enroute: "En route",
  onscene: "On scene",
};

/** One-page dispatch summary; hidden on screen, the only thing printed (globals.css). */
export function PrintSheet({ at, hazard, hazardSource, result, active, checklist, checked, sim, mapImage }: Props) {
  const now = new Date();
  const th = "border-b border-[#cbd5e3] px-1.5 py-1 text-left font-semibold";
  const td = "border-b border-[#e9eef5] px-1.5 py-1 align-top";
  return (
    <div className="print-sheet" style={{ fontSize: 11, lineHeight: 1.35 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", borderBottom: "2px solid #0b1f3a", paddingBottom: 6 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Flowline · Emergency dispatch summary</div>
          <div>
            Printed {now.toLocaleDateString("en-CA", { timeZone: "America/Edmonton" })} {clock(now)} (Alberta time)
          </div>
        </div>
        <div style={{ textAlign: "right", fontWeight: 700 }}>
          <div style={{ color: "#854d0e" }}>SAMPLE CREW DATA — TO BE VALIDATED</div>
          <div style={{ background: "#facc15", padding: "1px 6px", display: "inline-block", marginTop: 2 }}>TIMELINE IS A SIMULATION</div>
        </div>
      </div>

      <table style={{ width: "100%", marginTop: 8, borderCollapse: "collapse" }}>
        <tbody>
          <tr>
            <td className={td} style={{ width: "22%" }}><b>Incident location</b></td>
            <td className={td}>{at.label} ({at.latitude.toFixed(4)}, {at.longitude.toFixed(4)})</td>
          </tr>
          <tr>
            <td className={td}><b>Hazard</b></td>
            <td className={td}>{HAZARD_SHORT[hazard]} — {hazardSource}</td>
          </tr>
          <tr>
            <td className={td}><b>Selected base</b></td>
            <td className={td}>
              {active.base_name}: {formatMinutes(active.route.duration_min)} drive, {active.route.distance_km} km via {active.route.provider}
              {active.route.last_mile && `, then ${active.route.last_mile.distance_km} km off-road (${active.route.last_mile.label})`}
            </td>
          </tr>
          <tr>
            <td className={td}><b>Simulation status</b></td>
            <td className={td}>
              {PHASE_TEXT[sim.phase]}
              {sim.reportedAt && ` · reported ${clock(sim.reportedAt)}`}
              {sim.notifiedAt && ` · crew notified ${clock(sim.notifiedAt)}`}
              {sim.notifiedAt && active.route.duration_min != null &&
                ` · ETA ${clock(new Date(sim.notifiedAt.getTime() + active.route.duration_min * 60_000))} (router drive time only)`}
            </td>
          </tr>
        </tbody>
      </table>

      {mapImage && (
        // eslint-disable-next-line @next/next/no-img-element -- data URL snapshot of the live map
        <img src={mapImage} alt="Map of the incident and routes" style={{ width: "100%", maxHeight: 300, objectFit: "cover", marginTop: 8, border: "1px solid #cbd5e3" }} />
      )}

      <div style={{ fontWeight: 700, marginTop: 10 }}>Crew bases ranked by drive time</div>
      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 2 }}>
        <thead>
          <tr>
            <th className={th}>#</th>
            <th className={th}>Base</th>
            <th className={th}>Drive time</th>
            <th className={th}>Road km</th>
            <th className={th}>Off-road km</th>
            <th className={th}>Matching crews</th>
          </tr>
        </thead>
        <tbody>
          {result.bases.map((b, i) => (
            <tr key={b.base_id} style={b.base_id === active.base_id ? { background: "#fef3c7" } : undefined}>
              <td className={td}>{i + 1}</td>
              <td className={td}>{b.base_name}{b.base_id === active.base_id && " (selected)"}</td>
              <td className={td}>{formatMinutes(b.route.duration_min)}</td>
              <td className={td}>{b.route.distance_km}</td>
              <td className={td}>{b.route.last_mile ? b.route.last_mile.distance_km : "—"}</td>
              <td className={td}>{b.matching_crews.map((c) => c.crew_name).join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ fontWeight: 700, marginTop: 10 }}>Equipment checklist · {active.base_name}</div>
      {checklist.length === 0 ? (
        <div>No equipment listed for these crews in the crew table.</div>
      ) : (
        <div style={{ columns: 2, marginTop: 2 }}>
          {checklist.map((c) => (
            <div key={c.crew_type_id} style={{ breakInside: "avoid", marginBottom: 4 }}>
              <b>{c.crew_name}</b>
              {c.equipment.map((item) => (
                <div key={item}>{checked[`${active.base_id}:${c.crew_type_id}:${item}`] ? "☑" : "☐"} {item}</div>
              ))}
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 12, paddingTop: 6, borderTop: "1px solid #cbd5e3", fontSize: 10 }}>
        Drive times come from the road router named above (no traffic or weather). Notification,
        mobilisation and off-road travel times are not modelled. Crew bases, crews and equipment are sample
        data until validated. Forecasts are based on historical public incident data. Flowline supports
        engineering judgment; it does not certify any pipe as safe.
      </div>
    </div>
  );
}
