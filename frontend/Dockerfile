# =============================================================================
# Alpha Quantum Frontend — Multi-stage build
# Stage 1: deps     → install npm packages
# Stage 2: builder  → run `next build`
# Stage 3: runner   → minimal runtime image, non-root, standalone output
# =============================================================================

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
# `npm install` (vs ci) is more tolerant: handles platform-specific optional
# deps (e.g. @emnapi/runtime on arm vs amd64) without exploding when the lock
# file is generated on a different OS. For production deterministic builds
# regenerate the lock on the target platform first, then switch to npm ci.
RUN npm install --no-audit --no-fund

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Non-root user (Alpine uid pattern)
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Bring over only what we need at runtime
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next ./.next
COPY --from=builder --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /app/package.json ./package.json

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["npx", "next", "start"]
