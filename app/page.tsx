"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";

/*
============================================================
PIPELINE MAP
============================================================
*/

const PipelineMap = dynamic(() => import("./PipelineMap"), {
  ssr: false,

  loading: () => (
    <div className="flex h-[600px] items-center justify-center bg-slate-800 text-slate-400">
      Loading Alberta pipeline map...
    </div>
  ),
});

/*
============================================================
TYPES
============================================================
*/

type RiskLevel = "Low" | "Moderate" | "High" | "Very High";

type ConfidenceLevel = "Low" | "Moderate" | "High";

type ModelWeights = {
  severity: number;
  pipelineRelevance: number;
  frequency: number;
  recency: number;
  releaseVolume: number;
  exposure: number;
};

type Corridor = {
  id: number;
  name: string;

  relevantEvents: number;

  pipelineReleases: number;
  facilityFires: number;
  limitBreaches: number;
  otherEvents: number;

  seriousReleases: number;
  recentEvents: number;

  totalReleaseVolume: number;

  severity: number;
  pipelineRelevance: number;
  frequency: number;
  recency: number;
  releaseVolume: number;
  exposure: number;

  riskLevel: RiskLevel;
  confidence: ConfidenceLevel;

  primaryDriver: string;
  rationale: string[];
  recommendedAction: string;
};

/*
============================================================
DEMONSTRATION CORRIDOR DATA
============================================================

These values demonstrate how the model works.

They should eventually be replaced by calculated values from
the real pipeline + incident datasets.
*/

