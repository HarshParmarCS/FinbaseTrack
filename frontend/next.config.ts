import type { NextConfig } from "next";
import { parseServerEnv } from "./src/config/server-env";

const { BACKEND_INTERNAL_URL } = parseServerEnv(process.env);

const nextConfig: NextConfig = {
  // Self-contained server (.next/standalone) for the Docker image. Note: this config, including
  // the rewrite target below, is serialized into the build, so BACKEND_INTERNAL_URL is a build
  // argument in frontend/Dockerfile.
  output: "standalone",
  // The Docker build skips Next's built-in type check (SKIP_BUILD_TYPECHECK=true in
  // frontend/Dockerfile) because it needs more memory than a small container VM has. Types are
  // still checked by `pnpm typecheck`, which runs separately and must pass. Local `pnpm build`
  // keeps the check.
  typescript: { ignoreBuildErrors: process.env.SKIP_BUILD_TYPECHECK === "true" },
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
