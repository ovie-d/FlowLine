"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  askAgent,
  getBaseline,
  getCorridor,
  getDecisions,
  getImprovement,
  getRanking,
  getTriage,
  resetAgent,
} from "@/lib/api";
import { policyLabel } from "@/lib/format";
import type { TriageAction, TriageDraft } from "@/lib/types";
import { AgentSidebar } from "@/components/AgentSidebar";
import type { ChatMessage } from "@/components/ChatThread";
import { MapDetailsCard } from "@/components/MapDetailsCard";
import { PolicyBar } from "@/components/PolicyBar";
import { RankedList } from "@/components/RankedList";
import { StatCards } from "@/components/StatCards";

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

function normalizeAction(action: string): TriageAction {
  return action.toLowerCase() as TriageAction;
}

function normalizeDraft(d: TriageDraft): TriageDraft {
  return { ...d, action: normalizeAction(d.action) };
}

/** Existing corridor risk ranking (secondary tab of the command center). */
export default function RankingView() {
  const queryClient = useQueryClient();
  const [high, setHigh] = useState(3);
  const debouncedHigh = useDebounced(high, 250);
  const [picked, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<"map" | "details">("map");
  const [expanded, setExpanded] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [thinking, setThinking] = useState(false);
  const [approving, setApproving] = useState<string | null>(null);

  const rankingQ = useQuery({
    queryKey: ["ranking", debouncedHigh],
    queryFn: () => getRanking(debouncedHigh, 15),
    placeholderData: keepPreviousData,
  });

  const baselineQ = useQuery({
    queryKey: ["baseline"],
    queryFn: getBaseline,
  });

  const triageQ = useQuery({
    queryKey: ["triage", debouncedHigh],
    queryFn: () => getTriage(debouncedHigh),
    placeholderData: keepPreviousData,
    select: (data) => ({
      ...data,
      drafts: data.drafts.map(normalizeDraft),
    }),
  });

  const improvementQ = useQuery({
    queryKey: ["improvement", debouncedHigh],
    queryFn: () => getImprovement(debouncedHigh),
    placeholderData: keepPreviousData,
  });

  const decisionsQ = useQuery({
    queryKey: ["decisions"],
    queryFn: getDecisions,
  });

  const ranking = useMemo(() => rankingQ.data ?? [], [rankingQ.data]);
  const triage = triageQ.data;

  const draftsByCorridor = useMemo(() => {
    const map = new Map<string, TriageDraft>();
    for (const d of triage?.drafts ?? []) map.set(d.corridor, d);
    return map;
  }, [triage]);

  const baselineRank = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of baselineQ.data ?? []) map.set(r.corridor, r.rank);
    return map;
  }, [baselineQ.data]);

  // Default / persist selection (derived, not synced in an effect).
  const selected =
    picked && ranking.some((r) => r.corridor === picked)
      ? picked
      : (ranking[0]?.corridor ?? null);

  const corridorQ = useQuery({
    queryKey: ["corridor", selected, debouncedHigh],
    queryFn: () => getCorridor(selected!, debouncedHigh),
    enabled: !!selected,
    placeholderData: keepPreviousData,
  });

  const escalateDrafts = useMemo(
    () =>
      (triage?.drafts ?? []).filter(
        (d) => d.action === "escalate" || d.priority === "P1",
      ),
    [triage],
  );

  const loggedEscalations = useMemo(() => {
    const set = new Set<string>();
    const policy = policyLabel(debouncedHigh);
    for (const d of decisionsQ.data ?? []) {
      const policyStr =
        typeof d.policy === "string" ? d.policy : JSON.stringify(d.policy);
      if (
        d.action.toLowerCase().includes("escalate") &&
        (policyStr === policy ||
          policyStr.includes(`high=${debouncedHigh}`) ||
          policyStr.includes(`"high": ${debouncedHigh}`) ||
          policyStr.includes(`"high":${debouncedHigh}`))
      ) {
        set.add(d.corridor);
      }
    }
    return set;
  }, [decisionsQ.data, debouncedHigh]);

  const restDrafts = (triage?.drafts ?? []).filter((d) => d.rank > 5);
  const inspectN = restDrafts.filter((d) => d.action === "inspect").length;
  const deferN = restDrafts.filter((d) => d.action === "defer").length;
  const thinCount = ranking
    .slice(5)
    .filter((r) => r.confidence === "low").length;
  const collapsedParts: string[] = [];
  if (inspectN > 0) collapsedParts.push(`${inspectN} inspect`);
  if (deferN > 0) collapsedParts.push(`${deferN} defer`);
  const collapsedSummary = collapsedParts.join(" · ");

  const improvement = improvementQ.data;
  const seriousTop15 = improvement?.current.serious_captured ?? null;
  const seriousTotal = improvement?.serious_total ?? null;
  const seriousBaseline = improvement?.baseline.serious_captured ?? null;
  const incidentsTop15 = improvement?.current.incidents_covered ?? null;
  const incidentsBaseline = improvement?.baseline.incidents_covered ?? null;

  function selectCorridor(name: string) {
    setSelected(name);
    setTab("details");
    // Auto-expand when the selection sits in ranks 6–15.
    const row = ranking.find((r) => r.corridor === name);
    if (row && row.rank > 5) setExpanded(true);
  }

  async function sendQuestion(question: string) {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      text: question,
    };
    setMessages((m) => [...m, userMsg]);
    setThinking(true);
    try {
      const res = await askAgent(sessionId, question, high);
      const explain = res.tool_calls?.find((t) => t.name === "explain_corridor");
      const corridorFromTool =
        explain && typeof explain.input?.name === "string"
          ? explain.input.name
          : explain && typeof explain.input?.corridor === "string"
            ? explain.input.corridor
            : undefined;

      if (corridorFromTool) selectCorridor(corridorFromTool);

      if (res.tool_calls?.some((t) => t.name === "log_decision")) {
        await queryClient.invalidateQueries({ queryKey: ["decisions"] });
      }

      const escalateCorridor = escalateDrafts.find((d) =>
        res.answer?.includes(d.corridor),
      )?.corridor;

      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          role: "agent",
          text: res.error
            ? res.answer || "Agent unavailable. Rankings and triage still work."
            : res.answer,
          tool_calls: res.tool_calls,
          error: !!res.error,
          escalateCorridor:
            escalateCorridor &&
            escalateDrafts.some((d) => d.corridor === escalateCorridor)
              ? escalateCorridor
              : undefined,
        },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          role: "agent",
          text: "Agent request failed. Rankings and triage still work.",
          error: true,
        },
      ]);
    } finally {
      setThinking(false);
    }
  }

  async function approveP1(corridor: string) {
    setApproving(corridor);
    try {
      await sendQuestion(`Escalate ${corridor}, P1`);
      await queryClient.invalidateQueries({ queryKey: ["decisions"] });
    } finally {
      setApproving(null);
    }
  }

  async function newChat() {
    try {
      await resetAgent(sessionId);
    } catch {
      /* ignore — UI still clears */
    }
    setMessages([]);
  }

  const backendDown =
    rankingQ.isError && baselineQ.isError && triageQ.isError;

  const suggestLabels = [
    ranking[0] ? `Explain ${ranking[0].corridor}` : "Triage the top 15",
    "Explain Jenner",
    "Escalate Hardisty, P1",
  ];

  return (
    <div
      className="bg-bg text-fg antialiased"
      style={{
        display: "flex",
        flexDirection: "column",
        padding: "16px 24px 32px",
        boxSizing: "border-box",
      }}
    >
      <div
        className="mx-auto flex w-full min-h-0 flex-1 flex-col"
        style={{ maxWidth: 1600, gap: 14 }}
      >
        <p className="text-[13px] text-muted" style={{ flex: "0 0 auto" }}>
          Corridor inspection priority · Alberta · CER incident history 2015 – Aug 2026 ·
          historic hotspot ranking under your consequence weight
        </p>

        {backendDown && (
          <div
            className="rounded-lg border border-critical/30 bg-thin-bg px-3 py-2 text-[13px] text-warn"
            style={{ flex: "0 0 auto" }}
          >
            Backend unreachable at {process.env.NEXT_PUBLIC_API_URL}. Start
            FastAPI on :8000 (CORS for localhost:3000). Rankings will appear
            when the API is up.
          </div>
        )}

        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
          <main
            className="flex min-w-0 flex-col"
            style={{ gap: 14 }}
          >
            <div style={{ flex: "0 0 auto" }}>
              <PolicyBar high={high} onChange={setHigh} />
            </div>

            <div style={{ flex: "0 0 auto" }}>
              <StatCards
                topCorridor={ranking[0]?.corridor ?? null}
                topRow={ranking[0] ?? null}
                seriousTop15={seriousTop15}
                seriousTotal={seriousTotal}
                seriousBaseline={seriousBaseline}
                incidentsTop15={incidentsTop15}
                incidentsBaseline={incidentsBaseline}
                triage={triage}
              />
            </div>

            <section className="grid min-w-0 gap-4 2xl:grid-cols-[320px_minmax(0,1fr)]">
              <MapDetailsCard
                tab={tab}
                onTabChange={setTab}
                selected={selected}
                ranking={ranking}
                detail={corridorQ.data}
                detailLoading={corridorQ.isFetching}
                onSelect={selectCorridor}
              />
              <RankedList
                rows={ranking}
                draftsByCorridor={draftsByCorridor}
                baselineRank={baselineRank}
                selected={selected}
                expanded={expanded}
                onToggleExpanded={() => setExpanded((v) => !v)}
                onSelect={selectCorridor}
                high={debouncedHigh}
                collapsedSummary={collapsedSummary}
                thinCount={thinCount}
              />
            </section>
          </main>

          <AgentSidebar
            messages={messages}
            thinking={thinking}
            onSend={sendQuestion}
            onApprove={approveP1}
            approving={approving}
            loggedEscalations={loggedEscalations}
            decisions={decisionsQ.data ?? []}
            escalateDrafts={escalateDrafts}
            onNewChat={newChat}
            suggestionLabels={suggestLabels}
          />
        </div>

        <footer
          className="text-center text-[13px] text-muted"
          style={{ flex: "0 0 auto", paddingTop: 8 }}
        >
          We rank historic incident hotspots under a stated risk policy. We do
          not certify any pipe as safe. The tool supports the integrity
          engineer&apos;s decision; it doesn&apos;t replace engineering
          judgment.
        </footer>
      </div>
    </div>
  );
}