const corridors: Corridor[] = [
  {
    id: 1,
    name: "Corridor A",

    relevantEvents: 30,

    pipelineReleases: 4,
    facilityFires: 14,
    limitBreaches: 10,
    otherEvents: 2,

    seriousReleases: 1,
    recentEvents: 8,

    totalReleaseVolume: 8200,

    severity: 52,
    pipelineRelevance: 48,
    frequency: 92,
    recency: 68,
    releaseVolume: 45,
    exposure: 62,

    riskLevel: "Moderate",
    confidence: "High",

    primaryDriver:
      "High event frequency, but many events are contextual rather than serious pipeline releases.",

    rationale: [
      "30 relevant events provide a strong evidence base.",
      "Most events are facility fires or operating-limit breaches.",
      "Only 1 event is classified as a serious pipeline release.",
      "High frequency raises concern, but severity and pipeline relevance are lower.",
    ],

    recommendedAction:
      "Review repeated operating and facility events before assigning a dedicated pipeline inspection crew.",
  },

  {
    id: 2,
    name: "Corridor B",

    relevantEvents: 6,

    pipelineReleases: 6,
    facilityFires: 0,
    limitBreaches: 0,
    otherEvents: 0,

    seriousReleases: 5,
    recentEvents: 4,

    totalReleaseVolume: 48500,

    severity: 96,
    pipelineRelevance: 100,
    frequency: 48,
    recency: 88,
    releaseVolume: 94,
    exposure: 82,

    riskLevel: "Very High",
    confidence: "Moderate",

    primaryDriver:
      "Repeated high-severity releases directly associated with pipeline assets.",

    rationale: [
      "All 6 relevant events are pipeline releases.",
      "5 of the 6 releases are high-severity events.",
      "Large cumulative release volume increases consequence concern.",
      "4 events occurred recently.",
      "The evidence base is smaller, so confidence remains Moderate.",
    ],

    recommendedAction:
      "Prioritize for engineering review and near-term inspection planning.",
  },

  {
    id: 3,
    name: "Corridor C",

    relevantEvents: 2,

    pipelineReleases: 2,
    facilityFires: 0,
    limitBreaches: 0,
    otherEvents: 0,

    seriousReleases: 2,
    recentEvents: 2,

    totalReleaseVolume: 31000,

    severity: 98,
    pipelineRelevance: 100,
    frequency: 24,
    recency: 96,
    releaseVolume: 88,
    exposure: 85,

    riskLevel: "Very High",
    confidence: "Low",

    primaryDriver:
      "Two recent high-severity pipeline releases create a strong risk signal, but the evidence base is small.",

    rationale: [
      "Both recorded events are serious pipeline releases.",
      "Both events occurred recently.",
      "Release severity is high.",
      "Only 2 events support the ranking.",
      "This represents High Risk — Low Evidence Base.",
    ],

    recommendedAction:
      "Escalate for engineering review while acknowledging the limited evidence base.",
  },

  {
    id: 4,
    name: "Corridor D",

    relevantEvents: 18,

    pipelineReleases: 7,
    facilityFires: 4,
    limitBreaches: 5,
    otherEvents: 2,

    seriousReleases: 3,
    recentEvents: 7,

    totalReleaseVolume: 21500,

    severity: 76,
    pipelineRelevance: 78,
    frequency: 76,
    recency: 79,
    releaseVolume: 70,
    exposure: 74,

    riskLevel: "High",
    confidence: "High",

    primaryDriver:
      "Repeated pipeline-relevant events supported by a comparatively strong evidence base.",

    rationale: [
      "7 pipeline releases are present in the event history.",
      "3 releases are considered serious.",
      "7 events occurred recently.",
      "18 relevant events provide a comparatively strong evidence base.",
    ],

    recommendedAction:
      "Include in the inspection shortlist and review recent release history.",
  },

  {
    id: 5,
    name: "Corridor E",

    relevantEvents: 11,

    pipelineReleases: 3,
    facilityFires: 2,
    limitBreaches: 5,
    otherEvents: 1,

    seriousReleases: 1,
    recentEvents: 3,

    totalReleaseVolume: 7400,

    severity: 58,
    pipelineRelevance: 62,
    frequency: 60,
    recency: 55,
    releaseVolume: 42,
    exposure: 68,

    riskLevel: "Moderate",
    confidence: "Moderate",

    primaryDriver:
      "Mixed event history without a dominant high-severity pipeline-release pattern.",

    rationale: [
      "11 relevant events provide a moderate evidence base.",
      "Only 3 events are pipeline releases.",
      "Most events are lower-consequence or contextual.",
      "Recent-event activity is lower than higher-ranked corridors.",
    ],

    recommendedAction:
      "Continue monitoring and investigate if additional pipeline-relevant evidence emerges.",
  },

  {
    id: 6,
    name: "Corridor F",

    relevantEvents: 17,

    pipelineReleases: 8,
    facilityFires: 3,
    limitBreaches: 4,
    otherEvents: 2,

    seriousReleases: 4,
    recentEvents: 6,

    totalReleaseVolume: 26400,

    severity: 82,
    pipelineRelevance: 88,
    frequency: 74,
    recency: 81,
    releaseVolume: 76,
    exposure: 79,

    riskLevel: "Very High",
    confidence: "High",

    primaryDriver:
      "Repeated serious pipeline releases supported by a strong evidence base.",

    rationale: [
      "8 events are directly classified as pipeline releases.",
      "4 releases are high-severity events.",
      "Recent activity increases inspection priority.",
      "17 relevant events provide a strong evidence base.",
    ],

    recommendedAction:
      "Prioritize for engineering review and inspection planning.",
  },

  {
    id: 7,
    name: "Corridor G",

    relevantEvents: 13,

    pipelineReleases: 6,
    facilityFires: 2,
    limitBreaches: 4,
    otherEvents: 1,

    seriousReleases: 3,
    recentEvents: 5,

    totalReleaseVolume: 18700,

    severity: 75,
    pipelineRelevance: 84,
    frequency: 67,
    recency: 78,
    releaseVolume: 69,
    exposure: 73,

    riskLevel: "High",
    confidence: "High",

    primaryDriver:
      "Repeated pipeline-relevant releases with recent activity.",

    rationale: [
      "6 pipeline releases are present.",
      "3 releases are considered serious.",
      "5 relevant events occurred recently.",
      "Evidence is supported by 13 relevant events.",
    ],

    recommendedAction:
      "Include in the near-term engineering review shortlist.",
  },

  {
    id: 8,
    name: "Corridor H",

    relevantEvents: 4,

    pipelineReleases: 4,
    facilityFires: 0,
    limitBreaches: 0,
    otherEvents: 0,

    seriousReleases: 3,
    recentEvents: 3,

    totalReleaseVolume: 22100,

    severity: 90,
    pipelineRelevance: 100,
    frequency: 35,
    recency: 89,
    releaseVolume: 79,
    exposure: 77,

    riskLevel: "Very High",
    confidence: "Low",

    primaryDriver:
      "Few events, but most are serious and directly pipeline-related.",

    rationale: [
      "All 4 events are pipeline releases.",
      "3 are high-severity releases.",
      "Most occurred recently.",
      "Only 4 events support the ranking, reducing confidence.",
    ],

    recommendedAction:
      "Escalate for review while acknowledging the limited evidence base.",
  },

  {
    id: 9,
    name: "Corridor I",

    relevantEvents: 22,

    pipelineReleases: 7,
    facilityFires: 5,
    limitBreaches: 8,
    otherEvents: 2,

    seriousReleases: 2,
    recentEvents: 8,

    totalReleaseVolume: 14300,

    severity: 68,
    pipelineRelevance: 70,
    frequency: 84,
    recency: 80,
    releaseVolume: 62,
    exposure: 71,

    riskLevel: "High",
    confidence: "High",

    primaryDriver:
      "Large evidence base and repeated recent events.",

    rationale: [
      "22 relevant events provide strong evidence.",
      "7 events are pipeline releases.",
      "Recent event frequency is elevated.",
      "Severity is lower than the highest-ranked corridors.",
    ],

    recommendedAction:
      "Review repeated-event pattern and determine whether inspection is warranted.",
  },

  {
    id: 10,
    name: "Corridor J",

    relevantEvents: 9,

    pipelineReleases: 5,
    facilityFires: 1,
    limitBreaches: 2,
    otherEvents: 1,

    seriousReleases: 2,
    recentEvents: 4,

    totalReleaseVolume: 12100,

    severity: 71,
    pipelineRelevance: 82,
    frequency: 58,
    recency: 73,
    releaseVolume: 59,
    exposure: 69,

    riskLevel: "High",
    confidence: "Moderate",

    primaryDriver:
      "Pipeline-relevant events combined with moderate severity.",

    rationale: [
      "5 events are pipeline releases.",
      "2 are serious releases.",
      "Recent activity remains relevant.",
      "Evidence base is moderate.",
    ],

    recommendedAction:
      "Retain on the inspection shortlist for engineering review.",
  },

  {
    id: 11,
    name: "Corridor K",

    relevantEvents: 16,

    pipelineReleases: 4,
    facilityFires: 5,
    limitBreaches: 6,
    otherEvents: 1,

    seriousReleases: 1,
    recentEvents: 5,

    totalReleaseVolume: 6900,

    severity: 55,
    pipelineRelevance: 57,
    frequency: 72,
    recency: 65,
    releaseVolume: 40,
    exposure: 61,

    riskLevel: "Moderate",
    confidence: "High",

    primaryDriver:
      "Repeated events but comparatively low pipeline-release severity.",

    rationale: [
      "16 events provide a strong evidence base.",
      "Many events are contextual rather than pipeline releases.",
      "Only 1 serious release is present.",
    ],

    recommendedAction:
      "Monitor contextual events before escalating inspection priority.",
  },

  {
    id: 12,
    name: "Corridor L",

    relevantEvents: 7,

    pipelineReleases: 4,
    facilityFires: 1,
    limitBreaches: 1,
    otherEvents: 1,

    seriousReleases: 2,
    recentEvents: 3,

    totalReleaseVolume: 9700,

    severity: 66,
    pipelineRelevance: 76,
    frequency: 50,
    recency: 69,
    releaseVolume: 52,
    exposure: 64,

    riskLevel: "Moderate",
    confidence: "Moderate",

    primaryDriver:
      "Moderate pipeline relevance with several meaningful releases.",

    rationale: [
      "4 of 7 events are pipeline releases.",
      "2 releases are serious.",
      "Evidence base remains moderate.",
    ],

    recommendedAction:
      "Maintain on the inspection watchlist.",
  },

  {
    id: 13,
    name: "Corridor M",

    relevantEvents: 25,

    pipelineReleases: 5,
    facilityFires: 8,
    limitBreaches: 10,
    otherEvents: 2,

    seriousReleases: 1,
    recentEvents: 7,

    totalReleaseVolume: 6100,

    severity: 49,
    pipelineRelevance: 51,
    frequency: 88,
    recency: 70,
    releaseVolume: 37,
    exposure: 58,

    riskLevel: "Moderate",
    confidence: "High",

    primaryDriver:
      "High event count dominated by contextual facility and operating events.",

    rationale: [
      "25 events create a strong evidence base.",
      "Most events are not pipeline releases.",
      "Only 1 serious release is present.",
      "Raw incident count overstates pipeline-specific concern.",
    ],

    recommendedAction:
      "Review contextual events but do not prioritize solely because of incident count.",
  },

  {
    id: 14,
    name: "Corridor N",

    relevantEvents: 12,

    pipelineReleases: 3,
    facilityFires: 3,
    limitBreaches: 5,
    otherEvents: 1,

    seriousReleases: 1,
    recentEvents: 3,

    totalReleaseVolume: 5300,

    severity: 47,
    pipelineRelevance: 55,
    frequency: 63,
    recency: 54,
    releaseVolume: 35,
    exposure: 60,

    riskLevel: "Moderate",
    confidence: "Moderate",

    primaryDriver:
      "Moderate evidence without a strong high-severity release pattern.",

    rationale: [
      "12 relevant events are recorded.",
      "Only 3 are pipeline releases.",
      "1 serious release is present.",
      "Recent activity is comparatively limited.",
    ],

    recommendedAction:
      "Monitor and reassess as new evidence becomes available.",
  },

  {
    id: 15,
    name: "Corridor O",

    relevantEvents: 5,

    pipelineReleases: 2,
    facilityFires: 1,
    limitBreaches: 2,
    otherEvents: 0,

    seriousReleases: 0,
    recentEvents: 1,

    totalReleaseVolume: 2800,

    severity: 36,
    pipelineRelevance: 48,
    frequency: 40,
    recency: 38,
    releaseVolume: 25,
    exposure: 54,

    riskLevel: "Low",
    confidence: "Low",

    primaryDriver:
      "Limited evidence and no identified serious-release pattern.",

    rationale: [
      "Only 5 relevant events are available.",
      "2 events are pipeline releases.",
      "No serious releases are identified.",
      "Little recent activity is present.",
    ],

    recommendedAction:
      "Lower inspection priority unless additional evidence or engineering concerns emerge.",
  },
];

