"use client";

import { useEffect, useState } from "react";

type Props = {
  min: number;
  max: number;
  value: [number, number];
  onChange: (v: [number, number]) => void;
  shown: number;
};

const STEP_MS = 900;

/**
 * Year range for the incident layers (display only: the forecast always uses the
 * full history). Play slides the selected window forward one year at a time.
 */
export function YearSlider({ min, max, value, onChange, shown }: Props) {
  const [playing, setPlaying] = useState(false);
  const [from, to] = value;

  useEffect(() => {
    if (!playing) return;
    const t = window.setInterval(() => {
      if (to >= max) {
        setPlaying(false);
        return;
      }
      onChange([from + 1, to + 1]);
    }, STEP_MS);
    return () => window.clearInterval(t);
  }, [playing, from, to, max, onChange]);

  const full = from === min && to === max;

  function play() {
    if (playing) {
      setPlaying(false);
      return;
    }
    // A full or finished range restarts from the first year, keeping the window width.
    const width = full ? 0 : to - from;
    if (full || to >= max) onChange([min, min + width]);
    setPlaying(true);
  }

  const span = Math.max(1, max - min);
  const left = ((from - min) / span) * 100;
  const right = ((to - min) / span) * 100;

  return (
    <div className="rounded-md border border-border bg-panel/95 px-3 py-2 text-[12px] shadow backdrop-blur">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={play}
          aria-label={playing ? "Pause year animation" : "Play through the years"}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-bg hover:brightness-110"
        >
          {playing ? (
            <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden>
              <rect x="2" y="1.5" width="3" height="9" rx="0.5" />
              <rect x="7" y="1.5" width="3" height="9" rx="0.5" />
            </svg>
          ) : (
            <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden>
              <path d="M3 1.5v9l7.5-4.5z" />
            </svg>
          )}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2">
            <span className="font-mono font-semibold text-fg">{from === to ? from : `${from}–${to}`}</span>
            <span className="text-muted">
              <span className="font-mono text-fg">{shown.toLocaleString()}</span> incidents on map
              {!full && (
                <button type="button" onClick={() => { setPlaying(false); onChange([min, max]); }} className="ml-2 text-accent hover:underline">
                  All years
                </button>
              )}
            </span>
          </div>
          <div className="fl-range mt-1">
            <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded bg-panel-2" />
            <div className="absolute top-1/2 h-1 -translate-y-1/2 rounded bg-accent" style={{ left: `${left}%`, right: `${100 - right}%` }} />
            <input
              type="range"
              min={min}
              max={max}
              value={from}
              aria-label="First year shown"
              onChange={(e) => {
                setPlaying(false);
                onChange([Math.min(Number(e.target.value), to), to]);
              }}
            />
            <input
              type="range"
              min={min}
              max={max}
              value={to}
              aria-label="Last year shown"
              onChange={(e) => {
                setPlaying(false);
                onChange([from, Math.max(Number(e.target.value), from)]);
              }}
            />
          </div>
          <div className="mt-0.5 flex justify-between text-[10px] text-muted">
            <span>{min}</span>
            <span>Map display only · the forecast always uses all years</span>
            <span>{max}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
