"use client";

/*
  ============================================================
  IMPORTS
  ============================================================

  useEffect:
  Runs code when the map first loads.

  useState:
  Stores the pipeline data after we download it.

  React Leaflet:
  Displays the actual interactive map.
*/

import { useEffect, useState } from "react";

import {
  MapContainer,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
} from "react-leaflet";

import "leaflet/dist/leaflet.css";


/*
  ============================================================
  PIPELINE DATA TYPE
  ============================================================

  This describes the information we want to store
  for each pipeline returned by the GIS service.
*/

type Pipeline = {
  id: number;

  licenceNumber: string | number | null;

  lineNumber: string | number | null;

  company: string | null;

  status: string | null;

  substance: string | null;

  diameter: string | number | null;

  material: string | null;

  /*
    Leaflet expects coordinates like:

    [latitude, longitude]
  */
  coordinates: [number, number][];
};


/*
  ============================================================
  ARCGIS GEOJSON TYPES
  ============================================================

  The GIS server sends us GeoJSON.

  GeoJSON normally stores coordinates as:

  [longitude, latitude]

  This is backwards compared with Leaflet, so later
  we will reverse them.
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
  PIPELINE GIS URL
  ============================================================

  This is the ArcGIS FeatureServer query endpoint.

  Instead of manually typing coordinates, the website
  requests geographic pipeline geometry.
*/

const PIPELINE_API =
  "https://services9.arcgis.com/nUMfScOxh4qxkmsK/arcgis/rest/services/AERPipelines/FeatureServer/0/query";


/*
  ============================================================
  HELPER FUNCTION
  ============================================================

  GeoJSON gives us:

  [longitude, latitude]

  Leaflet wants:

  [latitude, longitude]

  This function converts between the two.
*/

function convertCoordinates(
  coordinates: number[][]
): [number, number][] {
  return coordinates.map((coordinate) => {
    const longitude = coordinate[0];
    const latitude = coordinate[1];

    return [latitude, longitude];
  });
}


/*
  ============================================================
  PIPELINE COLOUR
  ============================================================

  Right now the real GIS layer gives us pipeline information,
  but it does NOT automatically give us your calculated
  priority score.

  So for now we colour pipelines based on their status.

  Later we can join incident data to these pipelines and
  calculate your actual risk score.
*/

function getPipelineColor(status: string | null) {
  if (!status) {
    return "#94a3b8";
  }

  const statusLower = status.toLowerCase();

  /*
    Operating pipelines are cyan.
  */
  if (
    statusLower.includes("operating") ||
    statusLower.includes("active")
  ) {
    return "#22d3ee";
  }

  /*
    Abandoned pipelines are grey.
  */
  if (statusLower.includes("abandon")) {
    return "#64748b";
  }

  /*
    Discontinued pipelines are orange.
  */
  if (
    statusLower.includes("discontinued") ||
    statusLower.includes("inactive")
  ) {
    return "#fb923c";
  }

  /*
    Anything else gets blue.
  */
  return "#3b82f6";
}


/*
  ============================================================
  MAIN MAP COMPONENT
  ============================================================
*/

