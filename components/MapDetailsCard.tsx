"use client";

import type { CorridorDetail, RankingRow } from "@/lib/types";
import {
  driverSeverity,
  formatDate,
  formatDriverLabel,
} from "@/lib/format";
import { CorridorMapView } from "@/components/map/CorridorMapView";

type Tab = "map" | "details";

type Props = {
  tab: Tab;
  onTabChange: (tab: Tab) => void;
  selected: string | null;
  ranking: RankingRow[];
  detail: CorridorDetail | undefined;
  detailLoading: boolean;
  onSelect: (corridor: string) => void;
};

export function MapDetailsCard({
  tab,
  onTabChange,
  selected,
  ranking,
  detail,
  detailLoading,
  onSelect,
}: Props) {
  const detailsLabel = selected ?? "Details";

  return (
    <section
      className="flex min-h-0 flex-col rounded-xl border border-border bg-panel"
      style={{
        flex: "0 0 320px",
        width: 320,
        maxWidth: 320,
        minHeight: 0,
        height: "100%",
        padding: 14,
        boxSizing: "border-box",
        overflow: "hidden",
      }}
    >
      <div
        role="tablist"
        aria-label="Map and corridor details"
        className="mb-3 flex gap-1 rounded-lg bg-panel-2 p-[3px]"
        style={{ flex: "0 0 auto" }}
      >
        <TabButton
          selected={tab === "map"}
          onClick={() => onTabChange("map")}
          label="Map"
        />
        <TabButton
          selected={tab === "details"}
          onClick={() => onTabChange("details")}
          label={detailsLabel}
        />
      </div>

      <div
        className="min-h-0"
        style={{ flex: "1 1 auto", minHeight: 0, overflowY: "auto" }}
      >
        {tab === "map" ? (
          <CorridorMapView
            ranking={ranking}
            selected={selected}
            onSelect={onSelect}
          />
        ) : (
          <CorridorDetails
            detail={detail}
            loading={detailLoading}
            selected={selected}
          />
        )}
      </div>
    </section>
  );
}

function TabButton({
  selected,
  onClick,
  label,
}: {
  selected: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={selected}
      onClick={onClick}
      className="min-h-8 flex-1 overflow-hidden text-ellipsis whitespace-nowrap rounded-md px-2 text-[13px] font-semibold"
      style={{
        background: selected ? "var(--panel)" : "transparent",
        color: selected ? "var(--text)" : "var(--muted)",
        boxShadow: selected ? "0 1px 2px rgba(0,0,0,0.08)" : undefined,
        border: "none",
        minHeight: 32,
      }}
    >
      {label}
    </button>
  );
}

function CorridorDetails({
  detail,
  loading,
  selected,
}: {
  detail: CorridorDetail | undefined;
  loading: boolean;
  selected: string | null;
}) {
  if (!selected) {
    return (
      <p className="text-[13px] text-muted">
        Select a corridor to see details.
      </p>
    );
  }
  if (loading && !detail) {
    return <p className="text-[13px] text-muted">Loading…</p>;
  }
  if (!detail) {
    return (
      <p className="text-[13px] text-muted">
        No detail available for {selected}.
      </p>
    );
  }

  const total = detail.n_high + detail.n_medium + detail.n_low || 1;
  const cons =
    detail.n > 0
      ? (detail.score / detail.n).toFixed(2)
      : (detail.consequence?.toFixed?.(2) ?? "—");

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <div className="font-display text-[28px] leading-[1.1] text-fg">
          {detail.corridor}
        </div>
        <div className="font-mono text-[13px] text-muted">
          #{detail.rank} · {detail.score.toFixed(1)}
        </div>
      </div>

      {detail.confidence === "low" && (
        <div className="rounded-lg bg-thin-bg px-2.5 py-2 text-[13px] text-warn">
          <b>High risk, low evidence base.</b> Only {detail.n} incidents on
          record.
        </div>
      )}

      <div className="grid grid-cols-2 gap-2.5">
        <div className="rounded-lg bg-panel-2 px-3 py-2.5">
          <div className="text-[12px] text-muted">Likelihood</div>
          <div className="font-mono text-[20px] font-semibold">{detail.n}</div>
          <div className="text-[12px] text-muted">incidents</div>
        </div>
        <div className="rounded-lg bg-panel-2 px-3 py-2.5">
          <div className="text-[12px] text-muted">Consequence</div>
          <div className="font-mono text-[20px] font-semibold">{cons}</div>
          <div className="text-[12px] text-muted">average weight</div>
        </div>
      </div>

      <div className="flex h-2 overflow-hidden rounded bg-border">
        <span
          className="block bg-critical"
          style={{ width: `${(detail.n_high / total) * 100}%` }}
        />
        <span
          className="block bg-warn"
          style={{ width: `${(detail.n_medium / total) * 100}%` }}
        />
        <span
          className="block bg-border"
          style={{ width: `${(detail.n_low / total) * 100}%` }}
        />
      </div>
      <div className="text-[13px] text-fg">
        {detail.n_high} high · {detail.n_medium} medium · {detail.n_low} low
        consequence
      </div>

      <div className="rounded-lg bg-panel-2 px-3 py-2.5 font-mono text-[12px] leading-[1.55] text-fg">
        {detail.score_explanation}
      </div>

      {detail.operators?.length > 0 && (
        <div className="text-[13px] text-fg">
          <span className="text-muted">Operators:</span>{" "}
          {detail.operators.map((o) => `${o.company} (${o.n})`).join(" · ")}
        </div>
      )}

      <div className="text-[12px] font-semibold uppercase tracking-[0.08em] text-muted">
        Top drivers
      </div>
      <ul>
        {(detail.drivers ?? []).slice(0, 5).map((d, i) => {
          const sev = driverSeverity(d.weight);
          return (
            <li
              key={`${d.type ?? "d"}-${d.date ?? i}-${i}`}
              className="flex justify-between gap-2 border-t border-border pt-2 text-[13px]"
            >
              <span>{formatDriverLabel(d)}</span>
              <DriverSeverityChip sev={sev} />
            </li>
          );
        })}
      </ul>

      <div className="text-[12px] text-muted">
        Last incident {formatDate(detail.last_incident)}
      </div>
    </div>
  );
}

function DriverSeverityChip({ sev }: { sev: "high" | "medium" | "low" }) {
  const style =
    sev === "high"
      ? { background: "var(--critical)", color: "var(--panel)" }
      : sev === "medium"
        ? { background: "var(--thin-bg)", color: "var(--warn)" }
        : { background: "var(--border)", color: "var(--text)" };
  return (
    <span
      className="rounded px-1.5 py-0.5 text-[11px] font-semibold"
      style={style}
    >
      {sev}
    </span>
  );
}
