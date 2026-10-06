"use client";

import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { HazardMap } from "@/components/command/HazardMap";
import type { MapFocus } from "@/components/command/mapTypes";
import { PanelMessage } from "@/components/command/ForecastPanel";
import { SampleChip, SimulationBadge } from "@/components/ui/Badges";
import { InfoTip } from "@/components/ui/InfoTip";
import { dispatchRoute, getForecast } from "@/lib/forecastApi";
import type { Corridor, CrewsPayload, DispatchBase, DispatchResult } from "@/lib/forecastTypes";
import { HAZARD_ORDER, HAZARD_SHORT, type HazardGroup } from "@/lib/hazards";
import { clock, formatMinutes, pointAt, polyline } from "@/lib/routeSim";
import { PrintSheet } from "./PrintSheet";

export type DispatchPoint = { latitude: number; longitude: number; label: string };

type Props = {
  corridors: Corridor[];
  pipelines: GeoJSON.FeatureCollection | null;
  crews: CrewsPayload | null;
  today: string;
  at: DispatchPoint | null;
  onAt: (p: DispatchPoint | null) => void;
  manualHazard: HazardGroup | null;
  onManualHazard: (h: HazardGroup | null) => void;
};

const K_BASES = 5;
const SPEEDS = [60, 300, 1200] as const;

export type SimPhase = "idle" | "reported" | "notified" | "enroute" | "onscene";
export type Sim = {
  key: string;
  phase: SimPhase;
  reportedAt: Date | null;
  notifiedAt: Date | null;
  progress: number;
  playing: boolean;
  speed: number;
};

const IDLE = (key: string): Sim => ({ key, phase: "idle", reportedAt: null, notifiedAt: null, progress: 0, playing: false, speed: 300 });

