"use client";

import type { Decision } from "@/lib/types";

type Props = {
  decisions: Decision[];
};

export function DecisionLog({ decisions }: Props) {
  const items = decisions.slice(0, 40);

  return (
    <div
      className="flex flex-col gap-1.5 border-t border-[#ECECE7] pt-2.5"
      style={{ flex: "0 0 auto", maxHeight: 150, overflowY: "auto" }}
    >
      <div className="mt-1 text-[12px] font-semibold uppercase tracking-[0.08em] text-[#5A5F66]">
        Decision log
      </div>
      {items.length === 0 && (
        <div className="text-[13px] text-[#5A5F66]">No decisions logged yet.</div>
      )}
      {items.map((d, i) => (
        <div
          key={d.id ?? `${d.ts}-${d.corridor}-${i}`}
          className="flex justify-between gap-2 border-t border-[#EFEFEB] pt-1.5 text-[13px]"
        >
          <span>
            <b>{d.corridor}</b> · {d.action.toLowerCase()}
            {d.priority ? ` ${d.priority}` : ""}
          </span>
          <span className="font-mono text-[12px] text-[#5A5F66]">{d.policy}</span>
        </div>
      ))}
    </div>
  );
}
