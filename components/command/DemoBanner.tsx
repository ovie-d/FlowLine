"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getDemoStatus } from "@/lib/forecastApi";

const INSTALL_URL = "https://github.com/ovie-d/FlowLine#try-it-in-2-minutes";
const KEY = "flowline.demoBannerClosed";

/** Online demo notice (hosted website only): AI limit, private sandbox, install link. */
export function DemoBanner() {
  const q = useQuery({ queryKey: ["demo-status"], queryFn: getDemoStatus, staleTime: 5 * 60_000 });
  const [closed, setClosed] = useState(() => {
    try {
      return typeof window !== "undefined" && sessionStorage.getItem(KEY) === "1";
    } catch {
      return false;
    }
  });
  const s = q.data;
  if (!s || !s.demo || closed) return null;
  return (
    <div role="note" className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border bg-panel-2 px-4 py-1.5 text-[12px] text-fg">
      <span className="rounded bg-highlight px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#0B1F3A]">
        Online demo
      </span>
      <span className="min-w-0 flex-1">
        {s.note} Your edits and decisions stay private to your browser for 24 hours.{" "}
        <a href={INSTALL_URL} target="_blank" rel="noreferrer" className="font-semibold underline">
          Install it on your computer
        </a>{" "}
        for unlimited use with your own key.
      </span>
      <button
        type="button"
        aria-label="Hide this notice"
        onClick={() => {
          setClosed(true);
          try {
            sessionStorage.setItem(KEY, "1");
          } catch {
            /* storage blocked: hidden for this page view */
          }
        }}
        className="rounded px-1.5 text-muted hover:text-fg"
      >
        ×
      </button>
    </div>
  );
}
