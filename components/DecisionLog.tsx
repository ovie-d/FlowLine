"use client";

import { asDisplayText, formatPolicy } from "@/lib/format";
import type { Decision } from "@/lib/types";

type Props = {
  decisions: Decision[];
};

export function DecisionLog({ decisions }: Props) {
  const items = decisions.slice(0, 40);

  return (
    <div
      className="flex flex-col gap-1.5 border-t border-border pt-2.5"
      style={{ flex: "0 0 auto", maxHeight: 150, overflowY: "auto" }}
    >
      <div className="mt-1 text-[12px] font-semibold uppercase tracking-[0.08em] text-muted">
        Decision log
      </div>
      {items.length === 0 && (
        <div className="text-[13px] text-muted">No decisions logged yet.</div>
      )}
      {items.map((d, i) => {
        const action = asDisplayText(d.action).toLowerCase();
        const priority = d.priority ? ` ${asDisplayText(d.priority)}` : "";
        const policyLabel = formatPolicy(d.policy);
        return (
          <div
            key={d.id ?? `${d.ts}-${d.corridor}-${i}`}
            className="flex justify-between gap-2 border-t border-border pt-1.5 text-[13px]"
          >
            <span>
              <b>{asDisplayText(d.corridor)}</b> · {action}
              {priority}
            </span>
            <span className="font-mono text-[12px] text-muted">
              {policyLabel}
            </span>
          </div>
        );
      })}
    </div>
  );
}
