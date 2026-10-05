"use client";

import { useState } from "react";
import { FlowlineLogo } from "@/components/brand/FlowlineMark";
import type { Corridor } from "@/lib/forecastTypes";

export type Tab = "forecast" | "ranking" | "decisions";
export type Mode = "week" | "date";

const TABS: { key: Tab; label: string }[] = [
  { key: "forecast", label: "Hazard Forecast" },
  { key: "ranking", label: "Risk Ranking" },
  { key: "decisions", label: "Decision Log" },
];

type Props = {
  tab: Tab;
  onTab: (t: Tab) => void;
  corridors: Corridor[];
  onSearch: (c: Corridor) => void;
  mode: Mode;
  onMode: (m: Mode) => void;
  date: string;
  onDate: (d: string) => void;
};

export function TopBar({ tab, onTab, corridors, onSearch, mode, onMode, date, onDate }: Props) {
  const [query, setQuery] = useState("");
  const [notFound, setNotFound] = useState(false);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim().toLowerCase();
    const hit =
      corridors.find((c) => c.name.toLowerCase() === q) ??
      corridors.find((c) => c.name.toLowerCase().startsWith(q));
    setNotFound(!hit);
    if (hit) {
      onSearch(hit);
      setQuery(hit.name);
    }
  }

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border bg-panel px-4">
      <FlowlineLogo size={26} />
      <nav aria-label="Views" className="flex rounded-md border border-border p-0.5" role="tablist">
        {TABS.map((t) => (
          <button key={t.key} type="button" role="tab" aria-selected={tab === t.key} onClick={() => onTab(t.key)}
            className={`rounded px-3 py-1 text-[13px] ${tab === t.key ? "bg-panel-2 font-semibold text-fg" : "text-muted hover:text-fg"}`}>
            {t.label}
          </button>
        ))}
      </nav>
      {tab === "forecast" && (
        <div className="ml-auto flex items-center gap-3">
          <form onSubmit={submit} className="relative" role="search">
            <label htmlFor="area-search" className="sr-only">Search an area</label>
            <input id="area-search" list="corridor-list" value={query}
              onChange={(e) => { setQuery(e.target.value); setNotFound(false); }}
              placeholder="Search area (e.g. Edson)"
              aria-invalid={notFound}
              className="w-52 rounded-md border border-border bg-panel-2 px-2.5 py-1 text-[13px] text-fg placeholder:text-muted" />
            <datalist id="corridor-list">
              {corridors.map((c) => <option key={c.name} value={c.name} />)}
            </datalist>
            {notFound && <span role="status" className="absolute left-0 top-full mt-0.5 text-[11px] text-warn">No matching area</span>}
          </form>
          <div className="flex items-center rounded-md border border-border p-0.5" role="radiogroup" aria-label="Forecast window">
            <button type="button" role="radio" aria-checked={mode === "week"} onClick={() => onMode("week")}
              className={`rounded px-2.5 py-1 text-[12px] ${mode === "week" ? "bg-panel-2 font-semibold text-fg" : "text-muted"}`}>
              Next 7 days
            </button>
            <button type="button" role="radio" aria-checked={mode === "date"} onClick={() => onMode("date")}
              className={`rounded px-2.5 py-1 text-[12px] ${mode === "date" ? "bg-panel-2 font-semibold text-fg" : "text-muted"}`}>
              Pick date
            </button>
          </div>
          {mode === "date" && (
            <label className="flex items-center gap-1 text-[12px] text-muted">
              <span className="sr-only">Forecast date</span>
              <input type="date" value={date} onChange={(e) => e.target.value && onDate(e.target.value)}
                className="rounded border border-border bg-panel-2 px-1.5 py-0.5 text-fg [color-scheme:dark]" />
            </label>
          )}
        </div>
      )}
    </header>
  );
}
