"use client";

import ReactMarkdown from "react-markdown";
import { formatToolChip } from "@/lib/format";
import type { AgentToolCall } from "@/lib/types";

export type ChatMessage = {
  id: string;
  role: "user" | "agent";
  text: string;
  tool_calls?: AgentToolCall[];
  error?: boolean;
  escalateCorridor?: string;
};

type Props = {
  messages: ChatMessage[];
  thinking: boolean;
  approving: string | null;
  loggedEscalations: Set<string>;
  onApprove: (corridor: string) => void;
  emptyHints?: React.ReactNode;
};

export function ChatThread({
  messages,
  thinking,
  approving,
  loggedEscalations,
  onApprove,
  emptyHints,
}: Props) {
  return (
    <div className="flex flex-col gap-2.5">
      {messages.length === 0 && emptyHints}

      {messages.map((m) =>
        m.role === "user" ? (
          <div key={m.id} className="flex flex-col items-end">
            <div
              className="max-w-[85%] bg-[#15171A] px-3 py-2 text-[14px] text-white"
              style={{ borderRadius: "12px 12px 3px 12px" }}
            >
              {m.text}
            </div>
          </div>
        ) : (
          <div key={m.id} className="flex flex-col items-start gap-1.5">
            {m.tool_calls?.map((t, i) => (
              <span
                key={`${t.name}-${i}`}
                className="rounded font-mono text-[11px]"
                style={{
                  background: "#EEF2FF",
                  color: "#1E3A8A",
                  padding: "3px 8px",
                  borderRadius: 4,
                }}
              >
                {formatToolChip(t.name, t.input)}
              </span>
            ))}
            <div
              className={`max-w-[95%] px-3 py-2.5 text-[14px] leading-[1.5] ${
                m.error
                  ? "bg-[#FDEEE3] text-[#8A2E08]"
                  : "bg-[#F7F7F4] text-[#15171A]"
              }`}
              style={{ borderRadius: "3px 12px 12px 12px" }}
            >
              <ReactMarkdown
                components={{
                  p: ({ children }) => (
                    <p className="mb-1.5 last:mb-0">{children}</p>
                  ),
                  ul: ({ children }) => (
                    <ul className="mb-1.5 list-disc pl-4 last:mb-0">
                      {children}
                    </ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="mb-1.5 list-decimal pl-4 last:mb-0">
                      {children}
                    </ol>
                  ),
                  strong: ({ children }) => (
                    <strong className="font-semibold">{children}</strong>
                  ),
                  code: ({ children }) => (
                    <code className="font-mono text-[12px]">{children}</code>
                  ),
                }}
              >
                {m.text}
              </ReactMarkdown>
            </div>
            {m.escalateCorridor && (
              <div className="flex w-full items-center justify-between gap-2.5 rounded-lg border border-[#ECECE7] px-2.5 py-2">
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="text-[14px] font-semibold">
                    {m.escalateCorridor}
                  </span>
                </span>
                {loggedEscalations.has(m.escalateCorridor) ? (
                  <span
                    className="inline-flex items-center whitespace-nowrap rounded-lg border border-[#E3E3DE] bg-[#EFEFEB] px-3 text-[13px] font-semibold text-[#3A3E44]"
                    style={{ minHeight: 36 }}
                  >
                    Logged
                  </span>
                ) : (
                  <button
                    type="button"
                    disabled={approving === m.escalateCorridor}
                    onClick={() => onApprove(m.escalateCorridor!)}
                    className="whitespace-nowrap rounded-lg border border-[#15171A] bg-[#15171A] px-3 text-[13px] font-semibold text-white disabled:opacity-50"
                    style={{ minHeight: 36 }}
                  >
                    {approving === m.escalateCorridor
                      ? "Sending…"
                      : "Approve P1"}
                  </button>
                )}
              </div>
            )}
          </div>
        ),
      )}
      {thinking && (
        <div className="text-[13px] italic text-[#5A5F66]">Thinking…</div>
      )}
    </div>
  );
}
