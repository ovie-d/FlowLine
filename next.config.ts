import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  allowedDevOrigins: ["127.0.0.1"],
  // The page HTML must never be cached by the browser: after a rebuild (e.g. a new
  // Mapbox token in .env.local) a cached page would point at stale chunks. Hashed
  // /_next/static assets keep their immutable caching.
  async headers() {
    return [{ source: "/", headers: [{ key: "Cache-Control", value: "no-store, must-revalidate" }] }];
  },
};

export default nextConfig;