export default function PipelineMap() {
  /*
    pipelines

    Stores all pipelines after they are downloaded.
  */
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);


  /*
    loading

    Lets us tell the user that the pipeline information
    is currently downloading.
  */
  const [loading, setLoading] = useState(true);


  /*
    error

    Stores an error message if the API request fails.
  */
  const [error, setError] = useState<string | null>(null);


  /*
    ==========================================================
    DOWNLOAD PIPELINE DATA
    ==========================================================

    useEffect runs when PipelineMap first appears.
  */

  useEffect(() => {
    async function loadPipelines() {
      try {
        setLoading(true);

        setError(null);


        /*
          ====================================================
          BUILD OUR ARCGIS QUERY
          ====================================================

          where=1=1

          Means:
          Give us all available records.

          outFields:
          Specifies which information we want returned.

          returnGeometry=true:
          VERY IMPORTANT.

          This tells ArcGIS to include the actual
          pipeline coordinates.

          outSR=4326:
          Requests normal latitude/longitude coordinates.

          f=geojson:
          Requests GeoJSON instead of ArcGIS JSON.
        */

        const parameters = new URLSearchParams({
          where: "1=1",

          outFields:
            "OBJECTID_1,OBJECTID,LICENCE_NO,LINE_NO,COMP_NAME,SEG_STATUS,SUBSTANCE1,OUT_DIAMET,PIP_MATERL",

          returnGeometry: "true",

          outSR: "4326",

          f: "geojson",

          /*
            ArcGIS services normally limit how many
            records can be returned in one request.

            We request 2000 here.
          */
          resultRecordCount: "2000",
        });


        /*
          Create the final URL.
        */

        const url =
          `${PIPELINE_API}?${parameters.toString()}`;


        /*
          Send the request.
        */

        const response = await fetch(url);


        /*
          If the server returns an error code,
          stop here.
        */

        if (!response.ok) {
          throw new Error(
            `Pipeline request failed: ${response.status}`
          );
        }


        /*
          Convert the response into JavaScript.
        */

        const data: GeoJSONResponse =
          await response.json();


        /*
          Make sure the response actually contains features.
        */

        if (!data.features) {
          throw new Error(
            "The GIS service did not return pipeline features."
          );
        }


        /*
          ====================================================
          CONVERT GIS FEATURES INTO OUR PIPELINE OBJECTS
          ====================================================
        */

        const convertedPipelines: Pipeline[] = [];


        data.features.forEach((feature, featureIndex) => {
          /*
            Ignore anything without geometry.
          */

          if (!feature.geometry) {
            return;
          }


          /*
            Get the pipeline's properties.
          */

          const properties =
            feature.properties;


          /*
            Create a unique ID.

            Prefer the GIS OBJECTID.

            If one isn't available, use the feature's
            position in the returned array.
          */

          const id =
            properties.OBJECTID_1 ??
            properties.OBJECTID ??
            featureIndex;


          /*
            ==================================================
            LINESTRING
            ==================================================

            Most pipelines should be LineStrings.

            Example:

            [
              [-114.01, 51.02],
              [-113.98, 51.04],
              [-113.95, 51.06]
            ]
          */

          if (feature.geometry.type === "LineString") {
            const rawCoordinates =
              feature.geometry.coordinates as number[][];


            const coordinates =
              convertCoordinates(rawCoordinates);


            convertedPipelines.push({
              id,

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
            });
          }


          /*
            ==================================================
            MULTILINESTRING
            ==================================================

            Some geographic features can contain several
            separate line sections.

            We create one pipeline object for each section.
          */

          if (
            feature.geometry.type === "MultiLineString"
          ) {
            const lines =
              feature.geometry.coordinates as number[][][];


            lines.forEach((line, lineIndex) => {
              const coordinates =
                convertCoordinates(line);


              convertedPipelines.push({
                /*
                  Give each section its own ID.
                */
                id:
                  Number(
                    `${id}${lineIndex}`
                  ),

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
              });
            });
          }
        });


        /*
          Store the converted pipelines in React state.

          React automatically redraws the map after
          this happens.
        */

        setPipelines(convertedPipelines);
      } catch (err) {
        /*
          If anything goes wrong, print the full error
          in the browser console.
        */

        console.error(
          "Could not load pipeline data:",
          err
        );


        /*
          Show a readable error on the map.
        */

        setError(
          "Pipeline data could not be loaded."
        );
      } finally {
        /*
          Whether the request worked or failed,
          we're finished loading.
        */

        setLoading(false);
      }
    }


    /*
      Actually run our function.
    */

    loadPipelines();
  }, []);


  /*
    ==========================================================
    MAP
    ==========================================================
  */

  return (
    <div className="relative">

      {/*
        ======================================================
        LOADING MESSAGE
        ======================================================

        This floats above the map while pipeline data
        is downloading.
      */}

      {loading && (
        <div className="absolute left-1/2 top-4 z-[1000] -translate-x-1/2 rounded-lg border border-slate-600 bg-slate-900/95 px-4 py-2 text-sm text-slate-200 shadow-xl">
          Loading pipeline data...
        </div>
      )}


      {/*
        ======================================================
        ERROR MESSAGE
        ======================================================
      */}

      {error && (
        <div className="absolute left-1/2 top-4 z-[1000] -translate-x-1/2 rounded-lg border border-red-500/50 bg-red-950/95 px-4 py-2 text-sm text-red-200 shadow-xl">
          {error}
        </div>
      )}


      {/*
        ======================================================
        PIPELINE COUNT
        ======================================================

        Once loading finishes, show how many pipeline
        line features were loaded.
      */}

      {!loading && !error && (
        <div className="absolute left-4 top-4 z-[1000] rounded-lg border border-slate-600 bg-slate-900/90 px-3 py-2 text-xs text-slate-300 shadow-lg">
          {pipelines.length.toLocaleString()} pipeline segments loaded
        </div>
      )}


      {/*
        ======================================================
        LEAFLET MAP
        ======================================================
      */}

      <MapContainer
        /*
          Start roughly around central Alberta.
        */
        center={[53.3, -114.5]}

        /*
          Province-level zoom.
        */
        zoom={5}

        /*
          Prevent users from zooming too far out.
        */
        minZoom={4}

        /*
          Allow mouse-wheel zooming.
        */
        scrollWheelZoom={true}

        /*
          Map size.
        */
        style={{
          height: "600px",
          width: "100%",
          background: "#0f172a",
        }}
      >

        {/*
          ====================================================
          OPENSTREETMAP BASE MAP
          ====================================================

          This provides roads, cities, towns and other
          geographic information underneath the pipelines.
        */}

        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />


        {/*
          ====================================================
          REAL PIPELINES
          ====================================================

          Loop through every pipeline downloaded from
          the GIS service and draw it on the map.
        */}

        {pipelines.map((pipeline) => {
          /*
            Determine line colour based on status.
          */

          const color =
            getPipelineColor(pipeline.status);


          return (
            <Polyline
              key={pipeline.id}

              /*
                These are the coordinates that came
                from the GIS service.
              */
              positions={pipeline.coordinates}

              /*
                Pipeline appearance.
              */
              pathOptions={{
                color,
                weight: 3,
                opacity: 0.8,
              }}
            >

              {/*
                ==============================================
                HOVER TOOLTIP
                ==============================================

                Appears when you hover over a pipeline.
              */}

              <Tooltip sticky>
                <div>
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
                </div>
              </Tooltip>


              {/*
                ==============================================
                CLICK POPUP
                ==============================================

                Appears when you click a pipeline.
              */}

              <Popup>
                <div
                  style={{
                    minWidth: "220px",
                  }}
                >
                  {/* Company */}
                  <strong
                    style={{
                      fontSize: "16px",
                    }}
                  >
                    {pipeline.company ||
                      "Pipeline"}
                  </strong>


                  <hr
                    style={{
                      margin: "8px 0",
                    }}
                  />


                  {/* Licence number */}
                  <div>
                    <strong>
                      Licence:
                    </strong>{" "}

                    {pipeline.licenceNumber ??
                      "Unknown"}
                  </div>


                  {/* Line number */}
                  <div>
                    <strong>
                      Line:
                    </strong>{" "}

                    {pipeline.lineNumber ??
                      "Unknown"}
                  </div>


                  {/* Pipeline status */}
                  <div>
                    <strong>
                      Status:
                    </strong>{" "}

                    {pipeline.status ??
                      "Unknown"}
                  </div>


                  {/* Substance transported */}
                  <div>
                    <strong>
                      Substance:
                    </strong>{" "}

                    {pipeline.substance ??
                      "Unknown"}
                  </div>


                  {/* Pipeline diameter */}
                  <div>
                    <strong>
                      Diameter:
                    </strong>{" "}

                    {pipeline.diameter ??
                      "Unknown"}
                  </div>


                  {/* Pipeline material */}
                  <div>
                    <strong>
                      Material:
                    </strong>{" "}

                    {pipeline.material ??
                      "Unknown"}
                  </div>
                </div>
              </Popup>

            </Polyline>
          );
        })}

      </MapContainer>
    </div>
  );
}