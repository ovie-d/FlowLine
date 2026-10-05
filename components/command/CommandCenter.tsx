"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { DecisionLog } from "@/components/DecisionLog";
import { getDecisions } from "@/lib/api";
import {
  dispatchRoute,
  getAgentStatus,
  getBriefing,
  getCorridors,
  getCrews,
  getIncidentPoints,
  getPipelines,
  getReadiness,
  getWashout,
  logAgentUsage,
  type Where,
} from "@/lib/forecastApi";
import type { Corridor, SimilarIncident } from "@/lib/forecastTypes";
import type { HazardGroup } from "@/lib/hazards";
import { AboutModelModal } from "./AboutModelModal";
import { CrewEditorModal } from "./CrewEditorModal";
import { EvidencePanel } from "./EvidencePanel";
import { Footer } from "./Footer";
import { ForecastPanel, PanelMessage } from "./ForecastPanel";
import { HazardMap } from "./HazardMap";
import type { MapFocus } from "./mapTypes";
import { ReadinessDrawer, type DispatchState } from "./ReadinessDrawer";
import { TopBar, type Mode, type Tab } from "./TopBar";

const RankingView = dynamic(() => import("@/components/ranking/RankingView"), {
  ssr: false,
  loading: () => <div className="m-4 h-64 animate-pulse rounded-lg bg-panel" />,
});

const WEEK_HALF = 3;
/** Today's calendar date in Alberta as YYYY-MM-DD. */
function albertaToday(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Edmonton" }).format(new Date());
}

function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function errorText(e: unknown): string | null {
  return e ? (e instanceof Error ? e.message : String(e)) : null;
}

const INITIAL_DISPATCH: DispatchState = {
  picking: false,
  hazard: "equipment_failure",
  result: null,
  loading: false,
  error: null,
  activeBase: null,
};

