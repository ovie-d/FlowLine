"use client";

import { hazardColor } from "@/lib/hazards";
import type { AgentStatus, BriefingResult, Readiness, WashoutInsight } from "@/lib/forecastTypes";
import { SampleChip } from "@/components/ui/Badges";
import { InfoTip } from "@/components/ui/InfoTip";
import { formatMinutes as minutes } from "@/lib/routeSim";
import { PanelMessage } from "./ForecastPanel";

type Props = {
  readiness: Readiness | null;
  loading: boolean;
  open: boolean;
  onToggle: () => void;
  onEditCrews: () => void;
  onDispatch: () => void;
  agent: AgentStatus | null;
  briefing: BriefingResult | null;
  briefingLoading: boolean;
  onBriefing: () => void;
  washout: WashoutInsight | null;
};

function Card({ title, children, aside }: { title: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-border bg-panel p-3">
      <header className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-[12px] font-semibold uppercase tracking-[0.08em] text-muted">{title}</h3>
        {aside}
      </header>
      <div>{children}</div>
    </section>
  );
}

export function ReadinessDrawer(p: Props) {
  return (
    <section
      aria-label="Readiness and dispatch"
      className="border-t border-border bg-bg"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2">
        <button type="button" onClick={p.onToggle} aria-expanded={p.open}
          className="text-[13px] font-semibold uppercase tracking-[0.08em] text-muted hover:text-fg">
          {p.open ? "▾" : "▴"} Readiness &amp; dispatch
          {p.readiness && (
            <span className="ml-2 normal-case tracking-normal text-[12px] font-normal">
              week {p.readiness.week.start} → {p.readiness.week.end}
            </span>
          )}
        </button>
        <div className="flex items-center gap-2">
          <button type="button" onClick={p.onEditCrews}
            className="rounded border border-border px-2.5 py-1 text-[12px] text-fg hover:border-accent">
            Edit crew table
          </button>
          <button type="button" onClick={p.onDispatch}
            title="Open the Emergency Dispatch page for the selected point"
            className="rounded bg-critical-strong px-2.5 py-1 text-[12px] font-semibold text-white hover:brightness-110">
            Emergency dispatch →
          </button>
        </div>
      </div>
      {p.open && (
        <div className="grid grid-cols-1 items-start gap-3 px-4 pb-4 md:grid-cols-2 2xl:grid-cols-3">
          <CrewsCard readiness={p.readiness} loading={p.loading} />
          <WeatherCard readiness={p.readiness} loading={p.loading} washout={p.washout} />
          <BriefingCard agent={p.agent} briefing={p.briefing} loading={p.briefingLoading}
            onBriefing={p.onBriefing} canBrief={!!p.readiness} />
        </div>
      )}
    </section>
  );
}

function CrewsCard({ readiness, loading }: { readiness: Readiness | null; loading: boolean }) {
  return (
    <Card title="Recommended crews" aside={<SampleChip />}>
      {!readiness ? (
        loading ? <div className="h-full animate-pulse rounded bg-panel-2" /> :
          <PanelMessage text="Forecast an area to see which crews to have ready." />
      ) : (
        <ul className="grid gap-2 text-[12px]">
          {readiness.recommended.map((h) => (
            <li key={h.hazard_group}>
              <div className="flex items-center gap-1.5 font-semibold text-fg">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: hazardColor(h.hazard_group) }} />
                {h.label}{" "}
                <InfoTip tip="Forecast probability of this hazard type if an incident happens here (same number as the forecast panel).">
                  <span className="font-mono font-normal text-muted">{h.display}</span>
                </InfoTip>
              </div>
              <ul className="ml-4 mt-0.5 grid gap-0.5 text-muted">
                {h.crews.length === 0 && <li>No crew mapped — edit the crew table.</li>}
                {h.crews.map((c) => (
                  <li key={c.crew_type_id}>
                    <span className="text-fg">{c.crew_name}</span>
                    {c.nearest_base ? (
                      <> · {c.nearest_base.base_name},{" "}
                        <InfoTip tip="Drive time from the nearest sample base holding this crew, from the road router (no traffic).">
                          <span>{minutes(c.nearest_base.duration_min)}</span>
                        </InfoTip>
                        {c.nearest_base.warning && " (straight-line distance only)"}</>
                    ) : " · no base holds this crew"}
                    <div className="text-[11px]">{c.equipment.join(", ")}</div>
                  </li>
                ))}
              </ul>
            </li>
          ))}
          <li className="text-[11px] text-muted">Rule: {readiness.recommend_rule}.</li>
        </ul>
      )}
    </Card>
  );
}

