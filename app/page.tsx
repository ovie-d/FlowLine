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
import type { TriageDraft } from "@/lib/types";
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

export default function Home() {
  const queryClient = useQueryClient();
  const [high, setHigh] = useState(3);
  const debouncedHigh = useDebounced(high, 250);
  const [selected, setSelected] = useState<string | null>(null);
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
  });

  const improvementQ = useQuery({
    queryKey: ["improvement"],
    queryFn: getImprovement,
  });

  const decisionsQ = useQuery({
    queryKey: ["decisions"],
    queryFn: getDecisions,
  });

  const ranking = rankingQ.data ?? [];
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

  // Default / persist selection
  useEffect(() => {
    if (ranking.length === 0) return;
    setSelected((prev) => {
      if (prev && ranking.some((r) => r.corridor === prev)) return prev;
      return ranking[0].corridor;
    });
  }, [ranking]);

  // Auto-expand when selected is ranks 6–15
  useEffect(() => {
    if (!selected) return;
    const row = ranking.find((r) => r.corridor === selected);
    if (row && row.rank > 5) setExpanded(true);
  }, [selected, ranking]);

  const corridorQ = useQuery({
    queryKey: ["corridor", selected, debouncedHigh],
    queryFn: () => getCorridor(selected!, debouncedHigh),
    enabled: !!selected,
    placeholderData: keepPreviousData,
  });

  const escalateDrafts = useMemo(
    () =>
      (triage?.drafts ?? []).filter(
        (d) => d.action === "Escalate" || d.priority === "P1",
      ),
    [triage],
  );

  const loggedEscalations = useMemo(() => {
    const set = new Set<string>();
    const policy = policyLabel(debouncedHigh);
    for (const d of decisionsQ.data ?? []) {
      if (
        d.action.toLowerCase().includes("escalate") &&
        (d.policy === policy || d.policy.includes(`high=${debouncedHigh}`))
      ) {
        set.add(d.corridor);
      }
    }
    return set;
  }, [decisionsQ.data, debouncedHigh]);

  const restDrafts = (triage?.drafts ?? []).filter((d) => d.rank > 5);
  const inspectN = restDrafts.filter((d) => d.action === "Inspect").length;
  const deferN = restDrafts.filter((d) => d.action === "Defer").length;
  const thinCount = ranking
    .slice(5)
    .filter((r) => r.confidence === "low").length;
  const collapsedSummary = `${inspectN} inspect · ${deferN} defer`;

  const seriousTop15 = ranking.reduce((s, r) => s + (r.n_high ?? 0), 0);
  const incidentsTop15 = ranking.reduce((s, r) => s + (r.n ?? 0), 0);
  const baselineTop15 = (baselineQ.data ?? []).slice(0, 15);
  const seriousBaseline = baselineTop15.reduce((s, r) => s + (r.n_high ?? 0), 0);
  const incidentsBaseline = baselineTop15.reduce((s, r) => s + (r.n ?? 0), 0);
  const seriousTotal = (baselineQ.data ?? []).reduce(
    (s, r) => s + (r.n_high ?? 0),
    0,
  );

  // Prefer improvement endpoint for serious baseline if present
  const stages = improvementQ.data?.stages;
  const baselineSeriousFromApi =
    stages?.find((s) => String(s.name).toLowerCase().includes("baseline"))
      ?.serious ?? seriousBaseline;

  function selectCorridor(name: string) {
    setSelected(name);
    setTab("details");
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
      const res = await askAgent(sessionId, question);
      const explain = res.tool_calls?.find((t) => t.name === "explain_corridor");
      const corridorFromTool =
        explain && typeof explain.input?.name === "string"
          ? explain.input.name
          : explain && typeof explain.input?.corridor === "string"
            ? explain.input.corridor
            : undefined;

      if (corridorFromTool) selectCorridor(corridorFromTool);

      const escalateHit = res.tool_calls?.find((t) => t.name === "log_decision");
      if (escalateHit || res.tool_calls?.some((t) => t.name === "log_decision")) {
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
      className="bg-[#F5F5F3] text-[#15171A] antialiased"
      style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        padding: "16px 24px 32px",
        boxSizing: "border-box",
      }}
    >
      <div
        className="mx-auto flex w-full min-h-0 flex-1 flex-col"
        style={{ maxWidth: 1600, gap: 14 }}
      >
        <header
          className="flex flex-wrap items-end justify-between gap-4"
          style={{
            flex: "0 0 auto",
            paddingBottom: 10,
            borderBottom: "1px solid #DCDCD7",
          }}
        >
          <div className="flex flex-col gap-1">
            <h1
              className="font-display text-[40px] text-[#15171A]"
              style={{ lineHeight: 1, letterSpacing: "-0.01em" }}
            >
              Flowline
            </h1>
            <p className="text-[14px] text-[#5A5F66]">
              Pipeline corridor inspection priority · Alberta · CER incident
              history 2015 – Aug 2026
            </p>
          </div>
        </header>

        {backendDown && (
          <div
            className="rounded-lg border border-[#A8370A]/30 bg-[#FDEEE3] px-3 py-2 text-[13px] text-[#8A2E08]"
            style={{ flex: "0 0 auto" }}
          >
            Backend unreachable at {process.env.NEXT_PUBLIC_API_URL}. Start
            FastAPI on :8000 (CORS for localhost:3000). Rankings will appear
            when the API is up.
          </div>
        )}

        <div
          className="grid min-h-0"
          style={{
            flex: "1 1 auto",
            gridTemplateColumns: "minmax(0, 1fr) 380px",
            gap: 16,
            alignItems: "stretch",
            minHeight: 0,
          }}
        >
          <main
            className="flex min-w-0 flex-col"
            style={{ gap: 14, minHeight: 0, overflowY: "auto" }}
          >
            <PolicyBar high={high} onChange={setHigh} />

            <StatCards
              topCorridor={ranking[0]?.corridor ?? null}
              topRow={ranking[0] ?? null}
              seriousTop15={ranking.length ? seriousTop15 : null}
              seriousTotal={seriousTotal || null}
              seriousBaseline={baselineSeriousFromApi}
              incidentsTop15={ranking.length ? incidentsTop15 : null}
              incidentsBaseline={incidentsBaseline || null}
              triage={triage}
            />

            <section className="flex flex-wrap items-start gap-4">
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
          className="text-center text-[13px] text-[#5A5F66]"
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
