"use client";

import type { RankingRow, TriageDraft } from "@/lib/types";
import {
  capitalizeAction,
  formatMove,
  moveColor,
  moveDelta,
  sevColor,
} from "@/lib/format";
import { motion } from "framer-motion";

type Props = {
  rows: RankingRow[];
  draftsByCorridor: Map<string, TriageDraft>;
  baselineRank: Map<string, number>;
  selected: string | null;
  expanded: boolean;
  onToggleExpanded: () => void;
  onSelect: (corridor: string) => void;
  high: number;
  collapsedSummary: string;
  thinCount: number;
};

const COL = "36px minmax(0, 2fr) minmax(0, 1fr) 52px 104px";

export function RankedList({
  rows,
  draftsByCorridor,
  baselineRank,
  selected,
  expanded,
  onToggleExpanded,
  onSelect,
  high,
  collapsedSummary,
  thinCount,
}: Props) {
  const visible = expanded ? rows : rows.slice(0, 5);
  const maxScore = rows[0]?.score || 100;

  return (
    <section
      className="flex min-h-0 min-w-0 flex-col rounded-xl border border-border bg-panel"
      style={{ padding: 16, boxSizing: "border-box" }}
    >
      {/* Card header — fixed */}
      <div
        className="mb-2 flex flex-wrap items-baseline justify-between gap-3"
        style={{ flex: "0 0 auto" }}
      >
        <div className="text-[15px] font-semibold text-fg">
          Inspection priority · top 5 of 15
        </div>
        <div className="flex flex-wrap items-center gap-3.5">
          <span className="text-[12px] text-muted">
            Move = change vs count-only rank
          </span>
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL}/ranking.csv?high=${high}`}
            className="inline-flex items-center gap-[5px] rounded-[5px] border border-border bg-panel px-2 text-[12px] font-medium text-fg"
            style={{ minHeight: 26 }}
          >
            <svg width="12" height="12" viewBox="0 0 14 14" aria-hidden>
              <path
                d="M7 2v7M4 6.5L7 9.5 10 6.5M2.5 12h9"
                fill="none"
                stroke="var(--text)"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Export CSV
          </a>
        </div>
      </div>

      <div
        className="flex min-h-0 min-w-0 flex-col"
        style={{ flex: "1 1 auto", minHeight: 0, overflow: "hidden" }}
      >
        {/* Column header — fixed */}
        <div
          className="grid min-w-[600px] gap-3 border-b border-border px-2.5 py-2 text-[12px] text-muted"
          style={{ gridTemplateColumns: COL, flex: "0 0 auto" }}
        >
          <span>#</span>
          <span>Corridor · reason</span>
          <span>Risk score</span>
          <span>Move</span>
          <span>Agent draft</span>
        </div>

        {/* Rows */}
        <div>
          <div className="flex min-w-[600px] flex-col">
            {visible.map((row) => (
              <RankRow
                key={row.corridor}
                row={row}
                draft={draftsByCorridor.get(row.corridor)}
                move={moveDelta(baselineRank.get(row.corridor), row.rank)}
                selected={selected === row.corridor}
                maxScore={maxScore}
                onSelect={() => onSelect(row.corridor)}
              />
            ))}

            {rows.length > 5 && (
              <button
                type="button"
                onClick={onToggleExpanded}
                aria-expanded={expanded}
                className="flex w-full items-center justify-between gap-3 border-b border-panel-2 bg-panel-2 px-2.5 py-3 text-left text-fg"
              >
                <span className="flex flex-wrap items-center gap-2.5">
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 14 14"
                    aria-hidden
                    style={{
                      transition: "transform 0.15s",
                      transform: `rotate(${expanded ? 180 : 0}deg)`,
                    }}
                  >
                    <path
                      d="M3 5l4 4 4-4"
                      fill="none"
                      stroke="var(--text)"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <span className="text-[14px] font-semibold">
                    {expanded ? "Hide ranks 6–15" : "Show ranks 6–15"}
                  </span>
                  <span className="text-[13px] text-muted">
                    {collapsedSummary}
                  </span>
                </span>
                {thinCount > 0 && (
                  <span className="whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] font-semibold text-warn bg-thin-bg">
                    {thinCount} high risk, low evidence base
                  </span>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function RankRow({
  row,
  draft,
  move,
  selected,
  maxScore,
  onSelect,
}: {
  row: RankingRow;
  draft?: TriageDraft;
  move: number | null;
  selected: boolean;
  maxScore: number;
  onSelect: () => void;
}) {
  const thin = row.confidence === "low";
  const width = Math.max(4, Math.round((100 * row.score) / maxScore));
  const bar = sevColor(row.n_high);
  const action = draft?.action?.toLowerCase();
  const actionText = action
    ? `${capitalizeAction(action)}${draft?.priority ? ` · ${draft.priority}` : ""}`
    : "—";

  return (
    <motion.div layout>
      <button
        type="button"
        onClick={onSelect}
        className="grid w-full items-center gap-3 border-b border-panel-2 px-2.5 py-2.5 text-left text-fg"
        style={{
          gridTemplateColumns: COL,
          background: selected ? "var(--panel-2)" : "var(--panel)",
          boxShadow: selected ? "inset 3px 0 0 var(--accent)" : undefined,
        }}
      >
        <span className="font-mono text-[14px] font-semibold">{row.rank}</span>

        <span className="flex min-w-0 flex-col gap-[3px]">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-[15px] font-semibold">{row.corridor}</span>
            {thin && (
              <span className="rounded px-1.5 py-0.5 text-[11px] font-semibold text-warn bg-thin-bg">
                High risk, low evidence base
              </span>
            )}
          </span>
          <span className="text-[12px] leading-[1.4] text-muted">
            {draft?.reason ?? "—"}
          </span>
        </span>

        <span className="flex items-center gap-2">
          <span className="block h-1.5 flex-1 overflow-hidden rounded-[3px] bg-border">
            <span
              className="block h-full"
              style={{ width: `${width}%`, background: bar }}
            />
          </span>
          <span className="w-10 text-right font-mono text-[13px]">
            {row.score.toFixed(1)}
          </span>
        </span>

        <span
          className="font-mono text-[13px] font-semibold"
          style={{ color: moveColor(move) }}
        >
          {formatMove(move)}
        </span>

        <ActionBadge action={action} text={actionText} />
      </button>
    </motion.div>
  );
}

function ActionBadge({
  action,
  text,
}: {
  action?: string;
  text: string;
}) {
  if (!action) {
    return <span className="text-[12px] text-muted">—</span>;
  }
  const style =
    action === "escalate"
      ? { color: "var(--critical)", background: "var(--thin-bg)" }
      : action === "inspect"
        ? { color: "var(--accent)", background: "var(--panel-2)" }
        : { color: "var(--muted)", background: "var(--border)" };
  return (
    <span
      title="Agent draft · P1 = act first · P2 = regular cycle · P3 = monitor. Approve in the agent panel."
      className="inline-block cursor-default text-center text-[11px] font-semibold"
      style={{
        ...style,
        padding: "2px 8px",
        borderRadius: 9999,
        border: "none",
        boxShadow: "none",
        lineHeight: 1.4,
      }}
    >
      {text}
    </span>
  );
}