function errorText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export default function DispatchView(p: Props) {
  const { at } = p;
  const [query, setQuery] = useState(at && !at.label.includes(",") ? at.label : "");
  const [notFound, setNotFound] = useState(false);
  const [focus, setFocus] = useState<MapFocus | null>(() => (at ? { ...at, zoom: 7, key: 1 } : null));
  const [pickedBase, setPickedBase] = useState<string | null>(null);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [printImg, setPrintImg] = useState<string | null>(null);
  const snapshot = useRef<(() => string | null) | null>(null);
  const registerSnapshot = useCallback((fn: (() => string | null) | null) => {
    snapshot.current = fn;
  }, []);

  // Hazard: prefilled from the forecast's top hazard at the pin; the user can override.
  const forecastQ = useQuery({
    queryKey: ["dispatch-forecast", at?.latitude, at?.longitude, p.today],
    queryFn: () => getForecast({ latitude: at!.latitude, longitude: at!.longitude }, p.today),
    enabled: !!at,
    staleTime: 5 * 60_000,
  });
  const top = forecastQ.data?.hazards[0] ?? null;
  const hazard: HazardGroup | null = p.manualHazard ?? top?.hazard_group ?? null;

  const dispatchQ = useQuery<DispatchResult>({
    queryKey: ["dispatch", at?.latitude, at?.longitude, hazard],
    queryFn: () => dispatchRoute(at!.latitude, at!.longitude, hazard!, K_BASES),
    enabled: !!at && !!hazard,
    staleTime: 5 * 60_000,
  });
  const result = dispatchQ.data ?? null;
  const bases = useMemo(() => result?.bases ?? [], [result]);
  const active: DispatchBase | null = bases.find((b) => b.base_id === pickedBase) ?? bases[0] ?? null;

  // Simulation resets whenever the pin, hazard or selected base changes.
  const simKey = `${at?.latitude},${at?.longitude},${hazard},${active?.base_id}`;
  const [simState, setSim] = useState<Sim>(() => IDLE(simKey));
  const sim = simState.key === simKey ? simState : IDLE(simKey);

  // Fit the map to the pin and every ranked route whenever the ranking changes.
  const fit = useMemo<MapFocus | null>(() => {
    if (!at || !bases.length) return null;
    const pts: GeoJSON.Position[] = [[at.longitude, at.latitude]];
    for (const b of bases) {
      pts.push([b.longitude, b.latitude], ...(b.route.geometry?.coordinates ?? []));
    }
    const lons = pts.map((q) => q[0]);
    const lats = pts.map((q) => q[1]);
    return {
      ...at,
      key: bases.length,
      bounds: [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
    };
  }, [at, bases]);

  const road = useMemo(() => (active?.route.geometry ? polyline(active.route.geometry.coordinates) : null), [active]);
  const duration = active?.route.duration_min ?? null;

  // Animate the crew along the road route; playback time = router drive time / speed.
  useEffect(() => {
    if (sim.phase !== "enroute" || !sim.playing || !duration) return;
    let last = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      setSim((s) => {
        if (s.key !== simKey || s.phase !== "enroute") return s;
        const progress = Math.min(1, s.progress + (dt * s.speed) / (duration * 60));
        return progress >= 1 ? { ...s, progress: 1, phase: "onscene", playing: false } : { ...s, progress };
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [sim.phase, sim.playing, duration, simKey]);

  const vehicle = useMemo(() => {
    if (!active || sim.phase === "idle") return null;
    if (sim.phase === "onscene") return at ? { latitude: at.latitude, longitude: at.longitude } : null;
    if (sim.phase === "enroute" && road) return pointAt(road, sim.progress);
    return { latitude: active.latitude, longitude: active.longitude };
  }, [active, sim.phase, sim.progress, road, at]);

  function drop(latitude: number, longitude: number, label: string, fly = false) {
    p.onAt({ latitude, longitude, label });
    p.onManualHazard(null);
    setPickedBase(null);
    setChecked({});
    if (fly) setFocus({ latitude, longitude, zoom: 7, key: Date.now() });
  }

  function search(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim().toLowerCase();
    const hit = p.corridors.find((c) => c.name.toLowerCase() === q) ?? p.corridors.find((c) => c.name.toLowerCase().startsWith(q));
    setNotFound(!hit);
    if (hit) {
      setQuery(hit.name);
      drop(hit.latitude, hit.longitude, hit.name, true);
    }
  }

  function printSummary() {
    setPrintImg(snapshot.current?.() ?? null);
    window.setTimeout(() => window.print(), 150);
  }

  const crewsForHazard = useMemo(
    () => p.crews?.hazard_map.find((h) => h.hazard_group === hazard)?.crews ?? [],
    [p.crews, hazard],
  );
  const checklist = useMemo(() => {
    if (!active) return [];
    const ids = new Set(active.matching_crews.map((c) => c.crew_type_id));
    return crewsForHazard.filter((c) => ids.has(c.crew_type_id));
  }, [active, crewsForHazard]);

  const banner = !at ? (
    <div className="pointer-events-none absolute left-1/2 top-12 -translate-x-1/2 rounded-md border border-critical bg-panel px-3 py-1.5 text-[12px] font-semibold text-fg shadow">
      Click the map or search an area to drop the incident pin
    </div>
  ) : null;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_440px]">
      <div className="relative h-[clamp(380px,65vh,820px)] xl:sticky xl:top-14 xl:h-[calc(100dvh-3.5rem)]">
        <HazardMap
          incidents={null}
          pipelines={p.pipelines}
          bases={p.crews?.bases ?? []}
          selected={at}
          similar={[]}
          routes={bases.length ? bases : null}
          activeRouteId={active?.base_id ?? null}
          focus={fit ?? focus}
          pickMode="dispatch"
          vehicle={vehicle}
          onPick={(lat, lon) => {
            setQuery("");
            drop(lat, lon, `${lat.toFixed(3)}, ${lon.toFixed(3)}`);
          }}
          registerSnapshot={registerSnapshot}
          banner={banner}
        />
      </div>

      <aside className="flex min-w-0 flex-col gap-4 border-t border-border bg-panel p-4 xl:border-l xl:border-t-0" aria-label="Emergency dispatch">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-[15px] font-semibold text-fg">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-critical-strong" aria-hidden />
            Emergency dispatch
          </h2>
          <SampleChip />
        </header>

        <Section title="1 · Incident location">
          <form onSubmit={search} role="search" className="flex gap-2">
            <label htmlFor="dispatch-search" className="sr-only">Search an area</label>
            <input
              id="dispatch-search"
              list="dispatch-corridors"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setNotFound(false);
              }}
              placeholder="Search area (e.g. Edson)"
              aria-invalid={notFound}
              className="min-w-0 flex-1 rounded-md border border-border bg-panel-2 px-2.5 py-1.5 text-[13px] text-fg placeholder:text-muted"
            />
            <datalist id="dispatch-corridors">
              {p.corridors.map((c) => <option key={c.name} value={c.name} />)}
            </datalist>
            <button type="submit" className="rounded-md border border-border px-3 text-[12px] text-fg hover:border-accent">Go</button>
          </form>
          {notFound && <p role="status" className="mt-1 text-[11px] text-warn">No matching area. Try another name or click the map.</p>}
          <p className="mt-1.5 text-[12px] text-muted">
            {at ? (
              <>
                Pin: <span className="font-semibold text-fg">{at.label}</span>{" "}
                <span className="font-mono">({at.latitude.toFixed(4)}, {at.longitude.toFixed(4)})</span>
                <button type="button" onClick={() => { p.onAt(null); setQuery(""); }} className="ml-2 text-accent hover:underline">
                  Clear
                </button>
              </>
            ) : (
              "Or click the incident location on the map."
            )}
          </p>
        </Section>

        <Section title="2 · Hazard">
          <select
            value={hazard ?? ""}
            disabled={!at}
            onChange={(e) => p.onManualHazard(e.target.value as HazardGroup)}
            className="w-full rounded-md border border-border bg-panel-2 px-2 py-1.5 text-[13px] text-fg disabled:opacity-50"
            aria-label="Hazard"
          >
            {!hazard && <option value="">{at ? (forecastQ.isFetching ? "Reading the forecast…" : "Pick a hazard") : "Drop a pin first"}</option>}
            {HAZARD_ORDER.map((g) => <option key={g} value={g}>{HAZARD_SHORT[g]}</option>)}
          </select>
          <p className="mt-1 text-[11px] text-muted">
            {!at ? null : p.manualHazard ? (
              <>Chosen by you.{top && <> Forecast top hazard here: {HAZARD_SHORT[top.hazard_group]} ({top.display}).</>}</>
            ) : top ? (
              <>Prefilled from the forecast&apos;s top hazard here ({top.lower_certainty ? ">50%, lower certainty" : top.display}).</>
            ) : forecastQ.error ? (
              <>Forecast unavailable ({errorText(forecastQ.error)}); pick the hazard.</>
            ) : null}
          </p>
        </Section>

        <Section title="3 · Crew bases by drive time" aside={result && <span className="text-[11px] text-muted">top {bases.length} with a matching crew</span>}>
          {!at ? (
            <PanelMessage text="Drop the incident pin to rank crew bases." />
          ) : dispatchQ.error ? (
            <PanelMessage tone="error" text={errorText(dispatchQ.error)} />
          ) : dispatchQ.isFetching && !result ? (
            <div className="grid gap-2" aria-busy aria-label="Routing crews">
              {[0, 1, 2].map((i) => <div key={i} className="h-20 animate-pulse rounded-md bg-panel-2" />)}
            </div>
          ) : result ? (
            <ol className={`grid gap-2 transition-opacity ${dispatchQ.isFetching ? "opacity-60" : ""}`}>
              {result.message && <PanelMessage text={result.message} />}
              {bases.map((b, i) => (
                <BaseCard
                  key={b.base_id}
                  b={b}
                  rank={i + 1}
                  active={b.base_id === active?.base_id}
                  recommended={crewsForHazard.length}
                  onSelect={() => setPickedBase(b.base_id)}
                />
              ))}
            </ol>
          ) : null}
        </Section>

        {active && (
          <Section title="4 · Response timeline" aside={<SimulationBadge />}>
            <Timeline
              sim={sim}
              base={active}
              onStart={() => setSim({ ...IDLE(simKey), phase: "reported", reportedAt: new Date(), speed: sim.speed })}
              onNotify={() => setSim({ ...sim, phase: "enroute", notifiedAt: new Date(), progress: 0, playing: !!duration })}
              onToggle={() => setSim({ ...sim, playing: !sim.playing })}
              onReset={() => setSim({ ...IDLE(simKey), speed: sim.speed })}
              onSpeed={(speed) => setSim({ ...sim, speed })}
            />
          </Section>
        )}

        {active && (
          <Section title={`5 · Equipment checklist · ${active.base_name}`} aside={<SampleChip tip="Equipment comes from the crew table (Edit crew table on the forecast page). Sample until validated." />}>
            {checklist.length === 0 ? (
              <PanelMessage text="No equipment listed for these crews in the crew table." />
            ) : (
              <div className="grid gap-2.5">
                {checklist.map((c) => (
                  <fieldset key={c.crew_type_id}>
                    <legend className="text-[12px] font-semibold text-fg">{c.crew_name}</legend>
                    <ul className="mt-1 grid gap-0.5">
                      {c.equipment.map((item) => {
                        const k = `${active.base_id}:${c.crew_type_id}:${item}`;
                        return (
                          <li key={item}>
                            <label className="flex items-center gap-2 text-[12px] text-fg">
                              <input type="checkbox" checked={!!checked[k]} onChange={() => setChecked((s) => ({ ...s, [k]: !s[k] }))} className="accent-[var(--accent)]" />
                              <span className={checked[k] ? "text-muted line-through" : ""}>{item}</span>
                            </label>
                          </li>
                        );
                      })}
                    </ul>
                  </fieldset>
                ))}
              </div>
            )}
          </Section>
        )}

        {active && result && (
          <button
            type="button"
            onClick={printSummary}
            className="rounded-md border border-accent px-3 py-2 text-[13px] font-semibold text-accent hover:bg-panel-2"
          >
            Print / save one-page summary (PDF)
          </button>
        )}
      </aside>

      {active && result && at && typeof document !== "undefined" &&
        createPortal(
          <PrintSheet
            at={at}
            hazard={hazard!}
            hazardSource={p.manualHazard ? "chosen by the dispatcher" : top ? `forecast top hazard (${top.lower_certainty ? ">50%, lower certainty" : top.display})` : "chosen by the dispatcher"}
            result={result}
            active={active}
            checklist={checklist}
            checked={checked}
            sim={sim}
            mapImage={printImg}
          />,
          document.body,
        )}
    </div>
  );
}

