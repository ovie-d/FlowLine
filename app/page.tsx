"use client";

/*
  "use client" tells Next.js that this component needs to run in the browser.

  We need this because we're using:
  - useState
  - click events
  - an interactive map
*/

import dynamic from "next/dynamic";
import { useState } from "react";

/*
  Leaflet depends on browser features such as "window".

  Next.js normally tries to render components on the server first.
  Setting ssr: false prevents the map from being rendered on the server.
*/
const PipelineMap = dynamic(() => import("./PipelineMap"), {
  ssr: false,

  // This appears while the map is loading.
  loading: () => (
    <div className="flex h-[420px] items-center justify-center bg-slate-800 text-slate-400">
      Loading Alberta map...
    </div>
  ),
});

/*
  This TypeScript type describes what information
  every pipeline corridor must contain.

  For example:
  - name
  - number of incidents
  - risk values
  - final priority score
  - geographic coordinates
*/
export type Corridor = {
  id: number;
  name: string;
  incidents: number;

  historicalRisk: number;
  consequence: number;
  recency: number;
  trend: number;

  priorityScore: number;

  change: number;

  /*
    Each coordinate contains:

    [latitude, longitude]

    Multiple coordinates allow us to draw a pipeline line
    across the Alberta map.
  */
  coordinates: [number, number][];
};

/*
  SAMPLE PIPELINE DATA

  Right now this is demonstration data.

  Later, you could replace this with information coming from:
  - an API
  - database
  - CSV
  - Alberta open data
  - pipeline incident datasets
*/
export const corridors: Corridor[] = [
  {
    id: 1,
    name: "Corridor A",

    // Number of historical incidents.
    incidents: 31,

    // Individual risk factors.
    historicalRisk: 88,
    consequence: 86,
    recency: 90,
    trend: 76,

    // Final calculated risk/priority score.
    priorityScore: 87.4,

    // Example ranking movement.
    change: 6,

    /*
      Geographic points used to draw this corridor.

      Edmonton → Red Deer → Calgary
    */
    coordinates: [
      [53.5461, -113.4938],
      [52.2681, -113.8112],
      [51.0447, -114.0719],
    ],
  },

  {
    id: 2,
    name: "Corridor B",
    incidents: 24,

    historicalRisk: 68,
    consequence: 95,
    recency: 82,
    trend: 71,

    priorityScore: 79.2,
    change: 6,

    // Calgary → Medicine Hat area
    coordinates: [
      [51.0447, -114.0719],
      [50.0171, -110.7037],
    ],
  },

  {
    id: 3,
    name: "Corridor C",
    incidents: 19,

    historicalRisk: 72,
    consequence: 78,
    recency: 84,
    trend: 65,

    priorityScore: 79.8,
    change: 4,

    coordinates: [
      [53.5461, -113.4938],
      [53.2784, -110.005],
      [53.585, -113.0],
    ],
  },

  {
    id: 4,
    name: "Corridor D",
    incidents: 15,

    historicalRisk: 65,
    consequence: 85,
    recency: 74,
    trend: 69,

    priorityScore: 77.2,
    change: 2,

    // Calgary → southern Alberta → Lethbridge
    coordinates: [
      [51.0447, -114.0719],
      [50.5642, -111.898],
      [49.6956, -112.8451],
    ],
  },

  {
    id: 5,
    name: "Corridor E",
    incidents: 12,

    historicalRisk: 61,
    consequence: 82,
    recency: 72,
    trend: 67,

    priorityScore: 75.9,
    change: -2,

    // Central Alberta → Jasper area
    coordinates: [
      [52.2681, -113.8112],
      [52.8737, -118.0814],
    ],
  },
];

/*
  This function decides what colour each risk bar should use.

  "type" tells the function which risk category we're displaying.
*/
function riskBarColor(type: string) {
  switch (type) {
    case "historical":
      return "bg-blue-500";

    case "consequence":
      return "bg-red-500";

    case "recency":
      return "bg-amber-400";

    default:
      return "bg-cyan-400";
  }
}

