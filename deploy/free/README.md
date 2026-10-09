# Flowline online demo on free hosting

**Live demo:** https://flowline-hazard-forecast.vercel.app

| Part | Service (free plan, no credit card) | Notes |
|---|---|---|
| Website | [Vercel](https://vercel.com) Hobby | Next.js app; calls the API directly |
| API | [Render](https://render.com) free web service | `deploy/free/Dockerfile` (about 500 MB image, about 100 MB RAM). Sleeps after 15 min idle; wakes in about a minute |
| Database | [Neon](https://neon.tech) free Postgres | PostGIS + pgvector. Same public snapshot as local; AI quota and spend persist here |
| Routing | [Public OSRM server](https://router.project-osrm.org) | Same engine as a local install. Fair use only; falls back to straight-line distance with a warning |
| Maps | OpenFreeMap + Esri imagery | Keyless; same as a local install without a Mapbox token |

Demo mode (`FLOWLINE_DEMO=1`, set in the Dockerfile):

- Each visitor gets 3 AI prompts a day (`AI_PROMPTS_PER_VISITOR`).
- All AI stops for the day at US$1 of estimated spend (`AI_DAILY_BUDGET_USD`).
- Crew edits and decisions stay private to each visitor for 24 hours.

## Setting it up again

1. **Neon:** create a project (Postgres 17 or 18, region AWS US East 2) and copy its
   connection string (pooling off, `sslmode=require`). Save it to a private file in your
   own terminal:

   ```bash
   bash -c 'read -rs -p "Paste Neon connection string: " u && printf "%s" "$u" > ~/.flowline-neon-url && chmod 600 ~/.flowline-neon-url && echo " saved"'
   ```

   Then load the public snapshot (Flowline must have run locally once):

   ```bash
   deploy/free/init_neon.sh ~/.flowline-neon-url
   ```

2. **Render:** create a Web Service from the public repo `https://github.com/ovie-d/FlowLine`.
   - Docker build: Dockerfile path `deploy/free/Dockerfile`, build context `.`.
   - Instance type: Free; region: Ohio.
   - Environment variables: `DATABASE_URL` (the Neon string) and `GEMINI_API_KEY`. Use a
     separate demo key, with a budget alert in Google Cloud.

3. **Vercel:** in your own terminal, run `npx vercel@latest login`. Then deploy from a
   clean checkout of the committed code (`.vercelignore` keeps the Python backend out):

   ```bash
   git worktree add --detach ../flowline-web HEAD && cd ../flowline-web
   npx vercel@latest deploy --prod --yes \
     --build-env NEXT_PUBLIC_API_URL=https://<your-render-service>.onrender.com \
     --build-env NEXT_PUBLIC_FLOWLINE_HOSTED=1
   ```

**Updating:**

- **API code changed:** push it, then on Render choose Manual Deploy → Deploy latest commit.
- **Website changed:** repeat the Vercel deploy from a fresh worktree.
- **Data changed:** re-run `init_neon.sh`.

## Laptop backup (live demos)

`deploy/free/tunnel.sh` runs the full one-container demo on this laptop and shares it
through a free [Cloudflare quick tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/).
It includes the database, its own OSRM router, the API and the web app, with the same
demo limits. It needs no account. It only works while the laptop is on, and the `https://…trycloudflare.com` link changes each time.

```bash
deploy/free/tunnel.sh build   # once, or after code changes (a few minutes)
deploy/free/tunnel.sh         # start: prints the public link
deploy/free/tunnel.sh stop    # stop
```

The AI uses the `GEMINI_API_KEY` from your local `.env`, within the same demo limits.