function Section({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="min-w-0">
      <header className="mb-1.5 flex items-center justify-between gap-2">
        <h3 className="text-[12px] font-semibold uppercase tracking-[0.08em] text-muted">{title}</h3>
        {aside}
      </header>
      {children}
    </section>
  );
}

function BaseCard({ b, rank, active, recommended, onSelect }: {
  b: DispatchBase; rank: number; active: boolean; recommended: number; onSelect: () => void;
}) {
  const r = b.route;
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={active}
        className={`w-full rounded-md border p-2.5 text-left transition-colors ${active ? "border-accent bg-panel-2" : "border-border hover:border-muted"}`}
      >
        <div className="flex items-start justify-between gap-2">
          <span className="text-[13px] font-semibold text-fg">
            <span className="mr-1.5 inline-flex h-5 w-5 items-center justify-center rounded-full border border-border text-[11px]">{rank}</span>
            {b.base_name}
          </span>
          <InfoTip tip={r.duration_min == null ? "No road route found: only the straight-line distance is known." : `Drive time from ${routerName(r.provider)}. No traffic, weather or mobilisation time.`} align="end" focusable={false}>
            <span className="font-mono text-[14px] font-semibold text-fg">{formatMinutes(r.duration_min)}</span>
          </InfoTip>
        </div>
        <div className="mt-1.5 grid grid-cols-3 gap-2 text-[11px]">
          <Stat label="Crew match" align="start" value={`${b.matching_crews.length} of ${recommended}`}
            tip={`Crews at this base that the crew table recommends for this hazard: ${b.matching_crews.map((c) => c.crew_name).join(", ") || "none"}.`} />
          <Stat label="Road distance" value={`${r.distance_km} km`} tip={`Route length via ${r.provider}${r.provider === "straight_line" ? " (straight line, not a road)" : ""}.`} />
          <Stat
            label="Off-road last mile"
            align="end"
            value={r.last_mile ? `${r.last_mile.distance_km} km` : "none"}
            tip={r.last_mile ? `${r.last_mile.label}. Straight-line distance from the nearest road to the pin; travel time not modelled.` : "The route reaches the pin by road."}
          />
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1">
          {b.matching_crews.map((c) => (
            <span key={c.crew_type_id} className="rounded bg-panel px-1.5 py-0.5 text-[11px] text-fg ring-1 ring-border">{c.crew_name}</span>
          ))}
        </div>
        {r.warning && <div className="mt-1 text-[11px] text-warn">{r.warning}</div>}
      </button>
    </li>
  );
}

