"use client";

import { MotionConfig, motion } from "framer-motion";
import { useState } from "react";
import { InfoTip } from "@/components/ui/InfoTip";
import { HAZARD_SHORT, hazardColor, type HazardGroup } from "@/lib/hazards";
import type { Forecast, ForecastHazard } from "@/lib/forecastTypes";

type Props = {
  forecast: Forecast | null;
  loading: boolean;
  error: string | null;
  placeLabel: string | null;
  weekLabel: string | null;
  onOperatorChange: (operator: string) => void;
  onAbout: () => void;
  /** Hovering or focusing a hazard bar highlights that hazard's past incidents on the map. */
  onHoverHazard?: (h: HazardGroup | null) => void;
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
  onHoverHazard,
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
          onHoverHazard={onHoverHazard}
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
  onHoverHazard,
}: {
  forecast: Forecast;
  stale: boolean;
  placeLabel: string | null;
  weekLabel: string | null;
  onOperatorChange: (operator: string) => void;
  onHoverHazard?: (h: HazardGroup | null) => void;
}) {
  const ctx = forecast.context;
  const top = forecast.hazards[0]?.probability ?? 0;
  const scaleMax = top > 0.5 ? 1 : 0.5;
  const ev = forecast.evidence;
  return (
    <MotionConfig reducedMotion="user">
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

      <ol className="grid gap-1.5" aria-label="Hazard probabilities, highest first"
        onMouseLeave={() => onHoverHazard?.(null)}>
        {forecast.hazards.map((h, i) => (
          <HazardBar key={`${forecast.date}-${forecast.location.latitude}-${h.hazard_group}`} h={h}
            scaleMax={scaleMax} rank={i} onHover={onHoverHazard} />
        ))}
      </ol>
      <p className="text-[11px] text-muted">
        Bar scale 0–{Math.round(scaleMax * 100)}%. Above 50% is shown as “&gt;50%, lower certainty”
        (the model was overconfident there on held-out data). Hover a bar to see those past
        incidents on the map; click it for the main drivers.
      </p>

      <p className="text-[12px] text-muted">
        Evidence:{" "}
        <InfoTip tip={`CER incidents within ${ev.radius_km} km that happened before the forecast date. Fewer than a handful means the mix leans on the national pattern.`}>
          <span className="text-fg">{ev.prior_incidents}</span>
        </InfoTip>{" "}
        earlier incidents at{" "}
        <InfoTip tip="Distinct locations: repeat reports at the same coordinates count as one site.">
          <span className="text-fg">{ev.prior_sites}</span>
        </InfoTip>{" "}
        sites within {ev.radius_km} km (
        <InfoTip tip="How many of those incidents had a determined cause by the forecast date (open investigations have none yet).">
          <span>{ev.prior_with_known_cause}</span>
        </InfoTip>{" "}
        with a known cause by then). Weather is not a model input.
      </p>
    </div>
    </MotionConfig>
  );
}

function HazardBar({ h, scaleMax, rank, onHover }: {
  h: ForecastHazard; scaleMax: number; rank: number; onHover?: (g: HazardGroup | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const width = Math.min(1, h.probability / scaleMax) * 100;
  const short = HAZARD_SHORT[h.hazard_group] ?? h.label;
  const probTip = h.lower_certainty
    ? "Above 50%. On held-out data the model was overconfident in this range, so the exact value is not shown."
    : `If an incident happens here in this window, the model's chance it is ${short.toLowerCase()}.`;
  const ratioTip = h.alberta_share != null
    ? `Forecast chance divided by this hazard's historical share of Alberta incidents (${(h.alberta_share * 100).toFixed(1)}%).`
    : "Compared with this hazard's historical share of Alberta incidents.";
  return (
    <li onMouseEnter={() => onHover?.(h.hazard_group)}>
      <button
        type="button"
        className="group w-full rounded px-1 py-0.5 text-left hover:bg-panel-2 focus-visible:bg-panel-2 disabled:cursor-default"
        onClick={() => setOpen((v) => !v)}
        onFocus={() => onHover?.(h.hazard_group)}
        onBlur={() => onHover?.(null)}
        aria-expanded={h.drivers.length ? open : undefined}
        aria-disabled={!h.drivers.length}
        aria-label={`${h.label}: ${h.display}${h.vs_alberta != null && !h.lower_certainty ? `, ${h.vs_alberta} times the Alberta average` : ""}${h.low_evidence_group ? ", low-evidence hazard group" : ""}. ${h.drivers.length ? "Show drivers." : ""}`}
      >
        <div className="flex items-baseline justify-between gap-2 text-[12px]">
          <span className="truncate text-fg" title={h.label}>
            {short}
            {h.low_evidence_group && (
              <InfoTip focusable={false} align="start" tip="Few incidents of this type in the training data, so the model has little to learn from. Treat this bar with extra caution.">
                <span className="ml-1 text-[11px] text-warn">· low evidence</span>
              </InfoTip>
            )}
          </span>
          <span className="shrink-0 font-mono text-fg">
            <InfoTip focusable={false} align="end" tip={probTip}>
              <span>{h.lower_certainty ? ">50%" : h.display}</span>
            </InfoTip>
            {h.vs_alberta != null && rank < 3 && (
              <InfoTip focusable={false} align="end" tip={ratioTip}>
                <span className="ml-1.5 text-[11px] text-muted">
                  {/* A precise ratio would reveal the capped probability. */}
                  {h.lower_certainty ? "above AB avg" : `${h.vs_alberta}× AB avg`}
                </span>
              </InfoTip>
            )}
          </span>
        </div>
        <div className="mt-0.5 h-2 w-full overflow-hidden rounded-sm bg-panel-2">
          <motion.div
            className={`h-2 rounded-sm ${h.lower_certainty ? "bg-[repeating-linear-gradient(135deg,var(--c)_0_4px,transparent_4px_7px)]" : ""}`}
            initial={{ width: 0 }}
            animate={{ width: `${width}%` }}
            transition={{ duration: 0.6, delay: rank * 0.05, ease: [0.22, 1, 0.36, 1] }}
            style={
              {
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
        <motion.ul
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-1 ml-2 mt-1 grid gap-0.5 border-l border-border pl-2 text-[11px] text-muted"
        >
          {h.drivers.map((d) => (
            <li key={d.feature}>
              <span className={d.effect === "raises" ? "text-fg" : ""}>
                {d.effect === "raises" ? "▲ raises" : "▼ lowers"}
              </span>{" "}
              · {d.text}
            </li>
          ))}
        </motion.ul>
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
