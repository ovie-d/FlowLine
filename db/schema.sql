-- Flowline Hazard Forecast schema (PostgreSQL 18 + PostGIS + pgvector).
-- Idempotent: every statement is safe to re-run (scripts/load_postgres.py applies it).

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

-- National CER incidents, cleaned. Raw CER fields are kept verbatim in `raw`.
CREATE TABLE IF NOT EXISTS incidents (
  incident_number     text PRIMARY KEY,
  event_date          date NOT NULL,
  event_date_source   text NOT NULL CHECK (event_date_source IN ('occurred', 'discovered', 'reported')),
  occurred_at         timestamp,
  discovered_at       timestamp,
  reported_date       date,
  province            text NOT NULL,
  is_alberta          boolean NOT NULL,
  nearest_centre      text,
  company             text NOT NULL,
  operator_group      text NOT NULL,
  commodity           text NOT NULL,
  status              text,
  latitude            double precision NOT NULL,
  longitude           double precision NOT NULL,
  geom                geography(Point, 4326) NOT NULL,
  site_id             integer NOT NULL,
  hazard_group        text NOT NULL,
  hazard_groups       text[] NOT NULL,
  is_model_target     boolean NOT NULL,
  incident_types      text,
  what_category       text,
  detailed_what       text,
  why_category        text,
  detailed_why        text,
  raw                 jsonb NOT NULL,
  loaded_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS incidents_geom_idx ON incidents USING gist (geom);
CREATE INDEX IF NOT EXISTS incidents_event_date_idx ON incidents (event_date);
CREATE INDEX IF NOT EXISTS incidents_hazard_idx ON incidents (hazard_group);
CREATE INDEX IF NOT EXISTS incidents_site_idx ON incidents (site_id);

-- Phase 3 weather features (missing = NULL, never zero).
CREATE TABLE IF NOT EXISTS incident_weather (
  incident_number     text PRIMARY KEY REFERENCES incidents ON DELETE CASCADE,
  temp_mean_d0        double precision,
  temp_min_d0         double precision,
  temp_max_d0         double precision,
  temp_mean_7d        double precision,
  temp_min_7d         double precision,
  temp_max_7d         double precision,
  temp_mean_30d       double precision,
  temp_min_30d        double precision,
  temp_max_30d        double precision,
  freeze_thaw_30d     double precision,
  precip_7d           double precision,
  precip_30d          double precision,
  snow_on_ground_d0   double precision,
  temp_station_id     integer,
  temp_station_km     double precision,
  precip_station_id   integer,
  precip_station_km   double precision,
  snow_station_id     integer,
  snow_station_km     double precision
);

-- Vector store. Public CER data has cause codes only, no narratives; this table is
-- ready for operator incident narratives in a pilot (text_source records the field).
CREATE TABLE IF NOT EXISTS incident_embeddings (
  incident_number     text NOT NULL REFERENCES incidents ON DELETE CASCADE,
  text_source         text NOT NULL,
  model               text NOT NULL,
  embedding           vector(384) NOT NULL,
  created_at          timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (incident_number, text_source, model)
);

-- Ranking tab (existing product): the 313-row Alberta seed and cleaned corridors.
CREATE TABLE IF NOT EXISTS ranking_incidents (
  id                  serial PRIMARY KEY,
  date                date,
  company             text,
  corridor            text,
  substance           text,
  release_m3          double precision,
  incident_type       text,
  cause               text,
  latitude            double precision,
  longitude           double precision,
  consequence         text,
  source              text NOT NULL DEFAULT 'cer_seed',
  loaded_at           timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS corridors (
  name                text PRIMARY KEY,
  n_incidents         integer NOT NULL,
  latitude            double precision NOT NULL,
  longitude           double precision NOT NULL,
  geom                geography(Point, 4326) NOT NULL
);

-- Crew readiness. All seeded rows are SAMPLE data until validated (is_sample).
CREATE TABLE IF NOT EXISTS crew_types (
  id                  text PRIMARY KEY,
  name                text NOT NULL,
  description         text NOT NULL,
  is_sample           boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS hazard_crew_map (
  hazard_group        text NOT NULL,
  crew_type_id        text NOT NULL REFERENCES crew_types ON DELETE CASCADE,
  equipment           text[] NOT NULL DEFAULT '{}',
  priority            integer NOT NULL DEFAULT 1,
  is_sample           boolean NOT NULL DEFAULT true,
  updated_at          timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (hazard_group, crew_type_id)
);

CREATE TABLE IF NOT EXISTS crew_bases (
  id                  text PRIMARY KEY,
  name                text NOT NULL,
  province            text NOT NULL,
  latitude            double precision NOT NULL,
  longitude           double precision NOT NULL,
  geom                geography(Point, 4326) NOT NULL,
  crew_types          text[] NOT NULL,
  is_sample           boolean NOT NULL DEFAULT true
);

-- Planner decisions (migrated from inspection_decisions.json / SQLite).
CREATE TABLE IF NOT EXISTS decision_log (
  id                  text PRIMARY KEY,
  ts                  timestamptz NOT NULL,
  corridor            text NOT NULL,
  action              text NOT NULL CHECK (action IN ('inspect', 'escalate', 'defer')),
  priority            text NOT NULL,
  reason              text NOT NULL,
  policy              jsonb NOT NULL DEFAULT '{}',
  source              text NOT NULL
);

-- CER Pipeline Systems layer (route geometry; display + distance features).
CREATE TABLE IF NOT EXISTS pipelines (
  id                  serial PRIMARY KEY,
  pipeline_name       text NOT NULL,
  company             text NOT NULL,
  commodity           text NOT NULL,
  geom                geography(MultiLineString, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS pipelines_geom_idx ON pipelines USING gist (geom);

-- Phase 5 (decision A): structured context vectors for similar-incident evidence.
-- Dimension = core.similar.VECTOR_DIM (geo 3 + season 2 + weather 4 + commodity 2).
CREATE TABLE IF NOT EXISTS incident_context (
  incident_number     text PRIMARY KEY REFERENCES incidents ON DELETE CASCADE,
  vec                 vector(11) NOT NULL,
  weather_known       boolean NOT NULL
);
CREATE INDEX IF NOT EXISTS incident_context_hnsw
  ON incident_context USING hnsw (vec vector_l2_ops);

CREATE TABLE IF NOT EXISTS similarity_meta (
  id                  integer PRIMARY KEY CHECK (id = 1),
  medians             jsonb NOT NULL,
  scales              jsonb NOT NULL,
  updated_at          timestamptz NOT NULL DEFAULT now()
);

-- Narrative embeddings (pilot): cosine HNSW index, empty until narratives are loaded.
CREATE INDEX IF NOT EXISTS incident_embeddings_hnsw
  ON incident_embeddings USING hnsw (embedding vector_cosine_ops);

-- Phase 6 additions (idempotent column adds).
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS closed_date date;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS dist_pipeline_km double precision;