/*
============================================================
HELPER FUNCTIONS
============================================================
*/

function getRiskLevel(score: number): RiskLevel {
  if (score >= 80) {
    return "Very High";
  }

  if (score >= 70) {
    return "High";
  }

  if (score >= 50) {
    return "Moderate";
  }

  return "Low";
}

function riskBadge(level: RiskLevel) {
  switch (level) {
    case "Very High":
      return "border-red-500/30 bg-red-500/10 text-red-400";

    case "High":
      return "border-orange-500/30 bg-orange-500/10 text-orange-400";

    case "Moderate":
      return "border-yellow-500/30 bg-yellow-500/10 text-yellow-400";

    default:
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-400";
  }
}

function confidenceBadge(
  confidence: ConfidenceLevel
) {
  switch (confidence) {
    case "High":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-400";

    case "Moderate":
      return "border-yellow-500/30 bg-yellow-500/10 text-yellow-400";

    default:
      return "border-orange-500/30 bg-orange-500/10 text-orange-400";
  }
}

function factorColor(key: keyof ModelWeights) {
  switch (key) {
    case "severity":
      return "bg-red-500";

    case "pipelineRelevance":
      return "bg-purple-500";

    case "frequency":
      return "bg-blue-500";

    case "recency":
      return "bg-amber-400";

    case "releaseVolume":
      return "bg-cyan-400";

    default:
      return "bg-emerald-400";
  }
}

/*
============================================================
MAIN PAGE
============================================================
*/

