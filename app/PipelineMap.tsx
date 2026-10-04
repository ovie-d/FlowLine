"use client";

import { useEffect, useState } from "react";

import {
  CircleMarker,
  MapContainer,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
} from "react-leaflet";

import "leaflet/dist/leaflet.css";

/*
============================================================
TYPES
============================================================
*/

type RiskLevel = "Low" | "Moderate" | "High" | "Very High";

type ConfidenceLevel = "Low" | "Moderate" | "High";

type Pipeline = {
  id: string;

  licenceNumber: string | number | null;
  lineNumber: string | number | null;

  company: string | null;
  status: string | null;
  substance: string | null;
  diameter: string | number | null;
  material: string | null;

  coordinates: [number, number][];

  /*
    These fields are ready for the incident/risk model.

    Right now they are null because the GIS pipeline layer
    itself does not provide our calculated risk information.

    Later we will calculate these using the incident dataset.
  */

  riskScore: number | null;
  riskLevel: RiskLevel | null;

  confidence: ConfidenceLevel | null;

  relevantEvents: number | null;

  pipelineReleases: number | null;
  facilityFires: number | null;
  limitBreaches: number | null;
  otherEvents: number | null;

  seriousReleases: number | null;
  recentEvents: number | null;

  totalReleaseVolume: number | null;

  primaryDriver: string | null;
};

/*
============================================================
GEOJSON TYPES
============================================================
*/

type GeoJSONFeature = {
  type: "Feature";

  properties: {
    OBJECTID_1?: number;
    OBJECTID?: number;

    LICENCE_NO?: string | number;
    LINE_NO?: string | number;

    COMP_NAME?: string;

    SEG_STATUS?: string;

    SUBSTANCE1?: string;

    OUT_DIAMET?: string | number;

    PIP_MATERL?: string;
  };

  geometry: {
    type: "LineString" | "MultiLineString";

    coordinates:
      | number[][]
      | number[][][];
  };
};

type GeoJSONResponse = {
  type: "FeatureCollection";
  features: GeoJSONFeature[];
};

/*
============================================================
GIS API
============================================================
*/

const PIPELINE_API =
  "https://services9.arcgis.com/nUMfScOxh4qxkmsK/arcgis/rest/services/AERPipelines/FeatureServer/0/query";

/*
============================================================
COORDINATE CONVERSION
============================================================

GeoJSON:
[longitude, latitude]

Leaflet:
[latitude, longitude]
*/

function convertCoordinates(
  coordinates: number[][]
): [number, number][] {
  return coordinates.map((coordinate) => [
    coordinate[1],
    coordinate[0],
  ]);
}

/*
============================================================
RISK COLOUR
============================================================

Eventually the pipeline colour represents calculated risk.

RED     = Very High
ORANGE  = High
YELLOW  = Moderate
GREEN   = Low
GREY    = Risk not calculated yet
*/

function getRiskColor(
  riskLevel: RiskLevel | null
) {
  if (riskLevel === "Very High") {
    return "#ef4444";
  }

  if (riskLevel === "High") {
    return "#f97316";
  }

  if (riskLevel === "Moderate") {
    return "#eab308";
  }

  if (riskLevel === "Low") {
    return "#22c55e";
  }

  return "#64748b";
}

/*
============================================================
CONFIDENCE STYLE
============================================================

Confidence is deliberately separate from risk.

A pipeline can therefore be:

HIGH RISK + LOW CONFIDENCE

which is important when there are only a few severe incidents.
*/

function getConfidenceDash(
  confidence: ConfidenceLevel | null
) {
  if (confidence === "Low") {
    return "4 8";
  }

  if (confidence === "Moderate") {
    return "8 5";
  }

  /*
    High confidence = solid line.
  */

  return undefined;
}

/*
============================================================
EVENT MARKER SIZE
============================================================

Marker size represents amount of relevant evidence.

This is NOT the risk score.

More relevant events = larger marker.
*/

function getEvidenceMarkerSize(
  events: number | null
) {
  if (!events) {
    return 6;
  }

  return Math.min(
    24,
    6 + Math.sqrt(events) * 2.5
  );
}

/*
============================================================
PIPELINE MIDPOINT
============================================================

Used to position the evidence marker.
*/

