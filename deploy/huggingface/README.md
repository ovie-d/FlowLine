# Flowline online demo (Hugging Face Spaces)

> **Note (October 2026):** Hugging Face now requires a PRO subscription for Docker Spaces.
> The public demo therefore runs on free hosting instead (see [`../free/`](../free/)). This
> folder still builds the one-container version, for Spaces with PRO or any Docker host,
> and `deploy/free/tunnel.sh` uses it for the laptop backup.

The online demo is the full app in one Docker container on a free Hugging Face Space:
PostgreSQL + PostGIS + pgvector, the OSRM router, the FastAPI backend and the Next.js app
on port 7860. The database snapshot is restored and the routing graph unpacked **at build
time**, so the Space starts in seconds.

## What visitors get

- **Demo mode** (`FLOWLINE_DEMO=1`):
  - Each visitor (an anonymous browser id plus a hashed IP) gets **3 AI prompts per day**.
  - All AI stops for the day once the estimated spend reaches **US$1**
    (`AI_DAILY_BUDGET_USD`). A failed AI call gives the prompt back.
- **Private sandbox:** crew-table edits and decisions stay private to each visitor for 24
  hours, so the demo data stays clean for everyone, including presenters.
- **Hidden spend:** `/agent/usage` (spend details) is hidden.

## One-time setup (owner)

1. Create a free account at <https://huggingface.co/join>.
2. Create a **write** access token: <https://huggingface.co/settings/tokens>. Then log in
   on the machine that has the local Flowline data:
   `.venv/bin/pip install huggingface_hub && .venv/bin/hf auth login`.
3. Publish, from the Flowline folder (Flowline must have run once locally, so the database
   and `osrm/` exist):

   ```bash
   .venv/bin/python deploy/huggingface/publish.py <hf-user> all
   ```

   This step:
   - builds the public data bundle: CER/OSM-derived tables only (no decision log, crew
     edits or logs), plus the routing graph, about 350 MB;
   - uploads the bundle to the dataset `<hf-user>/flowline-data`;
   - uploads the committed code to the Space `<hf-user>/flowline`.
4. In the Space's **Settings → Variables and secrets**, add:
   - `GEMINI_API_KEY` (secret). Use a **separate key just for the demo**, and set a budget
     alert or cap in Google Cloud billing as well. Then the key can be revoked without
     touching your own.
   - `NEXT_PUBLIC_MAPBOX_TOKEN` (secret, optional). Use a public `pk.` token restricted to
     `https://<hf-user>-flowline.hf.space`. Without it the demo uses the open basemaps.
5. Restart the Space (Settings → Factory rebuild) after adding secrets. The Mapbox token
   is used at build time.

## Updating

- **App code changed:** run `publish.py <hf-user> space`.
- **Data changed** (new CER data loaded locally): run `publish.py <hf-user> all`.

## Limits worth knowing

- **Sleep:** free Spaces sleep after about 48 hours without visitors. The first visit
  wakes them in a minute or two. Open the demo shortly before presenting it.
- **Restarts reset counters:** the container's disk isn't persistent, so a restart resets
  the visitors' sandboxes and the daily AI counters. The Google-side budget cap is the
  backstop.
- **Basemap terms:** the keyless basemaps (OpenFreeMap, Esri imagery) have fair-use
  terms, and Mapbox's free tier covers 50,000 map loads a month.
