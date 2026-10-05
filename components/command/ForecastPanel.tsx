"use client";

import { useState } from "react";
import { HAZARD_SHORT, hazardColor } from "@/lib/hazards";
import type { Forecast, ForecastHazard } from "@/lib/forecastTypes";

type Props = {
  forecast: Forecast | null;
  loading: boolean;
  error: string | null;
  placeLabel: string | null;
  weekLabel: string | null;
  onOperatorChange: (operator: string) => void;
  onAbout: () => void;
};

const SKELETON_ROWS = 8;

export function ForecastPanel({
  forecast,
  loading,
  error,
  placeLabel,
  weekLabel,
  onOperatorChange,
  onAbout,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <section aria-labelledby="forecast-h" className="flex shrink-0 flex-col">
      <header className="mb-2 flex items-baseline justify-between gap-2">
        <h2 id="forecast-h" className="text-[13px] font-semibold uppercase tracking-[0.08em] text-muted">
          <button type="button" aria-expanded={!collapsed} onClick={() => setCollapsed((v) => !v)}
            className="uppercase tracking-[0.08em] hover:text-fg">
            <span aria-hidden className="mr-1">{collapsed ? "▸" : "▾"}</span>Hazard forecast
          </button>
        </h2>
        <button type="button" onClick={onAbout} className="text-[12px] text-accent hover:underline">
          About this model
        </button>
      </header>
      {collapsed ? null : error ? (
        <PanelMessage tone="error" text={error} />
      ) : !forecast && !loading ? (
        <PanelMessage text="Click the map or search an area to forecast the likely mix of hazard types." />
      ) : !forecast ? (
        <Skeleton />
      ) : (
        <ForecastBody
          forecast={forecast}
          stale={loading}
          placeLabel={placeLabel}
          weekLabel={weekLabel}
          onOperatorChange={onOperatorChange}
        />
      )}
    </section>
  );
}

function ForecastBody({
  forecast,
  stale,
  placeLabel,
  weekLabel,
  onOperatorChange,
}: {
  forecast: Forecast;
  stale: boolean;
  placeLabel: string | null;
  weekLabel: string | null;
  onOperatorChange: (operator: string) => void;
}) {
  const ctx = forecast.context;
  const top = forecast.hazards[0]?.probability ?? 0;
  const scaleMax = top > 0.5 ? 1 : 0.5;
  const ev = forecast.evidence;
  return (
    <div className={`flex flex-col gap-3 transition-opacity ${stale ? "opacity-60" : ""}`} aria-busy={stale}>
      <div className="text-[12px] text-muted">
        <div className="text-[14px] font-semibold text-fg">{placeLabel ?? "Selected point"}</div>
        <div>{weekLabel ?? forecast.date}</div>
        <label className="mt-1 flex flex-wrap items-center gap-1.5">
          <span>Operator</span>
          <select
            className="rounded border border-border bg-panel-2 px-1.5 py-0.5 text-[12px] text-fg"
            value={ctx.operator_group ?? ""}
            onChange={(e) => onOperatorChange(e.target.value)}
          >
            {ctx.operator_options.map((o) => (
              <option key={o.operator_group} value={o.operator_group}>
                {o.operator_group} · {o.commodity}
              </option>
            ))}
          </select>
          <span className="basis-full text-[11px]">({ctx.operator_source})</span>
        </label>
      </div>

      {forecast.low_evidence && (
        <div role="status" className="rounded-md border border-warn/60 bg-warn/10 px-2.5 py-1.5 text-[12px] text-fg">
          <span className="font-semibold text-warn">Low evidence base</span> — {forecast.low_evidence_rule}.
          Treat this mix as indicative.
        </div>
      )}

      <ol className="grid gap-1.5" aria-label="Hazard probabilities, highest first">
        {forecast.hazards.map((h, i) => (
          <HazardBar key={h.hazard_group} h={h} scaleMax={scaleMax} rank={i} />
        ))}
      </ol>
      <p className="text-[11px] text-muted">
        Bar scale 0–{Math.round(scaleMax * 100)}%. Above 50% is shown as “&gt;50%, lower certainty”
        (the model was overconfident there on held-out data).
      </p>

      <p className="text-[12px] text-muted">
        Evidence: <span className="text-fg">{ev.prior_incidents}</span> earlier incidents at{" "}
        <span className="text-fg">{ev.prior_sites}</span> sites within {ev.radius_km} km (
        {ev.prior_with_known_cause} with a known cause by then). Weather is not a model input.
      </p>
    </div>
  );
}

