import type { NextConfig } from "next";
import { parseServerEnv } from "./src/config/server-env";

const { BACKEND_INTERNAL_URL } = parseServerEnv(process.env);

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // The browser talks to one origin; Next.js forwards /api/* to the FastAPI backend.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_INTERNAL_URL}/api/:path*` }];
  },
};

export default nextConfig;