function WeatherCard({ readiness, loading, washout }: {
  readiness: Readiness | null; loading: boolean; washout: WashoutInsight | null;
}) {
  const w = readiness?.weather;
  return (
    <Card title="Weather context" aside={
      <InfoTip tip="Adding weather made no measurable difference to the forecast on held-out data, so it was removed from the model. Shown here for planning context only." align="end">
        <span className="text-[10px] text-muted">not a model input</span>
      </InfoTip>
    }>
      {loading && !readiness ? <div className="h-24 animate-pulse rounded bg-panel-2" /> : w ? (
        <div className="grid gap-1.5 text-[12px]">
          <div className="text-fg">
            Next 7 days: {w.outlook.min_temp}°C to {w.outlook.max_temp}°C · {w.outlook.precip_total_mm} mm
            precip · {w.outlook.snowfall_total_cm} cm snow
          </div>
          <div className="text-muted">
            Past 30 days: {w.prior_30_days.precip_mm ?? "—"} mm precip · {w.prior_30_days.freeze_thaw_days ?? "—"}{" "}
            freeze–thaw days
          </div>
          <div className="text-[11px] text-muted">Source: {w.source}</div>
        </div>
      ) : readiness ? (
        <PanelMessage text={readiness.weather_note ?? "Weather unavailable."} />
      ) : (
        <PanelMessage text="Weather outlook appears with a forecast." />
      )}
      {washout?.headline && <WashoutCard insight={washout} />}
    </Card>
  );
}

function WashoutCard({ insight }: { insight: WashoutInsight }) {
  const b = insight.before;
  const a = insight.after;
  return (
    <aside className="mt-3 rounded-md border border-border bg-panel-2/50 p-2 text-[11px]" aria-label="Observed pattern">
      <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-safe">Observed pattern · not a forecast</div>
      <p className="text-[12px] text-fg">{insight.headline}</p>
      <p className="mt-1 text-muted">
        Samples: {b.geotechnical} of {b.incidents} Alberta incidents {b.period}; {a.geotechnical} of {a.incidents}{" "}
        {a.period}. Rain medians use {a.n_geotechnical_with_precip} washout and {a.n_other_with_precip} other
        incidents with station weather.
      </p>
      <p className="mt-1 text-muted">{insight.note}</p>
    </aside>
  );
}

function BriefingCard({ agent, briefing, loading, onBriefing, canBrief }: {
  agent: AgentStatus | null; briefing: BriefingResult | null; loading: boolean;
  onBriefing: () => void; canBrief: boolean;
}) {
  const disabled = !agent?.available || !canBrief || loading;
  const reason = !agent ? "Checking AI availability…" : !agent.available ? agent.reason ?? "AI unavailable"
    : !canBrief ? "Forecast an area first." : undefined;
  return (
    <Card title="Readiness briefing" aside={agent?.available ? (
      <InfoTip tip="AI model that writes the briefing from tool results. Every number it writes is checked against those results." align="end">
        <span className="text-[10px] text-muted">{agent.model}</span>
      </InfoTip>
    ) : null}>
      {briefing && !briefing.error && (
        <p role="status" className={`mb-2 rounded border px-2 py-1 text-[11px] font-semibold ${briefing.numbers_verified ? "border-safe/50 text-safe" : "border-warn/60 text-warn"}`}>
          {briefing.numbers_verified
            ? "✓ Every number matches a tool result."
            : `⚠ Numbers not found in tool results: ${briefing.unsupported_numbers?.join(", ")}. Check before sharing.`}
        </p>
      )}
      <span title={reason} className="inline-block">
        <button type="button" disabled={disabled} onClick={onBriefing}
          aria-describedby={reason ? "brief-reason" : undefined}
          className="rounded bg-accent px-3 py-1 text-[12px] font-semibold text-bg hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40">
          {loading ? "Writing briefing…" : "Generate briefing"}
        </button>
      </span>
      {reason && <p id="brief-reason" className="mt-1.5 text-[11px] text-muted">{reason}</p>}
      {briefing && (
        <div className="mt-2 text-[12px]">
          {briefing.error ? <PanelMessage tone="error" text={briefing.reason ?? briefing.answer} /> : (
            <p className="whitespace-pre-line text-fg">{briefing.answer}</p>
          )}
        </div>
      )}
    </Card>
  );
}
