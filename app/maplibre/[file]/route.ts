import { readFile } from "node:fs/promises";
import path from "node:path";

/**
 * MapLibre GL 6 runs its tile work in a module Web Worker that it loads by URL. The
 * bundler does not emit those files, so serve them from the installed package (always
 * the same version as the main library). HazardMaplibre points setWorkerUrl here.
 */
const FILES = new Set(["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]);

export async function GET(_req: Request, { params }: { params: Promise<{ file: string }> }) {
  const { file } = await params;
  if (!FILES.has(file)) return new Response("Not found", { status: 404 });
  const body = await readFile(path.join(process.cwd(), "node_modules", "maplibre-gl", "dist", file));
  return new Response(body, {
    headers: { "Content-Type": "text/javascript; charset=utf-8", "Cache-Control": "public, max-age=86400" },
  });
}
