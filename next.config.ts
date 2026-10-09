import type { NextConfig } from "next";

// Online demo: the browser calls the API on the same address (/api/...) and Next
// forwards it to FastAPI. Set FLOWLINE_API_PROXY (e.g. http://127.0.0.1:8000) and
// NEXT_PUBLIC_API_URL=/api at build time. Local installs leave both unset.
const apiProxy = process.env.FLOWLINE_API_PROXY?.replace(/\/$/, "");

const nextConfig: NextConfig = {
  devIndicators: false,
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    return apiProxy ? [{ source: "/api/:path*", destination: `${apiProxy}/:path*` }] : [];
  },
  // The page HTML must never be cached by the browser: after a rebuild (e.g. a new
  // Mapbox token in .env.local) a cached page would point at stale chunks. Hashed
  // /_next/static assets keep their immutable caching.
  async headers() {
    return [{ source: "/", headers: [{ key: "Cache-Control", value: "no-store, must-revalidate" }] }];
  },
};

export default nextConfig;
