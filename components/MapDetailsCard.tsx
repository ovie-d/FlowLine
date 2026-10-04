"use client";

import type { CorridorDetail, RankingRow } from "@/lib/types";
import { formatDate, sevColor } from "@/lib/format";

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

const AB_POLYGON =
  "0.00,0.00 100.00,0.00 100.00,100.00 59.40,100.00 53.00,90.91 46.00,83.64 37.00,77.27 27.00,70.91 17.00,64.55 8.00,59.09 0.00,55.45";

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
      className="rounded-xl border border-[#E3E3DE] bg-white"
      style={{ flex: "0 0 320px", maxWidth: 320, padding: 14 }}
    >
      <div
        role="tablist"
        aria-label="Map and corridor details"
        className="mb-3 flex gap-1 rounded-lg bg-[#F2F2EE] p-[3px]"
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

      {tab === "map" ? (
        <CorridorMap
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
        background: selected ? "#FFFFFF" : "transparent",
        color: selected ? "#15171A" : "#5A5F66",
        boxShadow: selected ? "0 1px 2px rgba(0,0,0,0.08)" : undefined,
        border: "none",
        minHeight: 32,
      }}
    >
      {label}
    </button>
  );
}

function CorridorMap({
  ranking,
  selected,
  onSelect,
}: {
  ranking: RankingRow[];
  selected: string | null;
  onSelect: (corridor: string) => void;
}) {
  const maxScore = ranking[0]?.score || 1;
  const withCoords = ranking.filter(
    (r) =>
      r.lat != null &&
      r.lon != null &&
      Number.isFinite(r.lat) &&
      Number.isFinite(r.lon),
  );
  // Draw lower ranks first so top ranks sit on top
  const dots = [...withCoords].reverse();

  return (
    <div>
      <div
        className="relative w-full rounded-lg bg-[#FAFAF8]"
        style={{ aspectRatio: "10 / 15" }}
      >
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="absolute inset-0 h-full w-full"
          aria-hidden
        >
          <polygon
            points={AB_POLYGON}
            fill="#EFEFEB"
            stroke="#BDBDB6"
            strokeWidth="0.4"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        <div
          className="absolute left-2.5 top-2.5 text-[11px] uppercase tracking-[0.1em] text-[#6B6F75]"
        >
          Alberta
        </div>
        {dots.map((row) => {
          const size = Math.round(14 + (26 * row.score) / maxScore);
          const left = (((row.lon as number) + 120) / 10) * 100;
          const top = ((60 - (row.lat as number)) / 11) * 100;
          const isSel = selected === row.corridor;
          return (
            <button
              key={row.corridor}
              type="button"
              aria-label={`${row.corridor}, rank ${row.rank}`}
              onClick={() => onSelect(row.corridor)}
              className="absolute p-0 font-mono text-[11px] font-semibold text-white"
              style={{
                left: `${left.toFixed(2)}%`,
                top: `${top.toFixed(2)}%`,
                width: size,
                height: size,
                transform: "translate(-50%, -50%)",
                borderRadius: "50%",
                border: "2px solid #FFFFFF",
                background: sevColor(row.n_high),
                boxShadow: isSel
                  ? "0 0 0 3px #1D4ED8"
                  : "0 1px 3px rgba(0,0,0,0.25)",
                cursor: "pointer",
              }}
            >
              {row.rank <= 5 ? row.rank : ""}
            </button>
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap gap-3.5 text-[12px] text-[#5A5F66]">
        <LegendDot color="#A8370A" label="3+ serious" />
        <LegendDot color="#E0904A" label="1–2 serious" />
        <LegendDot color="#9C9FA5" label="minor only" />
      </div>
      {withCoords.length === 0 && (
        <p className="mt-2 text-[12px] text-[#5A5F66]">
          No lat/lon on ranked corridors yet.
        </p>
      )}
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block rounded-full"
        style={{ width: 10, height: 10, background: color }}
      />
      {label}
    </span>
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
      <p className="text-[13px] text-[#5A5F66]">
        Select a corridor to see details.
      </p>
    );
  }
  if (loading && !detail) {
    return <p className="text-[13px] text-[#5A5F66]">Loading…</p>;
  }
  if (!detail) {
    return (
      <p className="text-[13px] text-[#5A5F66]">
        No detail available for {selected}.
      </p>
    );
  }

  const total = detail.n_high + detail.n_medium + detail.n_low || 1;
  const cons =
    detail.n > 0 ? (detail.score / detail.n).toFixed(2) : detail.consequence?.toFixed?.(2) ?? "—";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <div className="font-display text-[28px] leading-[1.1] text-[#15171A]">
          {detail.corridor}
        </div>
        <div className="font-mono text-[13px] text-[#5A5F66]">
          #{detail.rank} · {detail.score.toFixed(1)}
        </div>
      </div>

      {detail.confidence === "low" && (
        <div className="rounded-lg bg-[#FDEEE3] px-2.5 py-2 text-[13px] text-[#8A2E08]">
          <b>High risk, low evidence base.</b> Only {detail.n} incidents on
          record.
        </div>
      )}

      <div className="grid grid-cols-2 gap-2.5">
        <div className="rounded-lg bg-[#F7F7F4] px-3 py-2.5">
          <div className="text-[12px] text-[#5A5F66]">Likelihood</div>
          <div className="font-mono text-[20px] font-semibold">{detail.n}</div>
          <div className="text-[12px] text-[#5A5F66]">incidents</div>
        </div>
        <div className="rounded-lg bg-[#F7F7F4] px-3 py-2.5">
          <div className="text-[12px] text-[#5A5F66]">Consequence</div>
          <div className="font-mono text-[20px] font-semibold">{cons}</div>
          <div className="text-[12px] text-[#5A5F66]">average weight</div>
        </div>
      </div>

      <div className="flex h-2 overflow-hidden rounded bg-[#EFEFEB]">
        <span
          className="block bg-[#A8370A]"
          style={{ width: `${(detail.n_high / total) * 100}%` }}
        />
        <span
          className="block bg-[#E0904A]"
          style={{ width: `${(detail.n_medium / total) * 100}%` }}
        />
        <span
          className="block bg-[#C6C6C0]"
          style={{ width: `${(detail.n_low / total) * 100}%` }}
        />
      </div>
      <div className="text-[13px] text-[#3A3E44]">
        {detail.n_high} high · {detail.n_medium} medium · {detail.n_low} low
        consequence
      </div>

      <div className="rounded-lg bg-[#F7F7F4] px-3 py-2.5 font-mono text-[12px] leading-[1.55] text-[#2A2D31]">
        {detail.score_explanation}
      </div>

      {detail.operators?.length > 0 && (
        <div className="text-[13px] text-[#3A3E44]">
          <span className="text-[#5A5F66]">Operators:</span>{" "}
          {detail.operators.map((o) => `${o.company} (${o.n})`).join(" · ")}
        </div>
      )}

      <div className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[#5A5F66]">
        Top drivers
      </div>
      <ul>
        {(detail.drivers ?? []).slice(0, 5).map((d, i) => (
          <li
            key={`${d}-${i}`}
            className="flex justify-between gap-2 border-t border-[#EFEFEB] pt-2 text-[13px]"
          >
            <span>{typeof d === "string" ? d : String(d)}</span>
            <SeverityChip nHigh={detail.n_high} />
          </li>
        ))}
      </ul>

      <div className="text-[12px] text-[#5A5F66]">
        Last incident {formatDate(detail.last_incident)}
      </div>
    </div>
  );
}

function SeverityChip({ nHigh }: { nHigh: number }) {
  const sev = nHigh >= 1 ? (nHigh >= 3 ? "high" : "medium") : "low";
  const style =
    sev === "high"
      ? { background: "#A8370A", color: "#FFFFFF" }
      : sev === "medium"
        ? { background: "#FCE6D4", color: "#8A2E08" }
        : { background: "#EFEFEB", color: "#3A3E44" };
  return (
    <span
      className="rounded px-1.5 py-0.5 text-[11px] font-semibold"
      style={style}
    >
      {sev}
    </span>
  );
}