export default function Home() {
  /*
  ==========================================================
  SLIDER WEIGHTS
  ==========================================================

  Default model:

  Severity             30%
  Pipeline Relevance   20%
  Frequency            15%
  Recency              15%
  Release Volume       10%
  Exposure             10%
  */

  const [weights, setWeights] =
    useState<ModelWeights>({
      severity: 30,
      pipelineRelevance: 20,
      frequency: 15,
      recency: 15,
      releaseVolume: 10,
      exposure: 10,
    });

  /*
    Selected corridor ID rather than storing the whole object.

    This makes sure the selected corridor's score changes
    immediately when the sliders move.
  */

  const [selectedCorridorId, setSelectedCorridorId] =
    useState(2);

  /*
  ==========================================================
  TOTAL WEIGHT
  ==========================================================
  */

  const totalWeight =
    weights.severity +
    weights.pipelineRelevance +
    weights.frequency +
    weights.recency +
    weights.releaseVolume +
    weights.exposure;

  /*
  ==========================================================
  UPDATE A SLIDER
  ==========================================================
  */

  function updateWeight(
    key: keyof ModelWeights,
    value: number
  ) {
    setWeights((currentWeights) => ({
      ...currentWeights,

      [key]: value,
    }));
  }

  /*
  ==========================================================
  RESET SLIDERS
  ==========================================================
  */

  function resetWeights() {
    setWeights({
      severity: 30,
      pipelineRelevance: 20,
      frequency: 15,
      recency: 15,
      releaseVolume: 10,
      exposure: 10,
    });
  }

  /*
  ==========================================================
  CALCULATE TOP 15
  ==========================================================

  The ranking is recalculated every time a slider changes.

  Formula:

  Score =
  (
    Severity × Severity Weight
    +
    Pipeline Relevance × Pipeline Relevance Weight
    +
    Frequency × Frequency Weight
    +
    Recency × Recency Weight
    +
    Release Volume × Release Volume Weight
    +
    Exposure × Exposure Weight
  )
  /
  Total Weight

  This also means the model still works if the sliders
  temporarily do not add up to exactly 100%.
  */

  const priorities = useMemo(() => {
    return corridors
      .map((corridor) => {
        /*
          Prevent division by zero if every slider is zero.
        */

        if (totalWeight === 0) {
          return {
            ...corridor,

            priorityScore: 0,

            calculatedRiskLevel:
              "Low" as RiskLevel,
          };
        }

        const score =
          (
            corridor.severity *
              weights.severity +

            corridor.pipelineRelevance *
              weights.pipelineRelevance +

            corridor.frequency *
              weights.frequency +

            corridor.recency *
              weights.recency +

            corridor.releaseVolume *
              weights.releaseVolume +

            corridor.exposure *
              weights.exposure
          ) / totalWeight;

        const roundedScore =
          Math.round(score * 10) / 10;

        return {
          ...corridor,

          priorityScore: roundedScore,

          calculatedRiskLevel:
            getRiskLevel(roundedScore),
        };
      })

      /*
        Highest risk first.
      */

      .sort(
        (a, b) =>
          b.priorityScore -
          a.priorityScore
      )

      /*
        Only show the Top 15.
      */

      .slice(0, 15);
  }, [weights, totalWeight]);

  /*
  ==========================================================
  SELECTED CORRIDOR
  ==========================================================
  */

  const selectedCorridor =
    priorities.find(
      (corridor) =>
        corridor.id ===
        selectedCorridorId
    ) ?? priorities[0];

  /*
  ==========================================================
  RISK BREAKDOWN
  ==========================================================
  */

  const breakdown = [
    {
      key: "severity" as const,

      label: "Severity / Consequence",

      value:
        selectedCorridor.severity,

      weight:
        weights.severity,
    },

    {
      key: "pipelineRelevance" as const,

      label: "Pipeline Relevance",

      value:
        selectedCorridor.pipelineRelevance,

      weight:
        weights.pipelineRelevance,
    },

    {
      key: "frequency" as const,

      label: "Frequency",

      value:
        selectedCorridor.frequency,

      weight:
        weights.frequency,
    },

    {
      key: "recency" as const,

      label: "Recency",

      value:
        selectedCorridor.recency,

      weight:
        weights.recency,
    },

    {
      key: "releaseVolume" as const,

      label: "Release Volume",

      value:
        selectedCorridor.releaseVolume,

      weight:
        weights.releaseVolume,
    },

    {
      key: "exposure" as const,

      label: "Exposure / Proximity",

      value:
        selectedCorridor.exposure,

      weight:
        weights.exposure,
    },
  ];

  return (
    <main className="min-h-screen bg-slate-950 p-4 text-slate-100 md:p-8">

      <div className="mx-auto max-w-7xl overflow-hidden rounded-2xl border border-slate-700/70 bg-slate-900 shadow-2xl">

        {/* ==================================================
            HEADER
        ================================================== */}

        <header className="border-b border-slate-700 bg-gradient-to-r from-blue-950 via-slate-900 to-teal-950 px-8 py-7">

          <p className="mb-2 text-sm font-semibold uppercase tracking-[0.2em] text-cyan-400">
            Inspection Decision Support
          </p>

          <h1 className="text-2xl font-bold text-white md:text-3xl">
            Alberta Pipeline Inspection Prioritization
          </h1>

          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            Identify which pipeline corridors warrant investigation first,
            why they ranked highly, and how strong the supporting evidence is.
          </p>

          <div className="mt-5 max-w-4xl rounded-lg border border-blue-800/60 bg-blue-950/40 px-4 py-3 text-sm leading-6 text-blue-200">

            <strong>
              Decision-support tool:
            </strong>{" "}

            Rankings identify corridors that may warrant further engineering
            review. They do not certify pipeline safety or replace integrity
            engineering judgment.

          </div>

        </header>

        {/* ==================================================
            OPERATIONAL QUESTION
        ================================================== */}

        <section className="border-b border-slate-700 px-8 py-7">

          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">
            Operational Question
          </p>

          <h2 className="mt-2 max-w-4xl text-xl font-bold leading-8 text-white md:text-2xl">
            Given limited inspection resources, which pipeline corridors
            should we investigate first this week, and what evidence supports
            that decision?
          </h2>

        </section>

        {/* ==================================================
            PRIORITIZATION MODEL
        ================================================== */}

        <section className="border-b border-slate-700 px-8 py-8">

          <div className="mb-7">

            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-cyan-400">
              Prioritization Model
            </p>

            <h2 className="text-xl font-bold text-white">
              Inspection Risk Model
            </h2>

            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              Incident count alone does not determine priority. Severity,
              pipeline relevance, frequency, recency, release volume, and
              exposure are considered separately.
            </p>

          </div>

          {/* FORMULA */}

          <div className="mb-8 rounded-xl border border-slate-700 bg-slate-800/70 p-5">

            <p className="font-semibold text-slate-200">
              Inspection Priority Score =
            </p>

            <p className="mt-2 text-sm leading-7 text-slate-400 md:text-base">

              {weights.severity}% Severity +

              {" "}

              {weights.pipelineRelevance}% Pipeline Relevance +

              {" "}

              {weights.frequency}% Frequency +

              {" "}

              {weights.recency}% Recency +

              {" "}

              {weights.releaseVolume}% Release Volume +

              {" "}

              {weights.exposure}% Exposure

            </p>

          </div>

          {/* ==================================================
              SLIDERS
          ================================================== */}

          <div className="rounded-xl border border-cyan-900/60 bg-slate-800/50 p-6">

            <div className="flex flex-wrap items-start justify-between gap-4">

              <div>

                <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">
                  Scenario Testing
                </p>

                <h3 className="mt-1 text-lg font-bold text-white">
                  Adjust Risk Weights
                </h3>

                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                  Change the importance of each factor to test different
                  inspection strategies. The Top 15 rankings automatically
                  recalculate and reorder.
                </p>

              </div>

              <button
                type="button"

                onClick={resetWeights}

                className="rounded-lg border border-slate-600 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-300 transition hover:border-cyan-500 hover:text-cyan-300"
              >
                Reset Weights
              </button>

            </div>

            {/* TOTAL */}

            <div className="mt-6 flex items-center justify-between rounded-lg border border-slate-700 bg-slate-900/70 px-4 py-3">

              <div>

                <p className="text-sm font-medium text-slate-300">
                  Total Weight
                </p>

                <p className="mt-1 text-xs text-slate-500">
                  Rankings normalize automatically.
                </p>

              </div>

              <span
                className={`text-xl font-bold ${
                  totalWeight === 100
                    ? "text-emerald-400"
                    : "text-amber-400"
                }`}
              >
                {totalWeight}%
              </span>

            </div>

            {totalWeight !== 100 && (

              <div className="mt-3 rounded-lg border border-amber-700/40 bg-amber-950/20 px-4 py-3 text-xs leading-5 text-amber-300">

                The weights currently total {totalWeight}%. The model
                automatically normalizes them, so rankings can still be
                compared. Reset the sliders to return to the default 100%
                model.

              </div>

            )}

            {/* SLIDER GRID */}

            <div className="mt-8 grid gap-x-10 gap-y-8 md:grid-cols-2">

              {/* =============================================
                  SEVERITY
              ============================================= */}

              <div>

                <div className="mb-3 flex items-start justify-between gap-4">

                  <div>

                    <p className="font-medium text-slate-200">
                      Severity / Consequence
                    </p>

                    <p className="mt-1 text-xs text-slate-500">
                      How serious were the events?
                    </p>

                  </div>

                  <span className="rounded-md bg-red-500/10 px-2 py-1 font-bold text-red-400">
                    {weights.severity}%
                  </span>

                </div>

                <input
                  type="range"
                  min="0"
                  max="50"
                  step="1"

                  value={
                    weights.severity
                  }

                  onChange={(event) =>
                    updateWeight(
                      "severity",
                      Number(
                        event.target.value
                      )
                    )
                  }

                  className="w-full cursor-pointer accent-red-500"
                />

                <div className="mt-1 flex justify-between text-[10px] text-slate-600">
                  <span>0%</span>
                  <span>50%</span>
                </div>

              </div>

              {/* =============================================
                  PIPELINE RELEVANCE
              ============================================= */}

              <div>

                <div className="mb-3 flex items-start justify-between gap-4">

                  <div>

                    <p className="font-medium text-slate-200">
                      Pipeline Relevance
                    </p>

                    <p className="mt-1 text-xs text-slate-500">
                      How directly is the event related to the pipeline?
                    </p>

                  </div>

                  <span className="rounded-md bg-purple-500/10 px-2 py-1 font-bold text-purple-400">
                    {weights.pipelineRelevance}%
                  </span>

                </div>

                <input
                  type="range"
                  min="0"
                  max="50"
                  step="1"

                  value={
                    weights.pipelineRelevance
                  }

                  onChange={(event) =>
                    updateWeight(
                      "pipelineRelevance",
                      Number(
                        event.target.value
                      )
                    )
                  }

                  className="w-full cursor-pointer accent-purple-500"
                />

                <div className="mt-1 flex justify-between text-[10px] text-slate-600">
                  <span>0%</span>
                  <span>50%</span>
                </div>

              </div>

              {/* =============================================
                  FREQUENCY
              ============================================= */}

              <div>

                <div className="mb-3 flex items-start justify-between gap-4">

                  <div>

                    <p className="font-medium text-slate-200">
                      Frequency
                    </p>

                    <p className="mt-1 text-xs text-slate-500">
                      How often have relevant events occurred?
                    </p>

                  </div>

                  <span className="rounded-md bg-blue-500/10 px-2 py-1 font-bold text-blue-400">
                    {weights.frequency}%
                  </span>

                </div>

                <input
                  type="range"
                  min="0"
                  max="50"
                  step="1"

                  value={
                    weights.frequency
                  }

                  onChange={(event) =>
                    updateWeight(
                      "frequency",
                      Number(
                        event.target.value
                      )
                    )
                  }

                  className="w-full cursor-pointer accent-blue-500"
                />

                <div className="mt-1 flex justify-between text-[10px] text-slate-600">
                  <span>0%</span>
                  <span>50%</span>
                </div>

              </div>

              {/* =============================================
                  RECENCY
              ============================================= */}

              <div>

                <div className="mb-3 flex items-start justify-between gap-4">

                  <div>

                    <p className="font-medium text-slate-200">
                      Recency
                    </p>

                    <p className="mt-1 text-xs text-slate-500">
                      How recently did the events occur?
                    </p>

                  </div>

                  <span className="rounded-md bg-amber-500/10 px-2 py-1 font-bold text-amber-400">
                    {weights.recency}%
                  </span>

                </div>

                <input
                  type="range"
                  min="0"
                  max="50"
                  step="1"

                  value={
                    weights.recency
                  }

                  onChange={(event) =>
                    updateWeight(
                      "recency",
                      Number(
                        event.target.value
                      )
                    )
                  }

                  className="w-full cursor-pointer accent-amber-400"
                />

                <div className="mt-1 flex justify-between text-[10px] text-slate-600">
                  <span>0%</span>
                  <span>50%</span>
                </div>

              </div>

              {/* =============================================
                  RELEASE VOLUME
              ============================================= */}

              <div>

                <div className="mb-3 flex items-start justify-between gap-4">

                  <div>

                    <p className="font-medium text-slate-200">
                      Release Volume
                    </p>

                    <p className="mt-1 text-xs text-slate-500">
                      How significant was the released volume?
                    </p>

                  </div>

                  <span className="rounded-md bg-cyan-500/10 px-2 py-1 font-bold text-cyan-400">
                    {weights.releaseVolume}%
                  </span>

                </div>

                <input
                  type="range"
                  min="0"
                  max="50"
                  step="1"

                  value={
                    weights.releaseVolume
                  }

                  onChange={(event) =>
                    updateWeight(
                      "releaseVolume",
                      Number(
                        event.target.value
                      )
                    )
                  }

                  className="w-full cursor-pointer accent-cyan-400"
                />

                <div className="mt-1 flex justify-between text-[10px] text-slate-600">
                  <span>0%</span>
                  <span>50%</span>
                </div>

              </div>

              {/* =============================================
                  EXPOSURE
              ============================================= */}

              <div>

                <div className="mb-3 flex items-start justify-between gap-4">

                  <div>

                    <p className="font-medium text-slate-200">
                      Exposure / Proximity
                    </p>

                    <p className="mt-1 text-xs text-slate-500">
                      Potential impact on people, infrastructure, or the
                      environment.
                    </p>

                  </div>

                  <span className="rounded-md bg-emerald-500/10 px-2 py-1 font-bold text-emerald-400">
                    {weights.exposure}%
                  </span>

                </div>

                <input
                  type="range"
                  min="0"
                  max="50"
                  step="1"

                  value={
                    weights.exposure
                  }

                  onChange={(event) =>
                    updateWeight(
                      "exposure",
                      Number(
                        event.target.value
                      )
                    )
                  }

                  className="w-full cursor-pointer accent-emerald-500"
                />

                <div className="mt-1 flex justify-between text-[10px] text-slate-600">
                  <span>0%</span>
                  <span>50%</span>
                </div>

              </div>

            </div>

          </div>

          {/* SCREENING THRESHOLD */}

          <div className="mt-6 rounded-xl border border-amber-700/40 bg-amber-950/20 p-5">

            <p className="font-semibold text-amber-300">
              Release-volume screening flag
            </p>

            <p className="mt-2 text-sm leading-6 text-slate-400">
              10,000 m³ may be used as an initial screening flag for larger
              gas releases. It is not a universal definition of a serious
              incident. Severity should also consider composition, location,
              duration, ignition potential, operating conditions, exposure,
              and other available incident information.
            </p>

          </div>

        </section>

        {/* ==================================================
            MAP + TOP 15
        ================================================== */}

        <section className="grid border-b border-slate-700 lg:grid-cols-[1.2fr_1fr]">

          {/* MAP */}

          <div className="border-b border-slate-700 p-8 lg:border-b-0 lg:border-r">

            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-cyan-400">
              Geographic Evidence
            </p>

            <h2 className="text-xl font-bold text-white">
              Alberta Pipeline Map
            </h2>

            <p className="mb-6 mt-2 text-sm leading-6 text-slate-400">
              Pipeline geometry comes from the GIS layer. Risk overlays are
              displayed only when incident evidence has been associated with
              an asset.
            </p>

            <div className="overflow-hidden rounded-xl border border-slate-700">
              <PipelineMap />
            </div>

            <div className="mt-4 grid gap-2 text-xs text-slate-400 sm:grid-cols-3">

              <div>
                <strong className="text-slate-300">
                  Line colour:
                </strong>{" "}
                inspection risk
              </div>

              <div>
                <strong className="text-slate-300">
                  Marker size:
                </strong>{" "}
                evidence volume
              </div>

              <div>
                <strong className="text-slate-300">
                  Line style:
                </strong>{" "}
                confidence
              </div>

            </div>

          </div>

          {/* TOP 15 */}

          <div className="p-8">

            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-cyan-400">
              Inspection Planning
            </p>

            <h2 className="text-xl font-bold text-white">
              Top 15 Inspection Priorities
            </h2>

            <p className="mt-2 text-sm leading-6 text-slate-400">
              Move the sliders above and watch the rankings change.
            </p>

            <div className="mt-6 overflow-x-auto rounded-xl border border-slate-700">

              <div className="min-w-[600px]">

                {/* TABLE HEADER */}

                <div className="grid grid-cols-[45px_1fr_65px_80px_90px] bg-slate-800 px-3 py-3 text-xs font-semibold uppercase tracking-wide text-slate-400">

                  <span>#</span>

                  <span>Corridor</span>

                  <span>Score</span>

                  <span>Evidence</span>

                  <span>Confidence</span>

                </div>

                {/* ROWS */}

                {priorities.map(
                  (item, index) => {

                    const selected =
                      item.id ===
                      selectedCorridor.id;

                    return (

                      <button
                        key={item.id}

                        type="button"

                        onClick={() =>
                          setSelectedCorridorId(
                            item.id
                          )
                        }

                        className={`grid w-full grid-cols-[45px_1fr_65px_80px_90px] items-center border-t border-slate-700/70 px-3 py-4 text-left transition ${
                          selected
                            ? "bg-cyan-950/50"
                            : "hover:bg-slate-800/70"
                        }`}
                      >

                        {/* RANK */}

                        <span className="font-bold text-slate-400">
                          #{index + 1}
                        </span>

                        {/* CORRIDOR */}

                        <div className="pr-3">

                          <div className="flex flex-wrap items-center gap-2">

                            <p
                              className={`font-medium ${
                                selected
                                  ? "text-cyan-300"
                                  : "text-slate-200"
                              }`}
                            >
                              {item.name}
                            </p>

                            <span
                              className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold ${riskBadge(
                                item.calculatedRiskLevel
                              )}`}
                            >
                              {item.calculatedRiskLevel}
                            </span>

                          </div>

                          <p className="mt-1 truncate text-[11px] text-slate-500">
                            {item.primaryDriver}
                          </p>

                        </div>

                        {/* SCORE */}

                        <span className="font-bold text-white">
                          {item.priorityScore}
                        </span>

                        {/* EVIDENCE */}

                        <span className="text-xs text-slate-300">
                          {item.relevantEvents} events
                        </span>

                        {/* CONFIDENCE */}

                        <span
                          className={`w-fit rounded-full border px-2 py-1 text-[10px] font-semibold ${confidenceBadge(
                            item.confidence
                          )}`}
                        >
                          {item.confidence}
                        </span>

                      </button>

                    );
                  }
                )}

              </div>

            </div>

          </div>

        </section>

        {/* ==================================================
            WHY COUNT ALONE FAILS
        ================================================== */}

        <section className="border-b border-slate-700 px-8 py-10">

          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">
            Why Count Alone Fails
          </p>

          <h2 className="mt-1 text-xl font-bold text-white">
            30 Minor Events vs. 6 Serious Releases
          </h2>

          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            More incidents do not automatically mean greater inspection
            priority. Event severity and relevance to the pipeline matter.
          </p>

          <div className="mt-7 grid gap-6 md:grid-cols-2">

            {/* A */}

            <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-6">

              <p className="font-bold text-white">
                Corridor A
              </p>

              <p className="mt-1 text-sm text-slate-400">
                30 relevant events
              </p>

              <div className="mt-5 space-y-2 text-sm text-slate-400">

                <p>14 facility fires</p>

                <p>10 limit breaches</p>

                <p>4 pipeline releases</p>

                <p>1 serious release</p>

              </div>

              <div className="mt-5 rounded-lg bg-yellow-500/10 p-3 text-sm text-yellow-300">
                Many events — but much of the evidence is contextual.
              </div>

            </div>

            {/* B */}

            <div className="rounded-xl border border-red-800/50 bg-red-950/20 p-6">

              <p className="font-bold text-white">
                Corridor B
              </p>

              <p className="mt-1 text-sm text-slate-400">
                6 relevant events
              </p>

              <div className="mt-5 space-y-2 text-sm text-slate-400">

                <p>6 pipeline releases</p>

                <p>5 serious releases</p>

                <p>4 recent events</p>

                <p>
                  48,500 m³ cumulative release volume
                </p>

              </div>

              <div className="mt-5 rounded-lg bg-red-500/10 p-3 text-sm text-red-300">
                Fewer events — but much greater severity and pipeline
                relevance.
              </div>

            </div>

          </div>

          <div className="mt-6 rounded-xl border border-cyan-800/40 bg-cyan-950/20 p-5">

            <p className="font-semibold text-cyan-300">
              Inspection decision
            </p>

            <p className="mt-2 text-sm leading-6 text-slate-300">
              The model can prioritize Corridor B even though Corridor A has
              five times as many events. Facility fires and limit breaches
              remain useful contextual evidence, but they are not
              automatically treated as pipeline failures.
            </p>

          </div>

        </section>

        {/* ==================================================
            SELECTED CORRIDOR
        ================================================== */}

        <section className="px-8 py-10">

          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">
            Decision Explanation
          </p>

          <h2 className="mt-1 text-xl font-bold text-white">
            Selected Corridor: {selectedCorridor.name}
          </h2>

          {/* RISK / EVIDENCE / CONFIDENCE */}

          <div className="mt-7 grid gap-4 md:grid-cols-3">

            {/* RISK */}

            <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-5">

              <p className="text-xs uppercase tracking-wider text-slate-500">
                Calculated Risk
              </p>

              <p className="mt-2 text-3xl font-bold text-white">
                {selectedCorridor.priorityScore}
              </p>

              <p className="mt-1 text-xs text-slate-500">
                out of 100
              </p>

              <span
                className={`mt-3 inline-block rounded-full border px-3 py-1 text-xs font-semibold ${riskBadge(
                  selectedCorridor.calculatedRiskLevel
                )}`}
              >
                {selectedCorridor.calculatedRiskLevel}
              </span>

            </div>

            {/* EVIDENCE */}

            <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-5">

              <p className="text-xs uppercase tracking-wider text-slate-500">
                Evidence
              </p>

              <p className="mt-2 text-3xl font-bold text-white">
                {selectedCorridor.relevantEvents}
              </p>

              <p className="mt-2 text-sm text-slate-400">
                relevant events
              </p>

            </div>

            {/* CONFIDENCE */}

            <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-5">

              <p className="text-xs uppercase tracking-wider text-slate-500">
                Confidence
              </p>

              <span
                className={`mt-3 inline-block rounded-full border px-3 py-1 text-sm font-semibold ${confidenceBadge(
                  selectedCorridor.confidence
                )}`}
              >
                {selectedCorridor.confidence}
              </span>

              {selectedCorridor.confidence ===
                "Low" && (

                <p className="mt-3 text-xs leading-5 text-orange-300">
                  This risk signal is supported by a limited evidence base.
                </p>

              )}

            </div>

          </div>

          {/* EVIDENCE + RATIONALE */}

          <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.3fr]">

            {/* EVIDENCE */}

            <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-6">

              <h3 className="font-semibold text-white">
                Evidence Breakdown
              </h3>

              <div className="mt-5 space-y-3 text-sm">

                {[
                  [
                    "Pipeline Releases",
                    selectedCorridor.pipelineReleases,
                  ],

                  [
                    "Facility Fires",
                    selectedCorridor.facilityFires,
                  ],

                  [
                    "Limit Breaches",
                    selectedCorridor.limitBreaches,
                  ],

                  [
                    "Other Events",
                    selectedCorridor.otherEvents,
                  ],

                  [
                    "Serious Releases",
                    selectedCorridor.seriousReleases,
                  ],

                  [
                    "Recent Events",
                    selectedCorridor.recentEvents,
                  ],
                ].map(([label, value]) => (

                  <div
                    key={String(label)}
                    className="flex justify-between border-b border-slate-700/60 pb-3"
                  >

                    <span className="text-slate-400">
                      {label}
                    </span>

                    <strong className="text-white">
                      {value}
                    </strong>

                  </div>

                ))}

                <div className="flex justify-between pt-1">

                  <span className="text-slate-400">
                    Total Release Volume
                  </span>

                  <strong className="text-white">
                    {selectedCorridor.totalReleaseVolume.toLocaleString()} m³
                  </strong>

                </div>

              </div>

            </div>

            {/* WHY */}

            <div className="rounded-xl border border-cyan-800/50 bg-gradient-to-br from-cyan-950/40 to-blue-950/40 p-6">

              <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">
                Primary Risk Driver
              </p>

              <p className="mt-3 text-lg font-semibold leading-7 text-white">
                {selectedCorridor.primaryDriver}
              </p>

              <div className="mt-6">

                <p className="font-semibold text-slate-200">
                  Why did it rank here?
                </p>

                <ul className="mt-3 space-y-3">

                  {selectedCorridor.rationale.map(
                    (reason) => (

                      <li
                        key={reason}
                        className="flex gap-3 text-sm leading-6 text-slate-400"
                      >

                        <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400" />

                        {reason}

                      </li>

                    )
                  )}

                </ul>

              </div>

              <div className="mt-6 border-t border-cyan-900 pt-5">

                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Recommended Action
                </p>

                <p className="mt-2 text-sm leading-6 text-slate-300">
                  {selectedCorridor.recommendedAction}
                </p>

              </div>

            </div>

          </div>

          {/* =================================================
              LIVE RISK FACTOR BREAKDOWN
          ================================================= */}

          <div className="mt-6 rounded-xl border border-slate-700 bg-slate-800/50 p-6">

            <div className="flex flex-wrap items-center justify-between gap-4">

              <div>

                <h3 className="font-semibold text-white">
                  Live Risk Factor Breakdown
                </h3>

                <p className="mt-1 text-sm text-slate-500">
                  Contributions update when the sliders change.
                </p>

              </div>

              <span className="text-2xl font-bold text-cyan-400">
                {selectedCorridor.priorityScore}
              </span>

            </div>

            <div className="mt-6 grid gap-x-8 gap-y-6 md:grid-cols-2">

              {breakdown.map((item) => {

                const contribution =
                  totalWeight === 0
                    ? 0
                    : (
                        item.value *
                        item.weight
                      ) / totalWeight;

                return (

                  <div key={item.key}>

                    <div className="flex justify-between gap-4">

                      <span className="text-sm text-slate-400">
                        {item.label}
                      </span>

                      <strong>
                        {item.value}/100
                      </strong>

                    </div>

                    <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-700">

                      <div
                        className={`h-full rounded-full ${factorColor(
                          item.key
                        )}`}

                        style={{
                          width: `${item.value}%`,
                        }}
                      />

                    </div>

                    <div className="mt-2 flex justify-between text-xs text-slate-500">

                      <span>
                        Current weight: {item.weight}%
                      </span>

                      <span>
                        Score contribution:{" "}
                        {contribution.toFixed(1)}
                      </span>

                    </div>

                  </div>

                );
              })}

            </div>

          </div>

          {/* INTERPRETATION */}

          <div className="mt-6 rounded-xl border border-slate-700 bg-slate-950/60 p-5 text-sm leading-6 text-slate-400">

            <strong className="text-slate-200">
              Interpretation:
            </strong>{" "}

            Facility fires and operating-limit breaches may contribute
            contextual evidence, but they should not automatically be treated
            as pipeline failures. Geographic proximity alone also does not
            establish that two incidents belong to the same terminal,
            facility, or pipeline segment. Asset identifiers and incident
            metadata should be verified before aggregation.

          </div>

          {/* PROTOTYPE WARNING */}

          <div className="mt-4 rounded-xl border border-amber-700/40 bg-amber-950/20 p-5 text-sm leading-6 text-amber-200">

            <strong>
              Prototype note:
            </strong>{" "}

            The Top 15 corridor scores and incident values shown here are
            demonstration data used to illustrate the prioritization method.
            They should be replaced by values calculated from validated
            pipeline and incident datasets before real inspection planning.

          </div>

        </section>

      </div>

    </main>
  );
}