export function CommandCenter() {
  const [tab, setTab] = useState<Tab>("forecast");
  const [where, setWhere] = useState<Where | null>(null);
  const [placeLabel, setPlaceLabel] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ latitude: number; longitude: number } | null>(null);
  const [mode, setMode] = useState<Mode>("week");
  const [today] = useState(albertaToday);
  const [date, setDate] = useState(today);
  const [operator, setOperator] = useState<string | null>(null);
  const [focus, setFocus] = useState<MapFocus | null>(null);
  const [hidden, setHidden] = useState<Set<HazardGroup>>(new Set());
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [dispatch, setDispatch] = useState<DispatchState>(INITIAL_DISPATCH);
  const [crewsOpen, setCrewsOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);

  const start = mode === "week" ? today : addDays(date, -WEEK_HALF);

  const corridorsQ = useQuery({ queryKey: ["corridors"], queryFn: getCorridors, staleTime: Infinity });
  const incidentsQ = useQuery({ queryKey: ["map-incidents"], queryFn: getIncidentPoints, staleTime: Infinity });
  const pipelinesQ = useQuery({ queryKey: ["map-pipelines"], queryFn: getPipelines, staleTime: Infinity });
  const crewsQ = useQuery({ queryKey: ["crews"], queryFn: getCrews });
  const agentQ = useQuery({ queryKey: ["agent-status"], queryFn: getAgentStatus, staleTime: 60_000 });
  const washoutQ = useQuery({ queryKey: ["washout"], queryFn: getWashout, staleTime: Infinity });
  const decisionsQ = useQuery({ queryKey: ["decisions"], queryFn: getDecisions, enabled: tab === "decisions" });
  const readinessQ = useQuery({
    queryKey: ["readiness", where, start, operator],
    queryFn: () => getReadiness(where!, start, operator),
    enabled: !!where,
    placeholderData: keepPreviousData,
  });

  const briefing = useMutation({
    mutationFn: () => getBriefing(where!, start, operator),
    onSettled: () => void logAgentUsage("AI usage after briefing"),
  });

  // Dev-console usage counter (budget guard), once per page load.
  useEffect(() => {
    void logAgentUsage();
  }, []);

  const readiness = readinessQ.data ?? null;
  const forecast = readiness?.forecast ?? null;
  const backendDown = corridorsQ.error && incidentsQ.error;

  const weekLabel = readiness
    ? mode === "week"
      ? `Next 7 days · ${readiness.week.start} → ${readiness.week.end} (forecast for ${readiness.week.forecast_date})`
      : `Forecast for ${readiness.week.forecast_date}`
    : null;

  function pickArea(where: Where, label: string, at: { latitude: number; longitude: number }) {
    setWhere(where);
    setPlaceLabel(label);
    setSelected(at);
    setOperator(null);
    briefing.reset();
  }

  function onSearch(c: Corridor) {
    pickArea({ corridor: c.name }, c.name, { latitude: c.latitude, longitude: c.longitude });
    setFocus({ latitude: c.latitude, longitude: c.longitude, zoom: 8, key: Date.now() });
  }

  async function runDispatch(latitude: number, longitude: number, hazard: HazardGroup) {
    setDispatch((d) => ({ ...d, picking: false, loading: true, error: null, result: null }));
    setDrawerOpen(true);
    try {
      const result = await dispatchRoute(latitude, longitude, hazard, 3);
      setDispatch((d) => ({ ...d, loading: false, result, activeBase: result.bases[0]?.base_id ?? null }));
    } catch (e) {
      setDispatch((d) => ({ ...d, loading: false, error: errorText(e) }));
    }
  }

  function onPick(latitude: number, longitude: number) {
    if (dispatch.picking) {
      setSelected({ latitude, longitude });
      void runDispatch(latitude, longitude, dispatch.hazard);
      return;
    }
    pickArea({ latitude, longitude }, `${latitude.toFixed(3)}, ${longitude.toFixed(3)}`, { latitude, longitude });
  }

  function onFocusIncident(s: SimilarIncident) {
    setFocus({ latitude: s.latitude, longitude: s.longitude, zoom: 9, key: Date.now() });
  }

  const similar = useMemo(() => readiness?.similar.incidents ?? [], [readiness]);

  return (
    <div className="flex min-h-dvh flex-col">
      <TopBar
        tab={tab}
        onTab={setTab}
        corridors={corridorsQ.data ?? []}
        onSearch={onSearch}
        mode={mode}
        onMode={setMode}
        date={date}
        onDate={setDate}
      />
      {backendDown && (
        <div role="alert" className="border-b border-critical/50 bg-critical/10 px-4 py-1.5 text-[12px]">
          Backend unreachable — start the API (uvicorn api.main:app) and the database (docker compose up -d).
        </div>
      )}
      <main className="flex flex-1 flex-col">
        {tab === "forecast" && (
          <>
            <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_400px]">
              {/* Map stays large. On wide screens it fills the viewport under the pinned top
                  bar and stays in view while the forecast column scrolls beside it. */}
              <div className="relative h-[clamp(360px,65vh,820px)] xl:sticky xl:top-14 xl:h-[calc(100dvh-3.5rem)]">
                <HazardMap
                  incidents={incidentsQ.data ?? null}
                  pipelines={pipelinesQ.data ?? null}
                  bases={crewsQ.data?.bases ?? []}
                  selected={selected}
                  similar={similar}
                  routes={dispatch.result?.bases ?? null}
                  activeRouteId={dispatch.activeBase}
                  focus={focus}
                  pickMode={dispatch.picking ? "dispatch" : "forecast"}
                  hiddenHazards={hidden}
                  onPick={onPick}
                  onToggleHazard={(g) =>
                    setHidden((s) => {
                      const next = new Set(s);
                      if (next.has(g)) next.delete(g);
                      else next.add(g);
                      return next;
                    })
                  }
                />
              </div>
              <aside className="flex min-w-0 flex-col gap-5 border-t border-border bg-panel p-4 xl:border-l xl:border-t-0">
                <ForecastPanel
                  forecast={forecast}
                  loading={readinessQ.isFetching}
                  error={errorText(readinessQ.error)}
                  placeLabel={placeLabel}
                  weekLabel={weekLabel}
                  onOperatorChange={setOperator}
                  onAbout={() => setAboutOpen(true)}
                />
                <EvidencePanel
                  incidents={readiness ? similar : null}
                  referenceDate={readiness?.similar.reference_date ?? null}
                  loading={readinessQ.isFetching}
                  onFocus={onFocusIncident}
                />
              </aside>
            </div>
            <ReadinessDrawer
              readiness={readiness}
              loading={readinessQ.isFetching}
              open={drawerOpen}
              onToggle={() => setDrawerOpen(!drawerOpen)}
              onEditCrews={() => setCrewsOpen(true)}
              dispatch={dispatch}
              onDispatchStart={() =>
                setDispatch((d) => ({
                  ...d,
                  picking: true,
                  error: null,
                  hazard: forecast?.hazards[0]?.hazard_group ?? d.hazard,
                }))
              }
              onDispatchCancel={() => setDispatch((d) => ({ ...d, picking: false }))}
              onDispatchHazard={(h) => {
                setDispatch((d) => ({ ...d, hazard: h }));
                if (dispatch.result) void runDispatch(dispatch.result.incident.latitude, dispatch.result.incident.longitude, h);
              }}
              onDispatchSelectBase={(id) => setDispatch((d) => ({ ...d, activeBase: id }))}
              agent={agentQ.data ?? null}
              briefing={briefing.data ?? (briefing.error ? { answer: errorText(briefing.error) ?? "", error: true } : null)}
              briefingLoading={briefing.isPending}
              onBriefing={() => briefing.mutate()}
              washout={washoutQ.data ?? null}
            />
          </>
        )}
        {tab === "ranking" && (
          <div className="flex-1">
            <RankingView />
          </div>
        )}
        {tab === "decisions" && (
          <div className="flex-1 p-4">
            <div className="mx-auto max-w-4xl rounded-lg border border-border bg-panel p-4 text-fg">
              {decisionsQ.error ? (
                <PanelMessage tone="error" text={errorText(decisionsQ.error) ?? ""} />
              ) : (
                <DecisionLog decisions={decisionsQ.data ?? []} />
              )}
            </div>
          </div>
        )}
      </main>
      <Footer />
      <CrewEditorModal open={crewsOpen} onClose={() => setCrewsOpen(false)} />
      <AboutModelModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </div>
  );
}