function HazardBar({ h, scaleMax, rank }: { h: ForecastHazard; scaleMax: number; rank: number }) {
  const [open, setOpen] = useState(false);
  const width = Math.min(1, h.probability / scaleMax) * 100;
  const tip =
    `${h.label}: ${h.display}` +
    (h.alberta_share != null ? ` · Alberta historical share ${(h.alberta_share * 100).toFixed(1)}%` : "") +
    (h.low_evidence_group ? " · low-evidence hazard group" : "");
  return (
    <li>
      <button
        type="button"
        className="group w-full rounded px-1 py-0.5 text-left hover:bg-panel-2 disabled:cursor-default"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={h.drivers.length ? open : undefined}
        disabled={!h.drivers.length}
        title={tip}
      >
        <div className="flex items-baseline justify-between gap-2 text-[12px]">
          <span className="truncate text-fg" title={h.label}>
            {HAZARD_SHORT[h.hazard_group] ?? h.label}
            {h.low_evidence_group && <span className="ml-1 text-[11px] text-warn">· low evidence</span>}
          </span>
          <span className="shrink-0 font-mono text-fg">
            {h.lower_certainty ? ">50%" : h.display}
            {h.vs_alberta != null && rank < 3 && (
              <span className="ml-1.5 text-[11px] text-muted">
                {/* A precise ratio would reveal the capped probability. */}
                {h.lower_certainty ? "above AB avg" : `${h.vs_alberta}× AB avg`}
              </span>
            )}
          </span>
        </div>
        <div className="mt-0.5 h-2 w-full rounded-sm bg-panel-2">
          <div
            className={`h-2 rounded-sm ${h.lower_certainty ? "bg-[repeating-linear-gradient(135deg,var(--c)_0_4px,transparent_4px_7px)]" : ""}`}
            style={
              {
                width: `${width}%`,
                background: h.lower_certainty ? undefined : hazardColor(h.hazard_group),
                "--c": hazardColor(h.hazard_group),
              } as React.CSSProperties
            }
          />
        </div>
        {h.lower_certainty && (
          <div className="mt-0.5 text-[11px] text-warn">
            Lower certainty — the model was overconfident above 50% on held-out data
          </div>
        )}
      </button>
      {open && h.drivers.length > 0 && (
        <ul className="mb-1 ml-2 mt-1 grid gap-0.5 border-l border-border pl-2 text-[11px] text-muted">
          {h.drivers.map((d) => (
            <li key={d.feature}>
              <span className={d.effect === "raises" ? "text-fg" : ""}>
                {d.effect === "raises" ? "▲ raises" : "▼ lowers"}
              </span>{" "}
              · {d.text}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

function Skeleton() {
  return (
    <div className="grid gap-3" aria-label="Loading forecast" aria-busy>
      <div className="h-10 animate-pulse rounded bg-panel-2" />
      {Array.from({ length: SKELETON_ROWS }, (_, i) => (
        <div key={i} className="grid gap-1">
          <div className="h-3 w-2/3 animate-pulse rounded bg-panel-2" />
          <div className="h-2 animate-pulse rounded bg-panel-2" />
        </div>
      ))}
    </div>
  );
}

export function PanelMessage({ text, tone = "muted" }: { text: string; tone?: "muted" | "error" }) {
  return (
    <p
      role={tone === "error" ? "alert" : undefined}
      className={`rounded-md border px-3 py-2 text-[12px] ${tone === "error" ? "border-critical/60 bg-critical/10 text-fg" : "border-border text-muted"}`}
    >
      {text}
    </p>
  );
}
