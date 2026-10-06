"use client";

import { policyText } from "@/lib/format";

const PRESETS = [
  { label: "Count-only", value: 1 },
  { label: "Balanced 3×", value: 3 },
  { label: "Severity 6×", value: 6 },
] as const;

type Props = {
  high: number;
  onChange: (value: number) => void;
};

export function PolicyBar({ high, onChange }: Props) {
  const fillPct = ((high - 1) / 7) * 100;

  return (
    <section
      className="flex flex-col rounded-xl border border-border bg-panel"
      style={{ padding: "14px 20px", gap: 12 }}
    >
      <style>{`
        .policy-slider {
          -webkit-appearance: none;
          appearance: none;
          width: 100%;
          height: 18px;
          margin: 0;
          background: transparent;
          cursor: pointer;
        }
        .policy-slider:focus-visible {
          outline: none;
        }
        .policy-slider:focus-visible::-webkit-slider-thumb {
          box-shadow: 0 0 0 2px var(--accent), 0 1px 3px rgba(0,0,0,.18);
        }
        .policy-slider:focus-visible::-moz-range-thumb {
          box-shadow: 0 0 0 2px var(--accent), 0 1px 3px rgba(0,0,0,.18);
        }
        .policy-slider::-webkit-slider-runnable-track {
          height: 4px;
          border-radius: 2px;
          background: linear-gradient(
            to right,
            var(--text) 0%,
            var(--text) var(--policy-fill, 0%),
            var(--border) var(--policy-fill, 0%),
            var(--border) 100%
          );
        }
        .policy-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 18px;
          height: 18px;
          margin-top: -7px;
          border-radius: 50%;
          background: var(--panel);
          border: 1px solid var(--border);
          box-shadow: 0 1px 3px rgba(0,0,0,.18);
        }
        .policy-slider::-moz-range-track {
          height: 4px;
          border-radius: 2px;
          background: var(--border);
        }
        .policy-slider::-moz-range-progress {
          height: 4px;
          border-radius: 2px;
          background: var(--text);
        }
        .policy-slider::-moz-range-thumb {
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: var(--panel);
          border: 1px solid var(--border);
          box-shadow: 0 1px 3px rgba(0,0,0,.18);
        }
      `}</style>

      {/* Row 1: label + policy text | presets */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-baseline gap-3">
          <span className="text-[12px] font-semibold uppercase tracking-[0.08em] text-muted">
            Risk policy
          </span>
          <span className="font-mono text-[13px] text-fg">
            {policyText(high)}
          </span>
        </div>

        <div
          role="radiogroup"
          aria-label="Policy presets"
          className="inline-flex"
          style={{
            gap: 3,
            background: "var(--panel-2)",
            borderRadius: 10,
            padding: 3,
          }}
        >
          {PRESETS.map((p) => {
            const active = high === p.value;
            return (
              <button
                key={p.value}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => onChange(p.value)}
                className="cursor-pointer whitespace-nowrap text-[13px] font-semibold"
                style={{
                  height: 34,
                  padding: "0 14px",
                  border: "none",
                  borderRadius: 8,
                  background: active ? "var(--panel)" : "transparent",
                  color: active ? "var(--text)" : "var(--muted)",
                  boxShadow: active
                    ? "0 1px 2px rgba(0,0,0,.10)"
                    : undefined,
                }}
              >
                {p.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Row 2: Frequency · slider · Severity */}
      <div
        className="flex items-center"
        style={{ gap: 12 }}
      >
        <span className="shrink-0 text-[12px] text-muted">Frequency</span>
        <label htmlFor="sev" className="sr-only">
          Severity weight
        </label>
        <input
          id="sev"
          type="range"
          min={1}
          max={8}
          step={1}
          value={high}
          onChange={(e) => onChange(Number(e.target.value))}
          className="policy-slider"
          style={{
            flex: 1,
            minWidth: 0,
            ["--policy-fill" as string]: `${fillPct}%`,
          }}
        />
        <span className="shrink-0 text-[12px] text-muted">Severity</span>
      </div>
    </section>
  );
}