function routerName(provider: string): string {
  if (provider === "osrm") return "the OSRM router on OpenStreetMap roads";
  if (provider === "mapbox") return "Mapbox Directions";
  return `the ${provider} router`;
}

function Stat({ label, value, tip, align = "center" }: { label: string; value: string; tip: string; align?: "start" | "center" | "end" }) {
  return (
    <div className="min-w-0">
      <div className="text-muted">{label}</div>
      <InfoTip tip={tip} align={align} focusable={false}>
        <span className="font-mono text-[12px] text-fg">{value}</span>
      </InfoTip>
    </div>
  );
}

function Timeline({ sim, base, onStart, onNotify, onToggle, onReset, onSpeed }: {
  sim: Sim; base: DispatchBase; onStart: () => void; onNotify: () => void; onToggle: () => void; onReset: () => void; onSpeed: (s: number) => void;
}) {
  const d = base.route.duration_min;
  const order: SimPhase[] = ["reported", "notified", "enroute", "onscene"];
  const at = order.indexOf(sim.phase);
  const eta = sim.notifiedAt && d != null ? new Date(sim.notifiedAt.getTime() + d * 60_000) : null;
  const steps: { key: SimPhase; label: string; detail: React.ReactNode }[] = [
    { key: "reported", label: "Reported", detail: sim.reportedAt ? `${clock(sim.reportedAt)} (when you started)` : "Start the simulation" },
    { key: "notified", label: "Crew notified", detail: sim.notifiedAt ? `${clock(sim.notifiedAt)} · ${base.base_name}` : "Notification and mobilisation time not modelled" },
    {
      key: "enroute",
      label: "En route",
      detail: d == null ? "No router drive time for this base, so the drive cannot be simulated."
        : sim.phase === "enroute" ? `${formatMinutes(sim.progress * d)} of ${formatMinutes(d)} drive (router ETA)` : `${formatMinutes(d)} drive (router ETA)`,
    },
    {
      key: "onscene",
      label: "On scene",
      detail: eta ? `ETA ${clock(eta)}${base.route.last_mile ? ` + ${base.route.last_mile.distance_km} km off-road (time not modelled)` : ""}` : "—",
    },
  ];
  return (
    <div className="rounded-md border border-dashed border-highlight/70 p-2.5">
      <ol className="grid gap-2">
        {steps.map((s, i) => {
          const done = at > i || sim.phase === "onscene";
          const current = at === i && sim.phase !== "onscene";
          return (
            <li key={s.key} className="flex gap-2.5">
              <span
                aria-hidden
                className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 text-[9px] ${done ? "border-safe bg-safe text-bg" : current ? "border-highlight" : "border-border"}`}
              >
                {done ? "✓" : ""}
              </span>
              <div className="min-w-0 text-[12px]">
                <div className={`font-semibold ${done || current ? "text-fg" : "text-muted"}`}>
                  {s.label}
                  {current && <span className="sr-only"> (current step)</span>}
                </div>
                <div className="text-[11px] text-muted">{s.detail}</div>
                {s.key === "enroute" && sim.phase === "enroute" && d != null && (
                  <div className="mt-1 h-1.5 w-full overflow-hidden rounded bg-panel-2" role="progressbar" aria-valuenow={Math.round(sim.progress * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="Simulated drive progress">
                    <div className="h-full bg-highlight" style={{ width: `${sim.progress * 100}%` }} />
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        {sim.phase === "idle" && (
          <button type="button" onClick={onStart} className="rounded-md bg-critical-strong px-3 py-1.5 text-[12px] font-semibold text-white hover:brightness-110">
            Start simulation
          </button>
        )}
        {sim.phase === "reported" && (
          <button type="button" onClick={onNotify} className="rounded-md bg-critical-strong px-3 py-1.5 text-[12px] font-semibold text-white hover:brightness-110">
            Notify crew (simulated)
          </button>
        )}
        {sim.phase === "enroute" && d != null && (
          <button type="button" onClick={onToggle} className="rounded-md border border-border px-3 py-1.5 text-[12px] text-fg hover:border-accent">
            {sim.playing ? "Pause" : "Resume"}
          </button>
        )}
        {sim.phase !== "idle" && (
          <button type="button" onClick={onReset} className="rounded-md border border-border px-3 py-1.5 text-[12px] text-muted hover:text-fg">
            Reset
          </button>
        )}
        <label className="ml-auto flex items-center gap-1 text-[11px] text-muted">
          Playback
          <select value={sim.speed} onChange={(e) => onSpeed(Number(e.target.value))} className="rounded border border-border bg-panel-2 px-1 py-0.5 text-fg">
            {SPEEDS.map((s) => <option key={s} value={s}>{s}× faster</option>)}
          </select>
        </label>
      </div>
    </div>
  );
}
