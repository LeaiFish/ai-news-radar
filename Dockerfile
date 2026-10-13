# syntax=docker/dockerfile:1
# One image for every role: setup (migrations and seed), api, worker and web.
# Build arg NPM_REGISTRY switches the npm registry (e.g. https://registry.npmmirror.com in mainland China).
FROM node:24-trixie-slim AS base
WORKDIR /app
# pg_dump for the optional database backups (Debian's client matches the PostgreSQL 17 server in compose).
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client ca-certificates python3 python3-venv \
 && rm -rf /var/lib/apt/lists/*

FROM base AS build
ARG NPM_REGISTRY=
COPY package.json package-lock.json tsconfig.base.json ./
# Explicit source allowlist: never copy a user's whole mixed project directory.
COPY apps/ apps/
COPY packages/ packages/
COPY industry/ industry/
COPY site/ site/
COPY modules/ modules/
COPY database/ database/
COPY scripts/ scripts/
COPY licenses/ licenses/
COPY NOTICE LICENSE ./
COPY assets/og-fonts/ assets/og-fonts/
COPY legacy-radar.html ./
COPY assets/logo.svg assets/styles.css assets/sidebar.css assets/topics.css assets/perspective.css assets/perspective.js assets/public-projection.js assets/
COPY config/topics.json config/source_tiers.json config/focus_sources.json config/
COPY feeds/follow.example.opml feeds/
COPY requirements.txt ./
RUN --mount=type=secret,id=proxy_ca sh -c 'if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; npm ci --no-audit --no-fund ${NPM_REGISTRY:+--registry=$NPM_REGISTRY}'
RUN --mount=type=secret,id=proxy_ca python3 -m venv /app/.venv && sh -c 'if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; /app/.venv/bin/pip install --no-cache-dir -r requirements.txt'
RUN npm run build -w @aihot/web && node scripts/package-public-site.ts && npm prune --omit=dev --no-audit --no-fund

FROM base
ENV NODE_ENV=production
ENV PATH="/app/.venv/bin:$PATH"
COPY --from=build --chown=node:node /app /app
RUN mkdir -p /data && chown node:node /data
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.ts"]