function getPipelineMidpoint(
  coordinates: [number, number][]
): [number, number] | null {
  if (coordinates.length === 0) {
    return null;
  }

  return coordinates[
    Math.floor(coordinates.length / 2)
  ];
}

/*
============================================================
MAIN COMPONENT
============================================================
*/

export default function PipelineMap() {
  const [pipelines, setPipelines] =
    useState<Pipeline[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const [selectedPipeline, setSelectedPipeline] =
    useState<Pipeline | null>(null);

  /*
  ============================================================
  LOAD PIPELINES
  ============================================================
  */

  useEffect(() => {
    async function loadPipelines() {
      try {
        setLoading(true);
        setError(null);

        const parameters =
          new URLSearchParams({
            where: "1=1",

            outFields:
              "OBJECTID_1,OBJECTID,LICENCE_NO,LINE_NO,COMP_NAME,SEG_STATUS,SUBSTANCE1,OUT_DIAMET,PIP_MATERL",

            returnGeometry: "true",

            outSR: "4326",

            f: "geojson",

            resultRecordCount: "2000",
          });

        const url =
          `${PIPELINE_API}?${parameters.toString()}`;

        const response =
          await fetch(url);

        if (!response.ok) {
          throw new Error(
            `Pipeline request failed: ${response.status}`
          );
        }

        const data: GeoJSONResponse =
          await response.json();

        if (!data.features) {
          throw new Error(
            "No pipeline features returned."
          );
        }

        const convertedPipelines: Pipeline[] =
          [];

        /*
        ======================================================
        CONVERT PIPELINE FEATURES
        ======================================================
        */

        data.features.forEach(
          (feature, featureIndex) => {
            if (!feature.geometry) {
              return;
            }

            const properties =
              feature.properties;

            const baseId =
              properties.OBJECTID_1 ??
              properties.OBJECTID ??
              featureIndex;

            /*
            --------------------------------------------------
            Helper for creating our Pipeline object.
            --------------------------------------------------
            */

            const createPipeline = (
              coordinates: [number, number][],
              suffix: string
            ): Pipeline => ({
              id: `${baseId}-${suffix}`,

              licenceNumber:
                properties.LICENCE_NO ?? null,

              lineNumber:
                properties.LINE_NO ?? null,

              company:
                properties.COMP_NAME ?? null,

              status:
                properties.SEG_STATUS ?? null,

              substance:
                properties.SUBSTANCE1 ?? null,

              diameter:
                properties.OUT_DIAMET ?? null,

              material:
                properties.PIP_MATERL ?? null,

              coordinates,

              /*
                IMPORTANT:

                We are NOT inventing risk data.

                These remain null until we join the
                real incident dataset.
              */

              riskScore: null,
              riskLevel: null,

              confidence: null,

              relevantEvents: null,

              pipelineReleases: null,
              facilityFires: null,
              limitBreaches: null,
              otherEvents: null,

              seriousReleases: null,
              recentEvents: null,

              totalReleaseVolume: null,

              primaryDriver: null,
            });

            /*
            --------------------------------------------------
            LINESTRING
            --------------------------------------------------
            */

            if (
              feature.geometry.type ===
              "LineString"
            ) {
              const rawCoordinates =
                feature.geometry
                  .coordinates as number[][];

              const coordinates =
                convertCoordinates(
                  rawCoordinates
                );

              convertedPipelines.push(
                createPipeline(
                  coordinates,
                  "0"
                )
              );
            }

            /*
            --------------------------------------------------
            MULTILINESTRING
            --------------------------------------------------
            */

            if (
              feature.geometry.type ===
              "MultiLineString"
            ) {
              const lines =
                feature.geometry
                  .coordinates as number[][][];

              lines.forEach(
                (line, lineIndex) => {
                  const coordinates =
                    convertCoordinates(
                      line
                    );

                  convertedPipelines.push(
                    createPipeline(
                      coordinates,
                      String(lineIndex)
                    )
                  );
                }
              );
            }
          }
        );

        setPipelines(
          convertedPipelines
        );
      } catch (err) {
        console.error(
          "Could not load pipeline data:",
          err
        );

        setError(
          "Pipeline data could not be loaded."
        );
      } finally {
        setLoading(false);
      }
    }

    loadPipelines();
  }, []);

  /*
  ============================================================
  MAP
  ============================================================
  */

  return (
    <div className="relative">

      {/* LOADING */}

      {loading && (
        <div className="absolute left-1/2 top-4 z-[1000] -translate-x-1/2 rounded-lg border border-slate-600 bg-slate-900/95 px-4 py-2 text-sm text-slate-200 shadow-xl">
          Loading pipeline data...
        </div>
      )}

      {/* ERROR */}

      {error && (
        <div className="absolute left-1/2 top-4 z-[1000] -translate-x-1/2 rounded-lg border border-red-500/50 bg-red-950/95 px-4 py-2 text-sm text-red-200 shadow-xl">
          {error}
        </div>
      )}

      {/* PIPELINE COUNT */}

      {!loading && !error && (
        <div className="absolute left-4 top-4 z-[1000] rounded-lg border border-slate-600 bg-slate-900/90 px-3 py-2 text-xs text-slate-300 shadow-lg">
          {pipelines.length.toLocaleString()} pipeline segments loaded
        </div>
      )}

      {/* LEGEND */}

      <div className="absolute bottom-6 left-4 z-[1000] w-52 rounded-xl border border-slate-700 bg-slate-950/95 p-4 text-xs text-slate-300 shadow-xl">

        <div className="mb-3 font-semibold text-white">
          Inspection Risk
        </div>

        <div className="space-y-2">

          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-red-500" />
            Very High
          </div>

          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-orange-500" />
            High
          </div>

          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-yellow-500" />
            Moderate
          </div>

          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-green-500" />
            Low
          </div>

          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-slate-500" />
            Not calculated
          </div>

        </div>

        <div className="mt-4 border-t border-slate-700 pt-3 text-[11px] leading-4 text-slate-400">
          Line colour = risk
          <br />
          Marker size = evidence
          <br />
          Dashed line = lower confidence
        </div>

      </div>

      {/* MAP */}

      <MapContainer
        center={[53.3, -114.5]}
        zoom={5}
        minZoom={4}
        scrollWheelZoom={true}
        style={{
          height: "600px",
          width: "100%",
          background: "#0f172a",
        }}
      >

        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/*
        ======================================================
        PIPELINES
        ======================================================
        */}

        {pipelines.map((pipeline) => {
          const color =
            getRiskColor(
              pipeline.riskLevel
            );

          const selected =
            selectedPipeline?.id ===
            pipeline.id;

          const midpoint =
            getPipelineMidpoint(
              pipeline.coordinates
            );

          return (
            <div key={pipeline.id}>

              {/*
              ------------------------------------------------
              PIPELINE LINE
              ------------------------------------------------
              */}

              <Polyline
                positions={
                  pipeline.coordinates
                }

                pathOptions={{
                  color,

                  weight:
                    selected ? 7 : 3,

                  opacity:
                    selected ? 1 : 0.75,

                  dashArray:
                    getConfidenceDash(
                      pipeline.confidence
                    ),
                }}

                eventHandlers={{
                  click: () =>
                    setSelectedPipeline(
                      pipeline
                    ),
                }}
              >

                <Tooltip sticky>

                  <div
                    style={{
                      minWidth: "180px",
                    }}
                  >

                    <strong>
                      {pipeline.company ||
                        "Pipeline"}
                    </strong>

                    <br />

                    Licence:{" "}
                    {pipeline.licenceNumber ??
                      "Unknown"}

                    <br />

                    Line:{" "}
                    {pipeline.lineNumber ??
                      "Unknown"}

                    <hr
                      style={{
                        margin: "5px 0",
                      }}
                    />

                    Risk:{" "}

                    <strong>
                      {pipeline.riskLevel ??
                        "Not calculated"}
                    </strong>

                    <br />

                    Confidence:{" "}

                    {pipeline.confidence ??
                      "Not calculated"}

                  </div>

                </Tooltip>

                <Popup>

                  <div
                    style={{
                      minWidth: "260px",
                    }}
                  >

                    <strong
                      style={{
                        fontSize: "16px",
                      }}
                    >
                      {pipeline.company ||
                        "Pipeline"}
                    </strong>

                    <div
                      style={{
                        marginTop: "3px",
                        color: "#64748b",
                      }}
                    >
                      Licence{" "}
                      {pipeline.licenceNumber ??
                        "Unknown"}

                      {" • "}

                      Line{" "}

                      {pipeline.lineNumber ??
                        "Unknown"}
                    </div>

                    <hr
                      style={{
                        margin: "10px 0",
                      }}
                    />

                    {/* RISK */}

                    <div>
                      <strong>
                        Inspection Risk:
                      </strong>{" "}

                      {pipeline.riskLevel ??
                        "Not calculated"}
                    </div>

                    {/* SCORE */}

                    <div>
                      <strong>
                        Risk Score:
                      </strong>{" "}

                      {pipeline.riskScore ??
                        "Pending incident analysis"}
                    </div>

                    {/* CONFIDENCE */}

                    <div>
                      <strong>
                        Confidence:
                      </strong>{" "}

                      {pipeline.confidence ??
                        "Pending incident analysis"}
                    </div>

                    <hr
                      style={{
                        margin: "10px 0",
                      }}
                    />

                    {/* EVIDENCE */}

                    <strong>
                      Evidence
                    </strong>

                    <div>
                      Relevant events:{" "}

                      {pipeline.relevantEvents ??
                        "Pending"}
                    </div>

                    <div>
                      Pipeline releases:{" "}

                      {pipeline.pipelineReleases ??
                        "Pending"}
                    </div>

                    <div>
                      Facility fires:{" "}

                      {pipeline.facilityFires ??
                        "Pending"}
                    </div>

                    <div>
                      Limit breaches:{" "}

                      {pipeline.limitBreaches ??
                        "Pending"}
                    </div>

                    <div>
                      Serious releases:{" "}

                      {pipeline.seriousReleases ??
                        "Pending"}
                    </div>

                    <div>
                      Recent events:{" "}

                      {pipeline.recentEvents ??
                        "Pending"}
                    </div>

                    <hr
                      style={{
                        margin: "10px 0",
                      }}
                    />

                    {/* PIPELINE INFORMATION */}

                    <strong>
                      Asset Information
                    </strong>

                    <div>
                      Substance:{" "}

                      {pipeline.substance ??
                        "Unknown"}
                    </div>

                    <div>
                      Status:{" "}

                      {pipeline.status ??
                        "Unknown"}
                    </div>

                    <div>
                      Diameter:{" "}

                      {pipeline.diameter ??
                        "Unknown"}
                    </div>

                    <div>
                      Material:{" "}

                      {pipeline.material ??
                        "Unknown"}
                    </div>

                    {/* WHY RANKED */}

                    {pipeline.primaryDriver && (
                      <>
                        <hr
                          style={{
                            margin:
                              "10px 0",
                          }}
                        />

                        <strong>
                          Why it ranked
                        </strong>

                        <div>
                          {
                            pipeline.primaryDriver
                          }
                        </div>
                      </>
                    )}

                    <div
                      style={{
                        marginTop: "12px",
                        padding: "8px",
                        background:
                          "#f1f5f9",
                        borderRadius: "6px",
                        fontSize: "11px",
                      }}
                    >
                      Decision-support ranking only.
                      Engineering review is required
                      before inspection decisions.
                    </div>

                  </div>

                </Popup>

              </Polyline>

              {/*
              ------------------------------------------------
              EVIDENCE MARKER
              ------------------------------------------------

              We ONLY display this once real incident
              evidence has been attached.

              This prevents us from showing fake markers.
              */}

              {midpoint &&
                pipeline.relevantEvents !==
                  null &&
                pipeline.relevantEvents >
                  0 && (

                  <CircleMarker
                    center={midpoint}

                    radius={
                      getEvidenceMarkerSize(
                        pipeline.relevantEvents
                      )
                    }

                    pathOptions={{
                      color: "#ffffff",

                      weight: 2,

                      fillColor: color,

                      fillOpacity: 0.8,
                    }}

                    eventHandlers={{
                      click: () =>
                        setSelectedPipeline(
                          pipeline
                        ),
                    }}
                  >

                    <Tooltip>
                      <div>
                        <strong>
                          {
                            pipeline.relevantEvents
                          }{" "}
                          relevant events
                        </strong>

                        <br />

                        Risk:{" "}

                        {pipeline.riskLevel ??
                          "Pending"}

                        <br />

                        Confidence:{" "}

                        {pipeline.confidence ??
                          "Pending"}
                      </div>
                    </Tooltip>

                  </CircleMarker>
                )}

            </div>
          );
        })}

      </MapContainer>

    </div>
  );
}