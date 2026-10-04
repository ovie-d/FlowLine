"use client";

import { useRef, useState } from "react";
import type { Decision, TriageDraft } from "@/lib/types";
import { ChatThread, type ChatMessage } from "./ChatThread";
import { DecisionLog } from "./DecisionLog";

const SUGGESTIONS = [
  "Triage the top 15",
  "Why is #1 ranked here?",
  "Explain the thin-data corridors",
];

type Props = {
  messages: ChatMessage[];
  thinking: boolean;
  onSend: (question: string) => Promise<void>;
  onApprove: (corridor: string) => Promise<void>;
  approving: string | null;
  loggedEscalations: Set<string>;
  decisions: Decision[];
  escalateDrafts: TriageDraft[];
  onNewChat?: () => void;
  suggestionLabels?: string[];
};

export function AgentSidebar({
  messages,
  thinking,
  onSend,
  onApprove,
  approving,
  loggedEscalations,
  decisions,
  escalateDrafts,
  suggestionLabels,
}: Props) {
  const [text, setText] = useState("");
  const threadRef = useRef<HTMLDivElement | null>(null);
  const busy = thinking || approving != null;
  const pills = suggestionLabels?.length ? suggestionLabels : SUGGESTIONS;

  async function submit(q: string) {
    const trimmed = q.trim();
    if (!trimmed || busy) return;
    setText("");
    await onSend(trimmed);
    requestAnimationFrame(() => {
      threadRef.current?.scrollTo({
        top: threadRef.current.scrollHeight,
        behavior: "smooth",
      });
    });
  }

  return (
    <aside
      aria-label="Agent"
      className="flex min-h-0 flex-col gap-2.5 rounded-xl border border-[#E3E3DE] bg-white"
      style={{
        height: "100%",
        minHeight: 0,
        padding: 16,
        boxSizing: "border-box",
        width: 380,
      }}
    >
      {/* Title — fixed top */}
      <div
        className="flex items-baseline justify-between border-b border-[#ECECE7] pb-2.5"
        style={{ flex: "0 0 auto" }}
      >
        <div className="text-[15px] font-semibold text-[#15171A]">Agent</div>
        <div className="text-[12px] text-[#5A5F66]">
          Drafts only · planner approves
        </div>
      </div>

      {/* Thread (+ escalate drafts) — only this scrolls */}
      <div
        className="flex min-h-0 flex-col gap-2.5"
        style={{ flex: 1, minHeight: 0, overflowY: "auto" }}
        ref={threadRef}
      >
        <ChatThread
          messages={messages}
          thinking={thinking}
          approving={approving}
          loggedEscalations={loggedEscalations}
          onApprove={onApprove}
          emptyHints={
            <p className="text-[13px] text-[#5A5F66]">
              Ask about a corridor, run triage, or approve an escalate draft.
            </p>
          }
        />

        {escalateDrafts.length > 0 && (
          <div className="flex flex-col gap-2">
            {escalateDrafts.map((d) => {
              const done = loggedEscalations.has(d.corridor);
              return (
                <div
                  key={d.corridor}
                  className="flex items-center justify-between gap-2.5 rounded-lg border border-[#ECECE7] px-2.5 py-2"
                >
                  <span className="flex min-w-0 flex-col gap-0.5">
                    <span className="text-[14px] font-semibold">
                      {d.corridor}
                    </span>
                    <span className="text-[12px] text-[#5A5F66]">{d.reason}</span>
                  </span>
                  <button
                    type="button"
                    disabled={busy || done}
                    onClick={() => onApprove(d.corridor)}
                    className="whitespace-nowrap rounded-lg px-3 text-[13px] font-semibold disabled:cursor-default"
                    style={{
                      minHeight: 36,
                      background: done ? "#EFEFEB" : "#15171A",
                      color: done ? "#3A3E44" : "#FFFFFF",
                      border: done
                        ? "1px solid #E3E3DE"
                        : "1px solid #15171A",
                    }}
                  >
                    {done ? "Logged" : "Approve P1"}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Bottom chrome — always visible */}
      <div className="flex flex-wrap gap-1.5" style={{ flex: "0 0 auto" }}>
        {pills.map((s) => (
          <button
            key={s}
            type="button"
            disabled={busy}
            onClick={() => submit(s)}
            className="rounded-full border border-[#DCDCD7] bg-white px-2.5 text-[12px] text-[#3A3E44] disabled:opacity-50"
            style={{ minHeight: 32 }}
          >
            {s}
          </button>
        ))}
      </div>

      <div
        className="flex gap-2 border-t border-[#ECECE7] pt-3"
        style={{ flex: "0 0 auto" }}
      >
        <label htmlFor="ask" className="sr-only">
          Ask the agent
        </label>
        <input
          id="ask"
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void submit(text);
          }}
          disabled={busy}
          placeholder="Ask about a corridor, or approve a decision"
          className="min-w-0 flex-1 rounded-lg border border-[#CFCFC9] bg-white px-3 text-[14px] text-[#15171A] disabled:opacity-50"
          style={{ minHeight: 42 }}
        />
        <button
          type="button"
          disabled={busy || !text.trim()}
          onClick={() => submit(text)}
          className="rounded-lg border border-[#15171A] bg-[#15171A] px-4 text-[14px] font-semibold text-white disabled:opacity-40"
          style={{ minHeight: 42 }}
        >
          Send
        </button>
      </div>

      <div style={{ flex: "0 0 auto" }}>
        <DecisionLog decisions={decisions} />
      </div>
    </aside>
  );
}
