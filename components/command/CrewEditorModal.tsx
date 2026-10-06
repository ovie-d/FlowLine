"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getCrews, putCrewMap } from "@/lib/forecastApi";
import { HAZARD_SHORT, hazardColor, type HazardGroup } from "@/lib/hazards";
import type { CrewsPayload } from "@/lib/forecastTypes";
import { PanelMessage } from "./ForecastPanel";
import { Modal } from "./Modal";

type Draft = { crew_type_id: string; equipment: string }[];

export function CrewEditorModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const crewsQ = useQuery({ queryKey: ["crews"], queryFn: getCrews, enabled: open });
  return (
    <Modal open={open} onClose={onClose} title="Crew & equipment table" wide>
      {crewsQ.error ? (
        <PanelMessage tone="error" text={String((crewsQ.error as Error).message)} />
      ) : !crewsQ.data ? (
        <div className="h-64 animate-pulse rounded bg-panel-2" aria-busy aria-label="Loading crews" />
      ) : (
        <CrewTable data={crewsQ.data} />
      )}
    </Modal>
  );
}

function CrewTable({ data }: { data: CrewsPayload }) {
  return (
    <div className="grid gap-3 text-[12px]">
      <p className="text-muted">
        {data.has_sample_data && (
          <span className="mr-1 font-semibold text-warn">{data.sample_label}.</span>
        )}
        Seeded rows are illustrative. Rows you save are marked as planner-entered. Crew bases:{" "}
        {data.bases.map((b) => b.name).join(", ")} (sample locations).
      </p>
      {data.hazard_map.map((h) => (
        <HazardRow key={h.hazard_group} data={data} hazard={h.hazard_group} />
      ))}
    </div>
  );
}

function HazardRow({ data, hazard }: { data: CrewsPayload; hazard: HazardGroup }) {
  const qc = useQueryClient();
  const entry = data.hazard_map.find((h) => h.hazard_group === hazard)!;
  const initial: Draft = entry.crews.map((c) => ({ crew_type_id: c.crew_type_id, equipment: c.equipment.join(", ") }));
  const [draft, setDraft] = useState<Draft>(initial);
  const [editing, setEditing] = useState(false);
  const save = useMutation({
    mutationFn: () =>
      putCrewMap(
        hazard,
        draft.map((d, i) => ({
          crew_type_id: d.crew_type_id,
          equipment: d.equipment.split(",").map((s) => s.trim()).filter(Boolean),
          priority: i + 1,
        })),
      ),
    onSuccess: async () => {
      setEditing(false);
      await qc.invalidateQueries({ queryKey: ["crews"] });
      await qc.invalidateQueries({ queryKey: ["readiness"] });
    },
  });
  const unused = data.crew_types.filter((t) => !draft.some((d) => d.crew_type_id === t.id));
  const nameOf = (id: string) => data.crew_types.find((t) => t.id === id)?.name ?? id;

  return (
    <section className="rounded-lg border border-border p-3">
      <header className="mb-2 flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 font-semibold">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: hazardColor(hazard) }} />
          {HAZARD_SHORT[hazard]}
          {entry.low_evidence && <span className="text-[11px] font-normal text-warn">· low evidence</span>}
        </h3>
        {!editing ? (
          <button type="button" className="text-accent hover:underline" onClick={() => setEditing(true)}>Edit</button>
        ) : (
          <span className="flex gap-2">
            <button type="button" className="text-muted hover:text-fg" onClick={() => { setDraft(initial); setEditing(false); }}>Cancel</button>
            <button type="button" disabled={save.isPending} onClick={() => save.mutate()}
              className="rounded bg-accent px-2 py-0.5 font-semibold text-bg disabled:opacity-50">
              {save.isPending ? "Saving…" : "Save"}
            </button>
          </span>
        )}
      </header>
      {save.error && <PanelMessage tone="error" text={(save.error as Error).message} />}
      <ul className="grid gap-1.5">
        {entry.crews.length === 0 && !editing && <li className="text-muted">No crew mapped.</li>}
        {(editing ? draft : initial).map((d, i) => {
          const saved = entry.crews.find((c) => c.crew_type_id === d.crew_type_id);
          return (
            <li key={d.crew_type_id} className="grid gap-1 md:grid-cols-[220px_1fr_auto] md:items-center">
              <span className="text-fg">
                {nameOf(d.crew_type_id)}
                {saved && <span className={`ml-1 text-[10px] ${saved.is_sample ? "text-warn" : "text-safe"}`}>
                  {saved.is_sample ? "sample" : "planner"}</span>}
              </span>
              {editing ? (
                <>
                  <input
                    aria-label={`Equipment for ${nameOf(d.crew_type_id)} (comma-separated)`}
                    value={d.equipment}
                    onChange={(e) => setDraft(draft.map((x, j) => (j === i ? { ...x, equipment: e.target.value } : x)))}
                    className="rounded border border-border bg-panel-2 px-2 py-1 text-fg"
                  />
                  <button type="button" className="text-muted hover:text-critical"
                    onClick={() => setDraft(draft.filter((_, j) => j !== i))}
                    aria-label={`Remove ${nameOf(d.crew_type_id)}`}>Remove</button>
                </>
              ) : (
                <span className="text-muted md:col-span-2">{d.equipment || "—"}</span>
              )}
            </li>
          );
        })}
      </ul>
      {editing && unused.length > 0 && (
        <label className="mt-2 flex items-center gap-2 text-muted">
          Add crew
          <select defaultValue="" onChange={(e) => {
            if (e.target.value) setDraft([...draft, { crew_type_id: e.target.value, equipment: "" }]);
            e.target.value = "";
          }} className="rounded border border-border bg-panel-2 px-1.5 py-0.5 text-fg">
            <option value="" disabled>Choose…</option>
            {unused.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </label>
      )}
    </section>
  );
}