/*
  This is our main homepage component.
*/
export default function Home() {
  /*
    STATE

    selectedCorridor stores which corridor the user currently selected.

    corridors[1] means the SECOND corridor in the array,
    so Corridor B will be selected when the website first loads.
  */
  const [selectedCorridor, setSelectedCorridor] = useState<Corridor>(
    corridors[1]
  );

  /*
    Make a copy of our corridors and sort them from
    highest priority score to lowest priority score.

    Example:

    87.4
    79.8
    79.2
    77.2
    ...
  */
  const priorities = [...corridors].sort(
    (a, b) => b.priorityScore - a.priorityScore
  );

  /*
    Build the risk breakdown for whichever corridor
    the user currently has selected.

    The weights match our risk model:

    Historical = 40%
    Consequence = 30%
    Recency = 20%
    Trend = 10%
  */
  const breakdown = [
    {
      label: "Historical Risk",
      value: selectedCorridor.historicalRisk,
      weight: 0.4,
      type: "historical",
    },
    {
      label: "Consequence",
      value: selectedCorridor.consequence,
      weight: 0.3,
      type: "consequence",
    },
    {
      label: "Recency",
      value: selectedCorridor.recency,
      weight: 0.2,
      type: "recency",
    },
    {
      label: "Trend",
      value: selectedCorridor.trend,
      weight: 0.1,
      type: "trend",
    },
  ];

  return (
    /*
      MAIN PAGE

      bg-slate-950 gives the entire website its dark background.
    */
    <main className="min-h-screen bg-slate-950 p-4 text-slate-100 md:p-8">

      {/* Main dashboard container */}
      <div className="mx-auto max-w-7xl overflow-hidden rounded-2xl border border-slate-700/70 bg-slate-900 shadow-2xl">

        {/* =====================================================
            HEADER
        ====================================================== */}
        <header className="border-b border-slate-700 bg-gradient-to-r from-blue-950 via-slate-900 to-teal-950 px-8 py-7">

          {/* Small heading above the main title */}
          <p className="mb-2 text-sm font-semibold uppercase tracking-[0.2em] text-cyan-400">
            Risk Intelligence
          </p>

          {/* Main website title */}
          <h1 className="text-2xl font-bold text-white md:text-3xl">
            Alberta Pipeline Corridor Risk Dashboard
          </h1>

          {/* Description */}
          <p className="mt-2 text-sm text-slate-400">
            Inspection prioritization and corridor risk analysis
          </p>
        </header>

        {/* =====================================================
            RISK MODEL
        ====================================================== */}
        <section className="border-b border-slate-700 px-8 py-8">

          {/* Section heading */}
          <div className="mb-7">
            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-cyan-400">
              Configuration
            </p>

            <h2 className="text-xl font-bold text-white">
              Risk Model
            </h2>
          </div>

          {/* Display the mathematical risk formula */}
          <div className="mb-8 rounded-xl border border-slate-700 bg-slate-800/70 p-5">
            <p className="font-semibold text-slate-200">
              Priority Score =
            </p>

            <p className="mt-2 text-sm text-slate-400 md:text-base">
              wH(Historical Risk) + wC(Consequence) + wR(Recency) +
              wT(Trend)
            </p>
          </div>

          {/*
            RISK WEIGHT SLIDERS

            Instead of writing four almost-identical slider components,
            we create an array and use .map() to generate them.
          */}
          <div className="space-y-7">
            {[
              ["Historical Incident Risk", "40", "0.40"],
              ["Consequence", "30", "0.30"],
              ["Recency", "20", "0.20"],
              ["Trend", "10", "0.10"],
            ].map(([label, value, decimal]) => (
              <div key={label}>

                {/* Slider name + percentage */}
                <div className="mb-2 flex justify-between">
                  <span className="font-medium text-slate-200">
                    {label}
                  </span>

                  <span className="font-semibold text-cyan-400">
                    {value}%
                  </span>
                </div>

                {/* Slider */}
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    defaultValue={value}
                    className="w-full accent-blue-500"
                  />

                  {/* Decimal representation of weight */}
                  <div className="w-20 rounded-lg border border-slate-600 bg-slate-800 p-2 text-center text-sm text-slate-200">
                    {decimal}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Weight total + reset button */}
          <div className="mt-8 flex flex-col justify-between gap-4 border-t border-slate-800 pt-6 sm:flex-row sm:items-center">

            {/* Shows that all weights currently add up to 100% */}
            <p className="font-semibold text-slate-300">
              Total Weight:{" "}
              <span className="text-emerald-400">
                100% ✓
              </span>
            </p>

            {/* Reset button */}
            <button className="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-medium text-slate-300 transition hover:bg-slate-700">
              Reset to Default
            </button>
          </div>

          {/* Apply weights button */}
          <button className="mt-5 rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white shadow-lg shadow-blue-950/40 transition hover:bg-blue-500">
            Apply Weights
          </button>
        </section>

        {/* =====================================================
            MAP + INSPECTION PRIORITIES
        ====================================================== */}
        <section className="grid border-b border-slate-700 lg:grid-cols-[1.4fr_1fr]">

          {/* ================= MAP ================= */}
          <div className="border-b border-slate-700 p-8 lg:border-b-0 lg:border-r">

            {/* Map heading */}
            <div className="mb-6">
              <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-cyan-400">
                Geographic Overview
              </p>

              <h2 className="text-xl font-bold text-white">
                Alberta Map
              </h2>

              <p className="mt-2 text-sm text-slate-400">
                Circle size represents historical incidents. Corridor colour
                represents calculated risk.
              </p>
            </div>

            {/*
              INTERACTIVE MAP

              We give PipelineMap:

              corridors
              = all pipeline corridor information

              selectedCorridor
              = corridor currently selected

              onSelect
              = allows PipelineMap to change the selected corridor
            */}
            <div className="overflow-hidden rounded-xl border border-slate-700">
              <PipelineMap
              />
            </div>

            {/* MAP LEGEND */}
            <div className="mt-4 flex flex-wrap gap-5 text-xs text-slate-400">

              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-red-500" />
                Very High
              </div>

              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-orange-400" />
                High
              </div>

              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-yellow-400" />
                Medium
              </div>

              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-emerald-400" />
                Lower Risk
              </div>

            </div>
          </div>

          {/* ================= PRIORITIES ================= */}
          <div className="p-8">

            {/* Section title */}
            <div className="mb-6">
              <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-cyan-400">
                Inspection Planning
              </p>

              <h2 className="text-xl font-bold text-white">
                Inspection Priorities
              </h2>
            </div>

            {/* Priority table */}
            <div className="overflow-hidden rounded-xl border border-slate-700">

              {/* Table headings */}
              <div className="grid grid-cols-[55px_1fr_70px] bg-slate-800 px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <span>Rank</span>
                <span>Corridor</span>
                <span>Score</span>
              </div>

              {/*
                Loop through every corridor after sorting them
                from highest risk to lowest risk.
              */}
              {priorities.map((item, index) => {

                // Check whether this row is currently selected.
                const selected =
                  item.id === selectedCorridor.id;

                return (
                  <button
                    key={item.id}

                    /*
                      Clicking a corridor changes selectedCorridor.

                      Because React state changes, the risk breakdown
                      at the bottom automatically updates.
                    */
                    onClick={() => setSelectedCorridor(item)}

                    className={`grid w-full grid-cols-[55px_1fr_70px] items-center border-t border-slate-700/70 px-4 py-4 text-left transition ${
                      selected
                        ? "bg-cyan-950/50"
                        : "hover:bg-slate-800/70"
                    }`}
                  >
                    {/* Ranking */}
                    <span className="font-bold text-slate-400">
                      #{index + 1}
                    </span>

                    {/* Corridor information */}
                    <div>
                      <p
                        className={`font-medium ${
                          selected
                            ? "text-cyan-300"
                            : "text-slate-200"
                        }`}
                      >
                        {item.name}
                      </p>

                      <p className="mt-1 text-xs text-slate-500">
                        {item.incidents} incidents
                      </p>
                    </div>

                    {/* Priority score */}
                    <span className="font-bold text-white">
                      {item.priorityScore}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Currently selected corridor */}
            <div className="mt-6 rounded-xl border border-slate-700 bg-slate-800/50 p-5">
              <p className="text-xs uppercase tracking-wider text-slate-500">
                Selected
              </p>

              <p className="mt-1 text-lg font-bold text-cyan-400">
                {selectedCorridor.name}
              </p>

              <p className="mt-2 text-sm text-slate-400">
                {selectedCorridor.incidents} recorded historical incidents
              </p>
            </div>
          </div>
        </section>

        {/* =====================================================
            RANKING COMPARISON
        ====================================================== */}
        <section className="border-b border-slate-700 px-8 py-10">

          <div className="mb-8">
            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-cyan-400">
              Ranking Analysis
            </p>

            <h2 className="text-xl font-bold text-white">
              How Did The Ranking Change?
            </h2>

            <p className="mt-2 text-sm text-slate-400">
              Compare traditional incident-count rankings with the
              risk-weighted model.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-3">

            {/*
              Only display the first three corridors here.
            */}
            {corridors.slice(0, 3).map((corridor) => {

              /*
                Calculate where this corridor ranks if we ONLY
                look at number of incidents.
              */
              const incidentRank =
                [...corridors]
                  .sort((a, b) => b.incidents - a.incidents)
                  .findIndex((c) => c.id === corridor.id) + 1;

              /*
                Calculate its ranking according to
                the final priority score.
              */
              const riskRank =
                priorities.findIndex(
                  (c) => c.id === corridor.id
                ) + 1;

              /*
                Determine how much its ranking changed.
              */
              const difference =
                incidentRank - riskRank;

              return (
                <div
                  key={corridor.id}
                  className="rounded-xl border border-slate-700 bg-slate-800/60 p-5"
                >
                  {/* Corridor name */}
                  <p className="font-semibold text-white">
                    {corridor.name}
                  </p>

                  {/* Ranking comparison */}
                  <div className="mt-5 flex items-center justify-between">

                    {/* Old ranking */}
                    <div>
                      <p className="text-xs text-slate-500">
                        Incident Rank
                      </p>

                      <p className="mt-1 text-2xl font-bold">
                        #{incidentRank}
                      </p>
                    </div>

                    <span className="text-2xl text-slate-600">
                      →
                    </span>

                    {/* New risk ranking */}
                    <div className="text-right">
                      <p className="text-xs text-slate-500">
                        Risk Rank
                      </p>

                      <p className="mt-1 text-2xl font-bold">
                        #{riskRank}
                      </p>
                    </div>
                  </div>

                  {/* Display whether ranking moved up or down */}
                  <div
                    className={`mt-5 rounded-lg px-3 py-2 text-center font-semibold ${
                      difference > 0
                        ? "bg-emerald-500/10 text-emerald-400"
                        : difference < 0
                        ? "bg-red-500/10 text-red-400"
                        : "bg-slate-700 text-slate-300"
                    }`}
                  >
                    {difference > 0 &&
                      `↑ ${difference} positions`}

                    {difference < 0 &&
                      `↓ ${Math.abs(difference)} positions`}

                    {difference === 0 &&
                      "No change"}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* =====================================================
            SELECTED CORRIDOR ANALYSIS
        ====================================================== */}
        <section className="px-8 py-10">

          {/* Heading */}
          <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">

            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-cyan-400">
                Corridor Analysis
              </p>

              {/*
                This automatically changes when the user
                selects another corridor.
              */}
              <h2 className="text-xl font-bold text-white">
                Selected Corridor: {selectedCorridor.name}
              </h2>
            </div>

            {/*
              Determine priority label from the score.

              80+ = Very High
              70+ = High
              Below 70 = Moderate
            */}
            <span
              className={`w-fit rounded-full border px-4 py-2 text-sm font-semibold ${
                selectedCorridor.priorityScore >= 80
                  ? "border-red-500/30 bg-red-500/10 text-red-400"
                  : selectedCorridor.priorityScore >= 70
                  ? "border-orange-500/30 bg-orange-500/10 text-orange-400"
                  : "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
              }`}
            >
              {selectedCorridor.priorityScore >= 80
                ? "Very High Priority"
                : selectedCorridor.priorityScore >= 70
                ? "High Priority"
                : "Moderate Priority"}
            </span>
          </div>

          <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">

            {/* ================= RISK BREAKDOWN ================= */}
            <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-6">

              <h3 className="mb-6 font-semibold text-white">
                Risk Breakdown
              </h3>

              <div className="space-y-6">

                {/*
                  Generate one progress bar for each
                  risk category.
                */}
                {breakdown.map((item) => (
                  <div key={item.label}>

                    {/* Risk name + value */}
                    <div className="flex justify-between">
                      <span className="text-slate-400">
                        {item.label}
                      </span>

                      <strong>
                        {item.value}/100
                      </strong>
                    </div>

                    {/* Progress bar background */}
                    <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-700">

                      {/* Actual coloured progress bar */}
                      <div
                        className={`h-full rounded-full ${riskBarColor(
                          item.type
                        )}`}
                        style={{
                          width: `${item.value}%`,
                        }}
                      />
                    </div>

                    {/*
                      Calculate how much this category contributes
                      to the final score.

                      Example:

                      Historical Risk = 68
                      Weight = 0.40

                      68 × 0.40 = 27.2
                    */}
                    <p className="mt-2 text-xs text-slate-500">
                      Contribution:{" "}
                      {(item.value * item.weight).toFixed(1)}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* ================= PRIORITY SCORE ================= */}
            <div className="rounded-xl border border-cyan-800/60 bg-gradient-to-br from-cyan-950/50 to-blue-950/50 p-6">

              <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">
                Priority Score
              </p>

              {/* Final priority score */}
              <p className="mt-4 text-6xl font-bold text-white">
                {selectedCorridor.priorityScore}
              </p>

              <p className="mt-2 text-sm text-slate-400">
                out of 100
              </p>

              <div className="my-6 h-px bg-cyan-900" />

              {/* Historical incident count */}
              <p className="text-sm font-semibold text-slate-300">
                Historical Incidents
              </p>

              <p className="mt-2 text-3xl font-bold text-white">
                {selectedCorridor.incidents}
              </p>

              <div className="my-6 h-px bg-cyan-900" />

              {/* Explanation */}
              <p className="text-sm font-semibold text-slate-300">
                Why is it ranked highly?
              </p>

              <p className="mt-2 text-sm leading-6 text-slate-400">
                This score combines historical incident risk, consequence,
                recency, and trend using the configured risk-model weights.
              </p>
            </div>

          </div>
        </section>

      </div>
    </main>
  );
}