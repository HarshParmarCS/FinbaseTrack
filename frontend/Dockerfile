# syntax=docker/dockerfile:1
# Next.js frontend: dependencies, build, then a small standalone runtime that runs as `node`.

ARG NODE_IMAGE=docker.io/library/node:24-alpine

# ---- base: the pnpm version pinned in package.json ("packageManager") -------------------------
FROM ${NODE_IMAGE} AS base
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm install --global pnpm@12.21.0 && pnpm --version
WORKDIR /app

# ---- dependencies (cached until the lockfile changes) ----------------------------------------
FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

# ---- build ------------------------------------------------------------------------------------
FROM base AS build
# Where the Next.js SERVER forwards /api/* (Docker service name; never sent to the browser).
ARG BACKEND_INTERNAL_URL=http://backend:8000
# Browser-side API base. Empty = same origin: the browser calls /api/v1 on the frontend and the
# server above forwards it. NEXT_PUBLIC_* values are inlined into the browser bundle at build.
ARG NEXT_PUBLIC_API_BASE_URL=
ARG NEXT_PUBLIC_APP_NAME="Finbase Workdesk"
# Type checking is a separate gate (`pnpm typecheck`); skipping it here keeps the image build
# within the memory of small container VMs. Pass --build-arg SKIP_BUILD_TYPECHECK=false to keep it.
ARG SKIP_BUILD_TYPECHECK=true
ENV BACKEND_INTERNAL_URL=${BACKEND_INTERNAL_URL} \
    NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_PUBLIC_APP_NAME=${NEXT_PUBLIC_APP_NAME} \
    SKIP_BUILD_TYPECHECK=${SKIP_BUILD_TYPECHECK}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

# ---- runtime ----------------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS runtime
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
WORKDIR /app
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD node -e "fetch('http://127.0.0.1:3000/login').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
